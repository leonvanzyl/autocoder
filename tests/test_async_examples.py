"""
Async Test Examples
===================

Example tests demonstrating pytest-asyncio usage with the Autocoder codebase.
These tests verify async functions and FastAPI endpoints work correctly.
"""

from pathlib import Path

# =============================================================================
# Basic Async Tests
# =============================================================================


async def test_async_basic():
    """Basic async test to verify pytest-asyncio is working."""
    import asyncio

    await asyncio.sleep(0.01)
    assert True


async def test_async_with_fixture(temp_db: Path):
    """Test that sync fixtures work with async tests."""
    assert temp_db.exists()
    assert (temp_db / "features.db").exists()


async def test_async_temp_db(async_temp_db: Path):
    """Test the async_temp_db fixture."""
    assert async_temp_db.exists()
    assert (async_temp_db / "features.db").exists()


# =============================================================================
# Database Async Tests
# =============================================================================


async def test_async_feature_creation(async_temp_db: Path):
    """Test creating features in an async context."""
    from api.database import Feature, create_database

    _, SessionLocal = create_database(async_temp_db)
    session = SessionLocal()

    try:
        feature = Feature(
            priority=1,
            category="test",
            name="Async Test Feature",
            description="Created in async test",
            steps=["Step 1", "Step 2"],
        )
        session.add(feature)
        session.commit()

        # Verify
        result = session.query(Feature).filter(Feature.name == "Async Test Feature").first()
        assert result is not None
        assert result.priority == 1
    finally:
        session.close()


async def test_async_feature_query(populated_db: Path):
    """Test querying features in an async context."""
    from api.database import Feature, create_database

    _, SessionLocal = create_database(populated_db)
    session = SessionLocal()

    try:
        # Query passing features
        passing = session.query(Feature).filter(Feature.passes == True).all()
        assert len(passing) == 2

        # Query in-progress features
        in_progress = session.query(Feature).filter(Feature.in_progress == True).all()
        assert len(in_progress) == 1
    finally:
        session.close()


# =============================================================================
# Security Hook Async Tests
# =============================================================================


async def test_bash_security_hook_allowed():
    """Test that allowed commands pass the async security hook."""
    from security import bash_security_hook

    # Test allowed command - hook returns empty dict for allowed commands
    result = await bash_security_hook({
        "tool_name": "Bash",
        "tool_input": {"command": "git status"}
    })

    # Should return empty dict (allowed) - no "decision": "block"
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("decision") != "block"


async def test_bash_security_hook_blocked():
    """Test that blocked commands are rejected by the async security hook."""
    from security import bash_security_hook

    # Test blocked command (sudo is in blocklist)
    # The hook returns {"decision": "block", "reason": "..."} for blocked commands
    result = await bash_security_hook({
        "tool_name": "Bash",
        "tool_input": {"command": "sudo rm -rf /"}
    })

    assert result.get("decision") == "block"
    assert "reason" in result


async def test_bash_security_hook_with_project_dir(temp_project_dir: Path):
    """Test security hook with project directory context."""
    from security import bash_security_hook

    # Create a minimal .autocoder config
    autocoder_dir = temp_project_dir / ".autocoder"
    autocoder_dir.mkdir(exist_ok=True)

    # Test with allowed command in project context
    # Use consistent payload shape with tool_name and tool_input
    result = await bash_security_hook(
        {"tool_name": "Bash", "tool_input": {"command": "npm install"}},
        context={"project_dir": str(temp_project_dir)}
    )
    assert result is not None


# =============================================================================
# Orchestrator Async Tests
# =============================================================================


async def test_orchestrator_initialization(mock_project_dir: Path):
    """Test ParallelOrchestrator async initialization."""
    from parallel_orchestrator import ParallelOrchestrator

    orchestrator = ParallelOrchestrator(
        project_dir=mock_project_dir,
        max_concurrency=2,
        yolo_mode=True,
    )

    assert orchestrator.max_concurrency == 2
    assert orchestrator.yolo_mode is True
    assert orchestrator.is_running is False


async def test_orchestrator_get_ready_features(populated_db: Path):
    """Test getting ready features from orchestrator."""
    from parallel_orchestrator import ParallelOrchestrator

    orchestrator = ParallelOrchestrator(
        project_dir=populated_db,
        max_concurrency=2,
    )

    ready = orchestrator.get_ready_features()

    # Should have pending features that are not in_progress and not passing
    assert isinstance(ready, list)
    # Features 4 and 5 should be ready (not passing, not in_progress)
    assert len(ready) >= 2


async def test_orchestrator_all_complete_check(populated_db: Path):
    """Test checking if all features are complete."""
    from parallel_orchestrator import ParallelOrchestrator

    orchestrator = ParallelOrchestrator(
        project_dir=populated_db,
        max_concurrency=2,
    )

    # Should not be complete (we have pending features)
    assert orchestrator.get_all_complete() is False


# =============================================================================
# FastAPI Endpoint Async Tests (using httpx)
# =============================================================================


async def test_health_endpoint(async_client):
    """Test the health check endpoint."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


async def test_list_projects_endpoint(async_client):
    """Test listing projects endpoint."""
    response = await async_client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# =============================================================================
# Logging Async Tests
# =============================================================================


async def test_logging_config_async():
    """Test that logging works correctly in async context."""
    from api.logging_config import get_logger, setup_logging

    # Setup logging (idempotent)
    setup_logging()

    logger = get_logger("test_async")
    logger.info("Test message from async test")

    # If we get here without exception, logging works
    assert True


# =============================================================================
# Concurrent Async Tests
# =============================================================================


async def test_concurrent_database_access(populated_db: Path):
    """Test concurrent database access doesn't cause issues."""
    import asyncio

    from api.database import Feature, create_database

    _, SessionLocal = create_database(populated_db)

    async def read_features():
        """Simulate async database read."""
        session = SessionLocal()
        try:
            await asyncio.sleep(0.01)  # Simulate async work
            features = session.query(Feature).all()
            return len(features)
        finally:
            session.close()

    # Run multiple concurrent reads
    results = await asyncio.gather(
        read_features(),
        read_features(),
        read_features(),
    )

    # All should return the same count
    assert all(r == results[0] for r in results)
    assert results[0] == 5  # populated_db has 5 features
