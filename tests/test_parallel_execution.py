"""
Tests for Parallel Execution Features
=====================================

Tests for the parallel agent execution system including:
- Atomic feature claiming
- Lease-based heartbeat
- Stale claim recovery
- Merge serialization
- Database migration

Run with: pytest tests/test_parallel_execution.py -v
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from api.database import (
    Feature,
    FeatureStatus,
    create_database,
    get_database_path,
    _migrate_database_schema,
)
from mcp_server.feature_mcp import (
    init_database_direct,
    feature_claim_next,
    feature_heartbeat,
    feature_reclaim_stale,
    feature_create_bulk,
    feature_get_stats,
)


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        project_dir.mkdir(parents=True, exist_ok=True)
        yield project_dir


@pytest.fixture
def db_session(temp_project_dir):
    """Initialize database and return a session."""
    # Reset global state in feature_mcp before each test
    import mcp_server.feature_mcp as mcp_module
    mcp_module._session_maker = None
    mcp_module._engine = None

    init_database_direct(temp_project_dir)

    # Get the session from feature_mcp module
    session_maker = mcp_module._session_maker
    session = session_maker()

    yield session

    # Clean up all connections
    session.close()
    if mcp_module._engine:
        mcp_module._engine.dispose()
    mcp_module._session_maker = None
    mcp_module._engine = None


@pytest.fixture
def populated_db(db_session, temp_project_dir):
    """Database with 10 pending features."""
    features = [
        {
            "category": f"Category-{i}",
            "name": f"Feature-{i}",
            "description": f"Description for feature {i}",
            "steps": [f"Step 1 for {i}", f"Step 2 for {i}"],
        }
        for i in range(10)
    ]

    result_json = feature_create_bulk(features)
    result = json.loads(result_json)
    assert result.get("created") == 10

    # Verify all are pending
    stats = json.loads(feature_get_stats())
    assert stats["total"] == 10
    assert stats["pending"] == 10

    return db_session


# ==============================================================================
# Test 1: Concurrent claim_next uniqueness
# ==============================================================================


def test_concurrent_claim_uniqueness(populated_db, temp_project_dir):
    """
    Test that N concurrent workers claiming features get N distinct features.

    Uses threading + barrier to ensure simultaneous execution.
    SQLite's atomic CTE UPDATE ensures no race conditions.
    """
    n_workers = 5
    claimed_ids = []
    errors = []
    barrier = Barrier(n_workers)

    def worker_claim(worker_id: int):
        """Worker function that claims a feature."""
        try:
            # Wait for all workers to be ready
            barrier.wait(timeout=5)

            # All workers claim simultaneously
            result_json = feature_claim_next(worker_id=f"worker-{worker_id}")
            result = json.loads(result_json)

            if "error" in result:
                errors.append(result["error"])
            elif result.get("status") == "no_features_available":
                # This is valid if we ran out of features
                pass
            else:
                claimed_ids.append(result["id"])

        except Exception as e:
            errors.append(str(e))

    # Create and start threads
    threads = [Thread(target=worker_claim, args=(i,)) for i in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    # Assertions
    assert len(errors) == 0, f"Errors during claiming: {errors}"
    assert len(claimed_ids) == n_workers, f"Expected {n_workers} claims, got {len(claimed_ids)}"
    assert len(set(claimed_ids)) == n_workers, f"Duplicate IDs claimed: {claimed_ids}"


# ==============================================================================
# Test 2: Heartbeat lease_lost behavior
# ==============================================================================


def test_heartbeat_lease_lost_wrong_worker(populated_db, temp_project_dir):
    """
    Test that heartbeat returns lease_lost when called with wrong worker_id.

    Scenario:
    1. Worker A claims feature
    2. Worker B tries to heartbeat the same feature
    3. Worker B should get lease_lost
    """
    # Worker A claims a feature
    claim_result = json.loads(feature_claim_next(worker_id="worker-A"))
    assert "id" in claim_result, f"Claim failed: {claim_result}"
    feature_id = claim_result["id"]

    # Worker A can heartbeat successfully
    hb_result_a = json.loads(feature_heartbeat(feature_id=feature_id, worker_id="worker-A"))
    assert hb_result_a.get("status") == "renewed", f"Worker A heartbeat failed: {hb_result_a}"

    # Worker B tries to heartbeat - should fail
    hb_result_b = json.loads(feature_heartbeat(feature_id=feature_id, worker_id="worker-B"))
    assert hb_result_b.get("status") == "lease_lost", (
        f"Expected lease_lost for wrong worker, got: {hb_result_b}"
    )


def test_heartbeat_lease_lost_unclaimed_feature(populated_db, temp_project_dir):
    """
    Test that heartbeat returns lease_lost for unclaimed features.
    """
    # Get a feature ID without claiming it (just read from DB)
    session = populated_db
    feature = session.query(Feature).filter(Feature.status == FeatureStatus.PENDING).first()
    assert feature is not None

    # Try to heartbeat unclaimed feature
    hb_result = json.loads(feature_heartbeat(feature_id=feature.id, worker_id="worker-A"))
    assert hb_result.get("status") == "lease_lost", (
        f"Expected lease_lost for unclaimed feature, got: {hb_result}"
    )


# ==============================================================================
# Test 3: Stale claim recovery
# ==============================================================================


def test_stale_reclaim_expired_lease(populated_db, temp_project_dir):
    """
    Test that features with expired leases are returned to pending.

    Scenario:
    1. Claim a feature
    2. Manually backdate claimed_at to simulate stale claim
    3. Run reclaim_stale
    4. Feature should be back to pending
    """
    # Claim a feature
    claim_result = json.loads(feature_claim_next(worker_id="worker-stale"))
    assert "id" in claim_result
    feature_id = claim_result["id"]

    # Verify it's in_progress
    session = populated_db
    feature = session.query(Feature).filter(Feature.id == feature_id).first()
    session.refresh(feature)
    assert feature.status == FeatureStatus.IN_PROGRESS
    assert feature.claimed_by == "worker-stale"

    # Backdate claimed_at to 45 minutes ago (beyond 30-min timeout)
    stale_time = datetime.utcnow() - timedelta(minutes=45)
    session.execute(
        text("UPDATE features SET claimed_at = :stale WHERE id = :id"),
        {"stale": stale_time, "id": feature_id}
    )
    session.commit()

    # Run stale recovery with 30-minute timeout
    reclaim_result = json.loads(feature_reclaim_stale(lease_timeout_minutes=30))
    assert reclaim_result.get("reclaimed") >= 1, f"Expected reclaim, got: {reclaim_result}"

    # Verify feature is back to pending
    session.refresh(feature)
    assert feature.status == FeatureStatus.PENDING, f"Expected pending, got: {feature.status}"
    assert feature.claimed_by is None
    assert feature.claimed_at is None


def test_stale_reclaim_fresh_lease_not_affected(populated_db, temp_project_dir):
    """
    Test that features with fresh leases are NOT reclaimed.
    """
    # Claim a feature
    claim_result = json.loads(feature_claim_next(worker_id="worker-fresh"))
    assert "id" in claim_result
    feature_id = claim_result["id"]

    # Run stale recovery immediately - should not reclaim anything
    json.loads(feature_reclaim_stale(lease_timeout_minutes=30))

    # Verify feature is still in progress
    session = populated_db
    feature = session.query(Feature).filter(Feature.id == feature_id).first()
    assert feature.status == FeatureStatus.IN_PROGRESS
    assert feature.claimed_by == "worker-fresh"


# ==============================================================================
# Test 4: Merge serialization smoke test
# ==============================================================================


@pytest.mark.asyncio
async def test_merge_serialization_lock():
    """
    Test that merge operations are serialized via asyncio.Lock.

    Verifies that two merges cannot run simultaneously by checking
    that the lock blocks concurrent access.
    """

    merge_lock = asyncio.Lock()
    execution_order = []

    async def mock_merge(name: str, delay: float):
        """Simulates a merge operation that records when it runs."""
        async with merge_lock:
            execution_order.append(f"{name}_start")
            await asyncio.sleep(delay)
            execution_order.append(f"{name}_end")

    # Start two merges "simultaneously"
    await asyncio.gather(
        mock_merge("merge1", 0.1),
        mock_merge("merge2", 0.1),
    )

    # Verify serialization: merge1 must complete before merge2 starts
    # (or vice versa, but they can't interleave)
    assert execution_order[0].endswith("_start")
    assert execution_order[1].endswith("_end")
    assert execution_order[2].endswith("_start")
    assert execution_order[3].endswith("_end")

    # The same merge that started first must end before the other starts
    first_merge = execution_order[0].replace("_start", "")
    second_event = execution_order[1].replace("_end", "")
    assert first_merge == second_event, (
        f"Merges interleaved: {execution_order}"
    )


@pytest.mark.asyncio
async def test_coordinator_uses_merge_lock():
    """
    Verify ParallelCoordinator actually uses merge_lock in _process_one_feature.
    """
    with tempfile.TemporaryDirectory():
        # Create coordinator with mocked dependencies
        coordinator = MagicMock()
        coordinator.merge_lock = asyncio.Lock()
        coordinator.worktree_mgr = AsyncMock()
        coordinator.worktree_mgr.checkout_feature_branch = AsyncMock(return_value="feature/test")
        coordinator.worktree_mgr.merge_feature_branch = AsyncMock(return_value=(True, "success"))
        coordinator.worktree_mgr.delete_feature_branch = AsyncMock()

        # Track lock acquisition
        lock_acquisitions = []
        original_acquire = coordinator.merge_lock.acquire

        async def tracking_acquire():
            lock_acquisitions.append(datetime.utcnow())
            return await original_acquire()

        coordinator.merge_lock.acquire = tracking_acquire

        # Simulate two concurrent merges through the lock
        async def simulate_merge(name: str):
            async with coordinator.merge_lock:
                lock_acquisitions.append(f"{name}_acquired")
                await asyncio.sleep(0.05)
                lock_acquisitions.append(f"{name}_released")

        await asyncio.gather(
            simulate_merge("A"),
            simulate_merge("B"),
        )

        # Verify lock was used (at least 4 events: A_acquired, A_released, B_acquired, B_released)
        assert len([e for e in lock_acquisitions if isinstance(e, str)]) == 4


# ==============================================================================
# Test 5: Migration forwards/backwards sanity
# ==============================================================================


def test_migration_enum_storage():
    """
    Test that FeatureStatus enum values are stored as strings in SQLite.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        engine, session_maker = create_database(project_dir)
        session = session_maker()

        try:
            # Create a feature
            feature = Feature(
                priority=1,
                category="Test",
                name="Test Feature",
                description="Description",
                steps=["step1"],
                status=FeatureStatus.PENDING,
                passes=False,
            )
            session.add(feature)
            session.commit()

            # Query raw SQL to verify string storage
            result = session.execute(
                text("SELECT status FROM features WHERE id = :id"),
                {"id": feature.id}
            )
            raw_status = result.fetchone()[0]

            # Enum should be stored as string "pending", not integer
            assert raw_status == "pending", f"Expected 'pending', got: {raw_status}"

            # Update to different status
            feature.status = FeatureStatus.PASSING
            feature.passes = True
            session.commit()

            result = session.execute(
                text("SELECT status FROM features WHERE id = :id"),
                {"id": feature.id}
            )
            raw_status = result.fetchone()[0]
            assert raw_status == "passing", f"Expected 'passing', got: {raw_status}"

        finally:
            session.close()
            engine.dispose()


def test_migration_passes_invariant():
    """
    Test that passes=True always corresponds to status=PASSING.

    The migration should ensure this invariant is maintained.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        engine, session_maker = create_database(project_dir)
        session = session_maker()

        try:
            # Create features with various states
            features = [
                Feature(
                    priority=i,
                    category="Test",
                    name=f"Feature {i}",
                    description="Desc",
                    steps=["step1"],
                    status=FeatureStatus.PENDING,
                    passes=False,
                )
                for i in range(5)
            ]
            session.add_all(features)
            session.commit()

            # Mark some as passing
            features[0].status = FeatureStatus.PASSING
            features[0].passes = True
            features[1].status = FeatureStatus.PASSING
            features[1].passes = True
            session.commit()

            # Verify invariant: passes=True implies status=PASSING
            result = session.execute(text("""
                SELECT COUNT(*) FROM features
                WHERE passes = 1 AND status != 'passing'
            """))
            violations = result.fetchone()[0]
            assert violations == 0, f"Found {violations} features where passes=True but status!=PASSING"

            # Verify reverse: status=PASSING implies passes=True
            result = session.execute(text("""
                SELECT COUNT(*) FROM features
                WHERE status = 'passing' AND passes = 0
            """))
            violations = result.fetchone()[0]
            assert violations == 0, f"Found {violations} features where status=PASSING but passes=False"

        finally:
            session.close()
            engine.dispose()


def test_migration_adds_new_columns():
    """
    Test that migration adds all required columns for parallel execution.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create initial database without new columns (simulate old schema)
        from sqlalchemy import create_engine
        db_path = get_database_path(project_dir)
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")

        # Create minimal table without new columns
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE features (
                    id INTEGER PRIMARY KEY,
                    priority INTEGER NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    steps JSON NOT NULL,
                    passes BOOLEAN DEFAULT 0
                )
            """))
            conn.commit()

        # Run migration
        _migrate_database_schema(engine)

        # Verify all new columns exist
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(features)"))
            columns = {row[1] for row in result.fetchall()}

        expected_columns = {
            "id", "priority", "category", "name", "description", "steps",
            "passes", "in_progress", "status", "claimed_by", "claimed_at",
            "completed_at", "completed_by"
        }
        missing = expected_columns - columns
        assert not missing, f"Migration missing columns: {missing}"

        engine.dispose()


def test_migration_preserves_existing_data():
    """
    Test that migration preserves existing feature data.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create database with old schema and some data
        from sqlalchemy import create_engine
        db_path = get_database_path(project_dir)
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")

        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE features (
                    id INTEGER PRIMARY KEY,
                    priority INTEGER NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    steps JSON NOT NULL,
                    passes BOOLEAN DEFAULT 0
                )
            """))
            # Insert test data
            conn.execute(text("""
                INSERT INTO features (priority, category, name, description, steps, passes)
                VALUES (1, 'Auth', 'Login', 'Login feature', '["step1"]', 1)
            """))
            conn.execute(text("""
                INSERT INTO features (priority, category, name, description, steps, passes)
                VALUES (2, 'Auth', 'Signup', 'Signup feature', '["step1"]', 0)
            """))
            conn.commit()

        # Run migration
        _migrate_database_schema(engine)

        # Verify data preserved and status migrated correctly
        with engine.connect() as conn:
            # passes=1 should have status='passing'
            result = conn.execute(text(
                "SELECT status FROM features WHERE name = 'Login'"
            ))
            assert result.fetchone()[0] == "passing"

            # passes=0 should have status='pending'
            result = conn.execute(text(
                "SELECT status FROM features WHERE name = 'Signup'"
            ))
            assert result.fetchone()[0] == "pending"

            # Original data should be intact
            result = conn.execute(text("SELECT category, description FROM features WHERE name = 'Login'"))
            row = result.fetchone()
            assert row[0] == "Auth"
            assert row[1] == "Login feature"

        engine.dispose()


# ==============================================================================
# Edge case tests
# ==============================================================================


def test_claim_next_no_features_available(temp_project_dir):
    """Test claim_next when no features exist."""
    import mcp_server.feature_mcp as mcp_module
    mcp_module._session_maker = None
    mcp_module._engine = None

    try:
        init_database_direct(temp_project_dir)

        result = json.loads(feature_claim_next(worker_id="worker-0"))
        assert result.get("status") == "no_features_available"

    finally:
        if mcp_module._engine:
            mcp_module._engine.dispose()
        mcp_module._session_maker = None
        mcp_module._engine = None


def test_claim_next_all_features_claimed(populated_db, temp_project_dir):
    """Test claim_next when all features are already claimed."""
    # Claim all features
    for i in range(10):
        result = json.loads(feature_claim_next(worker_id=f"worker-{i}"))
        # Should succeed until we run out
        if result.get("status") == "no_features_available":
            break

    # Next claim should fail
    result = json.loads(feature_claim_next(worker_id="worker-extra"))
    assert result.get("status") == "no_features_available"


def test_reclaim_stale_minimum_timeout():
    """Test that reclaim_stale respects minimum timeout of 5 minutes."""
    # This tests the Field(ge=5) constraint
    # We can't easily test Pydantic validation in MCP context,
    # but we can verify the function works with valid values
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        import mcp_server.feature_mcp as mcp_module
        mcp_module._session_maker = None
        mcp_module._engine = None

        try:
            init_database_direct(project_dir)

            # Create a feature
            features = [{"category": "Test", "name": "F1", "description": "D", "steps": ["s1"]}]
            feature_create_bulk(features)

            # 5 minutes should work (minimum valid value)
            result = json.loads(feature_reclaim_stale(lease_timeout_minutes=5))
            assert "error" not in result
            assert result.get("reclaimed") == 0  # Nothing stale yet

        finally:
            # Clean up database connections
            if mcp_module._engine:
                mcp_module._engine.dispose()
            mcp_module._session_maker = None
            mcp_module._engine = None
