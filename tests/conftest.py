"""
Pytest Configuration and Fixtures
=================================

Central pytest configuration and shared fixtures for all tests.
Includes async fixtures for testing FastAPI endpoints and async functions.
"""

import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Basic Fixtures
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with basic structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create prompts directory
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir()

    return project_dir


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary database for testing.

    Yields the path to the temp project directory with an initialized database.
    """
    from api.database import create_database, invalidate_engine_cache

    project_dir = tmp_path / "test_db_project"
    project_dir.mkdir()

    # Create prompts directory (required by some code)
    (project_dir / "prompts").mkdir()

    # Initialize database
    create_database(project_dir)

    yield project_dir

    # Dispose cached engine to prevent file locks on Windows
    invalidate_engine_cache(project_dir)


@pytest.fixture
def db_session(temp_db: Path):
    """Get a database session for testing.

    Provides a session that is automatically rolled back after each test.
    """
    from api.database import create_database

    _, SessionLocal = create_database(temp_db)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# Async Fixtures
# =============================================================================


@pytest.fixture
async def async_temp_db(tmp_path: Path) -> AsyncGenerator[Path, None]:
    """Async version of temp_db fixture.

    Creates a temporary database for async tests.
    """
    from api.database import create_database, invalidate_engine_cache

    project_dir = tmp_path / "async_test_project"
    project_dir.mkdir()
    (project_dir / "prompts").mkdir()

    # Initialize database (sync operation, but fixture is async)
    create_database(project_dir)

    yield project_dir

    # Dispose cached engine to prevent file locks on Windows
    invalidate_engine_cache(project_dir)


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================


@pytest.fixture
def test_app():
    """Create a test FastAPI application instance.

    Returns the FastAPI app configured for testing.
    """
    from server.main import app

    return app


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator:
    """Create an async HTTP client for testing FastAPI endpoints.

    Usage:
        async def test_endpoint(async_client):
            response = await async_client.get("/api/health")
            assert response.status_code == 200
    """
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test"
    ) as client:
        yield client


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_env(monkeypatch):
    """Fixture to safely modify environment variables.

    Usage:
        def test_with_env(mock_env):
            mock_env("API_KEY", "test_key")
            # Test code here
    """
    def _set_env(key: str, value: str):
        monkeypatch.setenv(key, value)

    return _set_env


@pytest.fixture
def mock_project_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a fully configured mock project directory.

    Includes:
    - prompts/ directory with sample files
    - .autocoder/ directory for config
    - features.db initialized
    """
    from api.database import create_database, invalidate_engine_cache

    project_dir = tmp_path / "mock_project"
    project_dir.mkdir()

    # Create directory structure
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir()

    autocoder_dir = project_dir / ".autocoder"
    autocoder_dir.mkdir()

    # Create sample app_spec
    (prompts_dir / "app_spec.txt").write_text(
        "<app_name>Test App</app_name>\n<description>Test description</description>"
    )

    # Initialize database
    create_database(project_dir)

    yield project_dir

    # Dispose cached engine to prevent file locks on Windows
    invalidate_engine_cache(project_dir)


# =============================================================================
# Feature Fixtures
# =============================================================================


@pytest.fixture
def sample_feature_data() -> dict:
    """Return sample feature data for testing."""
    return {
        "priority": 1,
        "category": "test",
        "name": "Test Feature",
        "description": "A test feature for unit tests",
        "steps": ["Step 1", "Step 2", "Step 3"],
    }


@pytest.fixture
def populated_db(temp_db: Path, sample_feature_data: dict) -> Generator[Path, None, None]:
    """Create a database populated with sample features.

    Returns the project directory path.
    """
    from api.database import Feature, create_database, invalidate_engine_cache

    _, SessionLocal = create_database(temp_db)
    session = SessionLocal()

    try:
        # Add sample features
        for i in range(5):
            feature = Feature(
                priority=i + 1,
                category=f"category_{i % 2}",
                name=f"Feature {i + 1}",
                description=f"Description for feature {i + 1}",
                steps=[f"Step {j}" for j in range(3)],
                passes=i < 2,  # First 2 features are passing
                in_progress=i == 2,  # Third feature is in progress
            )
            session.add(feature)

        session.commit()
    finally:
        session.close()

    yield temp_db

    # Dispose cached engine to prevent file locks on Windows
    invalidate_engine_cache(temp_db)
