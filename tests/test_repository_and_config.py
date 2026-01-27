"""
Tests for FeatureRepository and AutocoderConfig
================================================

Unit tests for the repository pattern and configuration classes.
"""

from pathlib import Path

# =============================================================================
# FeatureRepository Tests
# =============================================================================


class TestFeatureRepository:
    """Tests for the FeatureRepository class."""

    def test_get_by_id(self, populated_db: Path):
        """Test getting a feature by ID."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            feature = repo.get_by_id(1)

            assert feature is not None
            assert feature.id == 1
            assert feature.name == "Feature 1"
        finally:
            session.close()

    def test_get_by_id_not_found(self, populated_db: Path):
        """Test getting a non-existent feature returns None."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            feature = repo.get_by_id(9999)

            assert feature is None
        finally:
            session.close()

    def test_get_all(self, populated_db: Path):
        """Test getting all features."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            features = repo.get_all()

            assert len(features) == 5  # populated_db has 5 features
        finally:
            session.close()

    def test_count(self, populated_db: Path):
        """Test counting features."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            count = repo.count()

            assert count == 5
        finally:
            session.close()

    def test_get_passing(self, populated_db: Path):
        """Test getting passing features."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            passing = repo.get_passing()

            # populated_db marks first 2 features as passing
            assert len(passing) == 2
            assert all(f.passes for f in passing)
        finally:
            session.close()

    def test_get_passing_ids(self, populated_db: Path):
        """Test getting IDs of passing features."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            ids = repo.get_passing_ids()

            assert isinstance(ids, set)
            assert len(ids) == 2
        finally:
            session.close()

    def test_get_in_progress(self, populated_db: Path):
        """Test getting in-progress features."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            in_progress = repo.get_in_progress()

            # populated_db marks feature 3 as in_progress
            assert len(in_progress) == 1
            assert in_progress[0].in_progress
        finally:
            session.close()

    def test_get_pending(self, populated_db: Path):
        """Test getting pending features (not passing, not in progress)."""
        from api.database import create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(populated_db)
        session = SessionLocal()

        try:
            repo = FeatureRepository(session)
            pending = repo.get_pending()

            # 5 total - 2 passing - 1 in_progress = 2 pending
            assert len(pending) == 2
            for f in pending:
                assert not f.passes
                assert not f.in_progress
        finally:
            session.close()

    def test_mark_in_progress(self, temp_db: Path):
        """Test marking a feature as in progress."""
        from api.database import Feature, create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(temp_db)
        session = SessionLocal()

        try:
            # Create a feature
            feature = Feature(
                priority=1,
                category="test",
                name="Test Feature",
                description="Test",
                steps=["Step 1"],
            )
            session.add(feature)
            session.commit()
            feature_id = feature.id

            # Mark it in progress
            repo = FeatureRepository(session)
            updated = repo.mark_in_progress(feature_id)

            assert updated is not None
            assert updated.in_progress
            assert updated.started_at is not None
        finally:
            session.close()

    def test_mark_passing(self, temp_db: Path):
        """Test marking a feature as passing."""
        from api.database import Feature, create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(temp_db)
        session = SessionLocal()

        try:
            # Create a feature
            feature = Feature(
                priority=1,
                category="test",
                name="Test Feature",
                description="Test",
                steps=["Step 1"],
            )
            session.add(feature)
            session.commit()
            feature_id = feature.id

            # Mark it passing
            repo = FeatureRepository(session)
            updated = repo.mark_passing(feature_id)

            assert updated is not None
            assert updated.passes
            assert not updated.in_progress
            assert updated.completed_at is not None
        finally:
            session.close()

    def test_mark_failing(self, temp_db: Path):
        """Test marking a feature as failing."""
        from api.database import Feature, create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(temp_db)
        session = SessionLocal()

        try:
            # Create a passing feature
            feature = Feature(
                priority=1,
                category="test",
                name="Test Feature",
                description="Test",
                steps=["Step 1"],
                passes=True,
            )
            session.add(feature)
            session.commit()
            feature_id = feature.id

            # Mark it failing
            repo = FeatureRepository(session)
            updated = repo.mark_failing(feature_id)

            assert updated is not None
            assert not updated.passes
            assert not updated.in_progress
            assert updated.last_failed_at is not None
        finally:
            session.close()

    def test_get_ready_features_with_dependencies(self, temp_db: Path):
        """Test getting ready features respects dependencies."""
        from api.database import Feature, create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(temp_db)
        session = SessionLocal()

        try:
            # Create features with dependencies
            f1 = Feature(priority=1, category="test", name="F1", description="", steps=[], passes=True)
            f2 = Feature(priority=2, category="test", name="F2", description="", steps=[], passes=False)
            f3 = Feature(priority=3, category="test", name="F3", description="", steps=[], passes=False, dependencies=[1])
            f4 = Feature(priority=4, category="test", name="F4", description="", steps=[], passes=False, dependencies=[2])

            session.add_all([f1, f2, f3, f4])
            session.commit()

            repo = FeatureRepository(session)
            ready = repo.get_ready_features()

            # F2 is ready (no deps), F3 is ready (F1 passes), F4 is NOT ready (F2 not passing)
            ready_names = [f.name for f in ready]
            assert "F2" in ready_names
            assert "F3" in ready_names
            assert "F4" not in ready_names
        finally:
            session.close()

    def test_get_blocked_features(self, temp_db: Path):
        """Test getting blocked features with their blockers."""
        from api.database import Feature, create_database
        from api.feature_repository import FeatureRepository

        _, SessionLocal = create_database(temp_db)
        session = SessionLocal()

        try:
            # Create features with dependencies
            f1 = Feature(priority=1, category="test", name="F1", description="", steps=[], passes=False)
            f2 = Feature(priority=2, category="test", name="F2", description="", steps=[], passes=False, dependencies=[1])

            session.add_all([f1, f2])
            session.commit()

            repo = FeatureRepository(session)
            blocked = repo.get_blocked_features()

            # F2 is blocked by F1
            assert len(blocked) == 1
            feature, blocking_ids = blocked[0]
            assert feature.name == "F2"
            assert 1 in blocking_ids  # F1's ID
        finally:
            session.close()


# =============================================================================
# AutocoderConfig Tests
# =============================================================================


class TestAutocoderConfig:
    """Tests for the AutocoderConfig class."""

    def test_default_values(self, monkeypatch, tmp_path):
        """Test that default values are loaded correctly."""
        # Change to a directory without .env file
        monkeypatch.chdir(tmp_path)

        # Clear any env vars that might interfere
        env_vars = [
            "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "PLAYWRIGHT_BROWSER",
            "PLAYWRIGHT_HEADLESS", "API_TIMEOUT_MS", "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)  # Explicitly skip .env file

        assert config.playwright_browser == "firefox"
        assert config.playwright_headless is True
        assert config.api_timeout_ms == 120000
        assert config.anthropic_default_sonnet_model == "claude-sonnet-4-20250514"

    def test_env_var_override(self, monkeypatch, tmp_path):
        """Test that environment variables override defaults."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PLAYWRIGHT_BROWSER", "chrome")
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "false")
        monkeypatch.setenv("API_TIMEOUT_MS", "300000")

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)

        assert config.playwright_browser == "chrome"
        assert config.playwright_headless is False
        assert config.api_timeout_ms == 300000

    def test_is_using_alternative_api_false(self, monkeypatch, tmp_path):
        """Test is_using_alternative_api when not configured."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)

        assert config.is_using_alternative_api is False

    def test_is_using_alternative_api_true(self, monkeypatch, tmp_path):
        """Test is_using_alternative_api when configured."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token")

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)

        assert config.is_using_alternative_api is True

    def test_is_using_ollama_false(self, monkeypatch, tmp_path):
        """Test is_using_ollama when not using Ollama."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)

        assert config.is_using_ollama is False

    def test_is_using_ollama_true(self, monkeypatch, tmp_path):
        """Test is_using_ollama when using Ollama."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "ollama")

        from api.config import AutocoderConfig
        config = AutocoderConfig(_env_file=None)

        assert config.is_using_ollama is True

    def test_get_config_singleton(self, monkeypatch, tmp_path):
        """Test that get_config returns a singleton."""
        # Note: get_config uses the default config loading, which reads .env
        # This test just verifies the singleton pattern works
        import api.config
        api.config._config = None

        from api.config import get_config
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_reload_config(self, monkeypatch, tmp_path):
        """Test that reload_config creates a new instance."""
        import api.config
        api.config._config = None

        # Get initial config
        from api.config import get_config, reload_config
        config1 = get_config()

        # Reload creates a new instance
        config2 = reload_config()

        assert config2 is not config1
