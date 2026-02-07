#!/usr/bin/env python3
"""
Unit tests for detach.py module.

Tests cover:
- File detection patterns
- Backup creation and manifest
- Restore functionality
- Edge cases (locked projects, missing backups, etc.)
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import detach


class TestGetAutoforgeFiles(unittest.TestCase):
    """Tests for get_autoforge_files function."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_detects_autoforge_directory(self):
        """Should detect .autoforge directory."""
        (self.project_dir / ".autoforge").mkdir()
        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, ".autoforge")

    def test_detects_prompts_directory(self):
        """Should detect prompts directory."""
        (self.project_dir / "prompts").mkdir()
        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "prompts")

    def test_detects_features_db(self):
        """Should detect features.db file."""
        (self.project_dir / "features.db").touch()
        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "features.db")

    def test_detects_claude_md(self):
        """Should detect CLAUDE.md file."""
        (self.project_dir / "CLAUDE.md").touch()
        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "CLAUDE.md")

    def test_detects_glob_patterns(self):
        """Should detect files matching glob patterns in AutoForge directories.

        Patterns are only matched within .autoforge/, prompts/, and .playwright-mcp/
        to avoid accidentally moving user files like test-myfeature.py at root.
        """
        # Create AutoForge directory structure
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / ".autoforge" / "test-login.json").touch()
        (self.project_dir / ".autoforge" / "test-api.py").touch()
        (self.project_dir / ".autoforge" / "generate-data.py").touch()
        files = detach.get_autoforge_files(self.project_dir)
        # 1 directory + 3 pattern-matched files
        self.assertEqual(len(files), 4)
        names = {f.name for f in files}
        self.assertIn(".autoforge", names)
        self.assertIn("test-login.json", names)
        self.assertIn("test-api.py", names)
        self.assertIn("generate-data.py", names)

    def test_detects_sqlite_wal_files(self):
        """Should detect SQLite WAL companion files."""
        (self.project_dir / "features.db").touch()
        (self.project_dir / "features.db-shm").write_bytes(b"\x00" * 32768)
        (self.project_dir / "features.db-wal").touch()
        (self.project_dir / "assistant.db").touch()
        (self.project_dir / "assistant.db-shm").write_bytes(b"\x00" * 32768)
        (self.project_dir / "assistant.db-wal").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("features.db", names)
        self.assertIn("features.db-shm", names)
        self.assertIn("features.db-wal", names)
        self.assertIn("assistant.db", names)
        self.assertIn("assistant.db-shm", names)
        self.assertIn("assistant.db-wal", names)
        self.assertEqual(len(files), 6)

    def test_detects_sql_test_files(self):
        """Should detect test-*.sql files in AutoForge directories."""
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "prompts" / "test-feature153-create-page.sql").touch()
        (self.project_dir / "prompts" / "test-database-migration.sql").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("prompts", names)
        self.assertIn("test-feature153-create-page.sql", names)
        self.assertIn("test-database-migration.sql", names)
        self.assertEqual(len(files), 3)  # 1 directory + 2 files

    def test_detects_php_test_files(self):
        """Should detect test-*.php files in AutoForge directories."""
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / ".autoforge" / "test-feature28-create-page.php").touch()
        (self.project_dir / ".autoforge" / "test-api-endpoint.php").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn(".autoforge", names)
        self.assertIn("test-feature28-create-page.php", names)
        self.assertIn("test-api-endpoint.php", names)
        self.assertEqual(len(files), 3)  # 1 directory + 2 files

    def test_detects_test_helper_php_files(self):
        """Should detect create-*-test*.php helper scripts in AutoForge directories."""
        (self.project_dir / ".playwright-mcp").mkdir()
        (self.project_dir / ".playwright-mcp" / "create-xss-direct-test.php").touch()
        (self.project_dir / ".playwright-mcp" / "create-xss-test-page.php").touch()
        (self.project_dir / ".playwright-mcp" / "create-csrf-test.php").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn(".playwright-mcp", names)
        self.assertIn("create-xss-direct-test.php", names)
        self.assertIn("create-xss-test-page.php", names)
        self.assertIn("create-csrf-test.php", names)
        self.assertEqual(len(files), 4)  # 1 directory + 3 files

    def test_detects_rollback_json_files(self):
        """Should detect rollback-*.json files in AutoForge directories."""
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "prompts" / "rollback-test-translated.json").touch()
        (self.project_dir / "prompts" / "rollback-migration-v2.json").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("prompts", names)
        self.assertIn("rollback-test-translated.json", names)
        self.assertIn("rollback-migration-v2.json", names)
        self.assertEqual(len(files), 3)  # 1 directory + 2 files

    def test_does_not_capture_user_files_at_root(self):
        """Should NOT capture generic user files matching patterns if at project root.

        This prevents accidentally moving user files like test-myfeature.py.
        Generic patterns are only applied within AutoForge-owned directories.
        More specific patterns (test-feature*.py) are allowed at root.
        """
        # User files at project root - should NOT be captured
        (self.project_dir / "test-myfeature.py").touch()
        (self.project_dir / "test-user-data.json").touch()

        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 0)
        names = {f.name for f in files}
        self.assertNotIn("test-myfeature.py", names)
        self.assertNotIn("test-user-data.json", names)

    def test_detects_feature_test_files_at_root(self):
        """Should detect test-feature*.py files at project root.

        These are agent-generated feature test files that should be moved.
        """
        (self.project_dir / "test-feature184-missing-config.py").touch()
        (self.project_dir / "test-feature182-log-archiving.py").touch()
        (self.project_dir / "test-feature100-basic.json").touch()

        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("test-feature184-missing-config.py", names)
        self.assertIn("test-feature182-log-archiving.py", names)
        self.assertIn("test-feature100-basic.json", names)
        self.assertEqual(len(files), 3)

    def test_detects_generate_files_at_root(self):
        """Should detect generate-*.py files at project root."""
        (self.project_dir / "generate-100items.py").touch()
        (self.project_dir / "generate-test-data.py").touch()

        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("generate-100items.py", names)
        self.assertIn("generate-test-data.py", names)
        self.assertEqual(len(files), 2)

    def test_detects_mark_feature_files_at_root(self):
        """Should detect mark_feature*.py files at project root."""
        (self.project_dir / "mark_feature123.py").touch()
        (self.project_dir / "mark_feature_passing.py").touch()

        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("mark_feature123.py", names)
        self.assertIn("mark_feature_passing.py", names)
        self.assertEqual(len(files), 2)

    def test_detects_rollback_json_at_root(self):
        """Should detect rollback-*.json files at project root."""
        (self.project_dir / "rollback-test-translated.json").touch()
        (self.project_dir / "rollback-migration.json").touch()

        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("rollback-test-translated.json", names)
        self.assertIn("rollback-migration.json", names)
        self.assertEqual(len(files), 2)

    def test_detects_create_test_php_at_root(self):
        """Should detect create-*-test*.php files at project root."""
        (self.project_dir / "create-xss-test.php").touch()
        (self.project_dir / "create-csrf-test-page.php").touch()

        files = detach.get_autoforge_files(self.project_dir)
        names = {f.name for f in files}
        self.assertIn("create-xss-test.php", names)
        self.assertIn("create-csrf-test-page.php", names)
        self.assertEqual(len(files), 2)

    def test_excludes_artifacts_when_disabled(self):
        """Should exclude .playwright-mcp when include_artifacts=False."""
        (self.project_dir / ".playwright-mcp").mkdir()
        (self.project_dir / "features.db").touch()

        # With artifacts
        files_with = detach.get_autoforge_files(self.project_dir, include_artifacts=True)
        names_with = {f.name for f in files_with}
        self.assertIn(".playwright-mcp", names_with)

        # Without artifacts
        files_without = detach.get_autoforge_files(self.project_dir, include_artifacts=False)
        names_without = {f.name for f in files_without}
        self.assertNotIn(".playwright-mcp", names_without)
        self.assertIn("features.db", names_without)

    def test_returns_empty_for_non_autoforge_project(self):
        """Should return empty list for projects without AutoForge files."""
        (self.project_dir / "src").mkdir()
        (self.project_dir / "package.json").touch()
        files = detach.get_autoforge_files(self.project_dir)
        self.assertEqual(len(files), 0)

    def test_returns_sorted_results(self):
        """Should return files sorted by name."""
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / "features.db").touch()
        files = detach.get_autoforge_files(self.project_dir)
        names = [f.name for f in files]
        self.assertEqual(names, sorted(names))


class TestBackupCreation(unittest.TestCase):
    """Tests for create_backup function."""

    def setUp(self):
        """Create temporary project with AutoForge files."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create AutoForge files
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / ".autoforge" / "config.yaml").write_text("test: true")
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "prompts" / "app_spec.txt").write_text("spec content")
        (self.project_dir / "features.db").write_bytes(b"SQLite database")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_creates_backup_directory(self):
        """Should create .autoforge-backup directory."""
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

        backup_dir = self.project_dir / detach.BACKUP_DIR
        self.assertTrue(backup_dir.exists())

    def test_moves_files_to_backup(self):
        """Should move all files to backup directory."""
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

        backup_dir = self.project_dir / detach.BACKUP_DIR

        # Original locations should be gone
        self.assertFalse((self.project_dir / ".autoforge").exists())
        self.assertFalse((self.project_dir / "prompts").exists())
        self.assertFalse((self.project_dir / "features.db").exists())

        # Backup locations should exist
        self.assertTrue((backup_dir / ".autoforge").exists())
        self.assertTrue((backup_dir / "prompts").exists())
        self.assertTrue((backup_dir / "features.db").exists())

    def test_creates_manifest(self):
        """Should create manifest.json with correct structure."""
        files = detach.get_autoforge_files(self.project_dir)
        manifest = detach.create_backup(self.project_dir, "test-project", files)

        # Check manifest structure
        self.assertEqual(manifest["version"], detach.MANIFEST_VERSION)
        self.assertEqual(manifest["project_name"], "test-project")
        self.assertIn("detached_at", manifest)
        self.assertIn("files", manifest)
        self.assertIn("total_size_bytes", manifest)
        self.assertIn("file_count", manifest)

        # Check manifest file exists
        manifest_path = self.project_dir / detach.BACKUP_DIR / detach.MANIFEST_FILE
        self.assertTrue(manifest_path.exists())

    def test_manifest_contains_checksums(self):
        """Should include checksums for files."""
        files = detach.get_autoforge_files(self.project_dir)
        manifest = detach.create_backup(self.project_dir, "test-project", files)

        for entry in manifest["files"]:
            if entry["type"] == "file":
                self.assertIsNotNone(entry["checksum"])
            else:
                self.assertIsNone(entry["checksum"])

    def test_dry_run_does_not_move_files(self):
        """Dry run should not move files or create backup."""
        files = detach.get_autoforge_files(self.project_dir)
        manifest = detach.create_backup(self.project_dir, "test-project", files, dry_run=True)

        # Original files should still exist
        self.assertTrue((self.project_dir / ".autoforge").exists())
        self.assertTrue((self.project_dir / "prompts").exists())
        self.assertTrue((self.project_dir / "features.db").exists())

        # Backup should not exist
        backup_dir = self.project_dir / detach.BACKUP_DIR
        self.assertFalse(backup_dir.exists())

        # Manifest should still be returned
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["project_name"], "test-project")


class TestBackupRestore(unittest.TestCase):
    """Tests for restore_backup function."""

    def setUp(self):
        """Create temporary project with backup."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create AutoForge files and backup them
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / ".autoforge" / "config.yaml").write_text("test: true")
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "prompts" / "app_spec.txt").write_text("spec content")
        (self.project_dir / "features.db").write_bytes(b"SQLite database")

        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_restores_files_from_backup(self):
        """Should restore all files from backup."""
        success, files_restored, conflicts = detach.restore_backup(self.project_dir)

        self.assertTrue(success)
        self.assertEqual(files_restored, 3)  # .autoforge, prompts, features.db
        self.assertEqual(conflicts, [])  # No conflicts expected

        # Files should be restored
        self.assertTrue((self.project_dir / ".autoforge").exists())
        self.assertTrue((self.project_dir / "prompts").exists())
        self.assertTrue((self.project_dir / "features.db").exists())

    def test_removes_backup_after_restore(self):
        """Should remove backup directory after successful restore."""
        detach.restore_backup(self.project_dir)

        backup_dir = self.project_dir / detach.BACKUP_DIR
        self.assertFalse(backup_dir.exists())

    def test_restores_file_contents(self):
        """Should restore correct file contents."""
        detach.restore_backup(self.project_dir)

        config_content = (self.project_dir / ".autoforge" / "config.yaml").read_text()
        self.assertEqual(config_content, "test: true")

        spec_content = (self.project_dir / "prompts" / "app_spec.txt").read_text()
        self.assertEqual(spec_content, "spec content")

    def test_fails_without_backup(self):
        """Should fail gracefully if no backup exists."""
        # Remove backup
        shutil.rmtree(self.project_dir / detach.BACKUP_DIR)

        success, files_restored, conflicts = detach.restore_backup(self.project_dir)
        self.assertFalse(success)
        self.assertEqual(files_restored, 0)
        self.assertEqual(conflicts, [])

    def test_partial_restore_removes_manifest(self):
        """Partial restore should remove manifest to allow re-detach."""
        # Remove one backup file to simulate partial restore
        backup_dir = self.project_dir / detach.BACKUP_DIR
        (backup_dir / "features.db").unlink()

        success, files_restored, conflicts = detach.restore_backup(self.project_dir)

        # Should fail (partial restore)
        self.assertFalse(success)
        # Manifest should be removed to allow re-detach
        self.assertFalse((backup_dir / detach.MANIFEST_FILE).exists())
        # Backup directory should still exist (preserving remaining files)
        self.assertTrue(backup_dir.exists())


class TestDetachStatus(unittest.TestCase):
    """Tests for status checking functions."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_is_project_detached_false(self):
        """Should return False for non-detached project."""
        (self.project_dir / "features.db").touch()
        self.assertFalse(detach.is_project_detached(self.project_dir))

    def test_is_project_detached_true(self):
        """Should return True for detached project."""
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")
        self.assertTrue(detach.is_project_detached(self.project_dir))

    def test_has_backup(self):
        """Should correctly detect backup existence."""
        self.assertFalse(detach.has_backup(self.project_dir))

        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        self.assertTrue(detach.has_backup(self.project_dir))

    def test_get_backup_info(self):
        """Should return manifest info when backup exists."""
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()

        manifest = {
            "version": 1,
            "project_name": "test",
            "total_size_bytes": 1000,
            "file_count": 5,
        }
        (backup_dir / detach.MANIFEST_FILE).write_text(json.dumps(manifest))

        info = detach.get_backup_info(self.project_dir)
        self.assertIsNotNone(info)
        self.assertEqual(info["project_name"], "test")
        self.assertEqual(info["total_size_bytes"], 1000)

    def test_get_backup_info_returns_none_without_backup(self):
        """Should return None when no backup exists."""
        info = detach.get_backup_info(self.project_dir)
        self.assertIsNone(info)

    @patch('detach.get_project_path')
    def test_get_detach_status_reports_state(self, mock_get_path):
        """Should report state field in detach status."""
        mock_get_path.return_value = self.project_dir

        # Attached state
        (self.project_dir / "features.db").touch()
        status = detach.get_detach_status("test-project")
        self.assertEqual(status["state"], "attached")
        self.assertFalse(status["is_detached"])
        self.assertFalse(status["is_inconsistent"])
        self.assertEqual(status["files_at_root"], 1)

    @patch('detach.get_project_path')
    def test_get_detach_status_reports_inconsistent(self, mock_get_path):
        """Should report inconsistent state in detach status."""
        mock_get_path.return_value = self.project_dir

        # Create both files at root AND backup manifest
        (self.project_dir / "features.db").touch()
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        status = detach.get_detach_status("test-project")
        self.assertEqual(status["state"], "inconsistent")
        self.assertFalse(status["is_detached"])
        self.assertTrue(status["is_inconsistent"])
        self.assertEqual(status["files_at_root"], 1)
        self.assertTrue(status["backup_exists"])


class TestProjectDetachState(unittest.TestCase):
    """Tests for get_project_detach_state function."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_state_clean_no_files_no_manifest(self):
        """Should return 'clean' when no files and no manifest."""
        state, files = detach.get_project_detach_state(self.project_dir)
        self.assertEqual(state, "clean")
        self.assertEqual(files, [])

    def test_state_attached_files_present(self):
        """Should return 'attached' when files present, no manifest."""
        (self.project_dir / "features.db").touch()
        (self.project_dir / ".autoforge").mkdir()

        state, files = detach.get_project_detach_state(self.project_dir)
        self.assertEqual(state, "attached")
        self.assertEqual(len(files), 2)

    def test_state_detached_manifest_only(self):
        """Should return 'detached' when manifest exists, no files at root."""
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        state, files = detach.get_project_detach_state(self.project_dir)
        self.assertEqual(state, "detached")
        self.assertEqual(files, [])

    def test_state_inconsistent_both_exist(self):
        """Should return 'inconsistent' when both manifest and files exist."""
        # Create backup with manifest
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        # Also create files at root (simulating partial reattach)
        (self.project_dir / "features.db").touch()
        (self.project_dir / ".autoforge").mkdir()

        state, files = detach.get_project_detach_state(self.project_dir)
        self.assertEqual(state, "inconsistent")
        self.assertEqual(len(files), 2)


class TestDetachProject(unittest.TestCase):
    """Tests for detach_project function."""

    def setUp(self):
        """Create temporary project with AutoForge files."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create AutoForge files
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / "features.db").touch()
        (self.project_dir / "prompts").mkdir()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    @patch('detach.get_project_path')
    def test_detach_by_path(self, mock_get_path):
        """Should detach project by path."""
        mock_get_path.return_value = None

        success, message, manifest, user_files_restored = detach.detach_project(str(self.project_dir))

        self.assertTrue(success)
        self.assertIn("files", message)
        self.assertIsNotNone(manifest)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_detach_by_name(self, mock_get_path):
        """Should detach project by registry name."""
        mock_get_path.return_value = self.project_dir

        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertTrue(success)
        self.assertIsNotNone(manifest)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_fails_if_already_detached(self, mock_get_path):
        """Should fail if project is already detached (clean detach state)."""
        mock_get_path.return_value = self.project_dir

        # Remove AutoForge files from root to simulate clean detach
        shutil.rmtree(self.project_dir / ".autoforge")
        (self.project_dir / "features.db").unlink()
        shutil.rmtree(self.project_dir / "prompts")

        # Create backup (simulating files moved to backup)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertFalse(success)
        self.assertIn("already detached", message)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_fails_if_agent_running(self, mock_get_path):
        """Should fail if agent is running (lock file exists)."""
        mock_get_path.return_value = self.project_dir

        # Create agent lock
        (self.project_dir / ".agent.lock").touch()

        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertFalse(success)
        self.assertIn("Agent is currently running", message)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_force_bypasses_agent_check(self, mock_get_path):
        """Should bypass agent check with force=True."""
        mock_get_path.return_value = self.project_dir

        # Create agent lock
        (self.project_dir / ".agent.lock").touch()

        success, message, manifest, user_files_restored = detach.detach_project("test-project", force=True)

        self.assertTrue(success)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_fails_if_no_autoforge_files(self, mock_get_path):
        """Should fail if no AutoForge files found."""
        # Remove AutoForge files
        shutil.rmtree(self.project_dir / ".autoforge")
        (self.project_dir / "features.db").unlink()
        shutil.rmtree(self.project_dir / "prompts")

        mock_get_path.return_value = self.project_dir

        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertFalse(success)
        self.assertIn("No AutoForge files found", message)
        self.assertEqual(user_files_restored, 0)

    @patch('detach.get_project_path')
    def test_fails_on_inconsistent_state_without_force(self, mock_get_path):
        """Should fail on inconsistent state without --force."""
        mock_get_path.return_value = self.project_dir

        # Create backup with manifest (simulating previous partial reattach)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        # AutoForge files also exist at root
        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertFalse(success)
        self.assertIn("Inconsistent state", message)
        self.assertIn("--force", message)

    @patch('detach.get_project_path')
    def test_force_cleans_inconsistent_state(self, mock_get_path):
        """Should clean up old backup with --force on inconsistent state."""
        mock_get_path.return_value = self.project_dir

        # Create backup with manifest (simulating previous partial reattach)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")
        (backup_dir / "old_features.db").write_bytes(b"old backup content")

        # AutoForge files also exist at root (from partial reattach)
        success, message, manifest, user_files_restored = detach.detach_project(
            "test-project", force=True
        )

        self.assertTrue(success)
        self.assertIn("files", message)
        # New backup should be created with fresh data
        self.assertTrue((backup_dir / detach.MANIFEST_FILE).exists())

    @patch('detach.get_project_path')
    def test_cleans_orphaned_backup_directory(self, mock_get_path):
        """Detach should clean up orphaned backup directory (no manifest).

        This can happen after partial reattach removes manifest but keeps
        backup files due to restore failures.
        """
        mock_get_path.return_value = self.project_dir

        # Create orphaned backup directory (simulates partial reattach)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / ".autoforge").mkdir()
        (backup_dir / "old_features.db").write_bytes(b"orphaned backup content")
        # NO manifest.json - this is the orphaned state

        # Detach should succeed and clean up orphaned backup first
        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertTrue(success)
        self.assertIn("files", message)

        # Verify features.db moved to backup (not orphaned old backup)
        self.assertFalse((self.project_dir / "features.db").exists())
        self.assertTrue((backup_dir / "features.db").exists())

        # Verify orphaned files were cleaned up and replaced with new backup
        self.assertFalse((backup_dir / "old_features.db").exists())
        self.assertTrue((backup_dir / detach.MANIFEST_FILE).exists())


class TestReattachProject(unittest.TestCase):
    """Tests for reattach_project function."""

    def setUp(self):
        """Create temporary project with backup."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create and backup AutoForge files
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / "features.db").write_bytes(b"test")

        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    @patch('detach.get_project_path')
    def test_reattach_restores_files(self, mock_get_path):
        """Should restore files from backup."""
        mock_get_path.return_value = self.project_dir

        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertTrue(success)
        self.assertGreater(files_restored, 0)
        self.assertEqual(conflicts, [])
        self.assertTrue((self.project_dir / ".autoforge").exists())
        self.assertTrue((self.project_dir / "features.db").exists())

    @patch('detach.get_project_path')
    def test_reattach_fails_without_backup(self, mock_get_path):
        """Should fail if no backup exists."""
        mock_get_path.return_value = self.project_dir

        # Remove backup
        shutil.rmtree(self.project_dir / detach.BACKUP_DIR)

        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertFalse(success)
        self.assertIn("No backup found", message)
        self.assertEqual(conflicts, [])

    @patch('detach.get_project_path')
    def test_reattach_fails_when_agent_running(self, mock_get_path):
        """Should fail if agent lock exists."""
        mock_get_path.return_value = self.project_dir

        # Create agent lock file
        (self.project_dir / ".agent.lock").touch()

        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertFalse(success)
        self.assertIn("Agent is currently running", message)
        self.assertEqual(files_restored, 0)
        self.assertEqual(conflicts, [])

    @patch('detach.get_project_path')
    def test_reattach_fails_when_already_attached(self, mock_get_path):
        """Should fail if project is already attached (no backup, files at root)."""
        mock_get_path.return_value = self.project_dir

        # Remove backup but keep files at root
        shutil.rmtree(self.project_dir / detach.BACKUP_DIR)
        (self.project_dir / "features.db").write_bytes(b"test")
        (self.project_dir / ".autoforge").mkdir()

        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertFalse(success)
        self.assertIn("already attached", message)
        self.assertEqual(files_restored, 0)
        self.assertEqual(conflicts, [])

    @patch('detach.get_project_path')
    def test_reattach_handles_inconsistent_state_by_restoring(self, mock_get_path):
        """Should restore from backup even if some files exist at root (user-created).

        This handles the case where user creates files while detached.
        The conflicting files get backed up to .pre-reattach-backup/ before restore.
        """
        mock_get_path.return_value = self.project_dir

        # Backup exists from setUp (with features.db and .autoforge in backup)
        # Add files at root too (simulates user creating files while detached)
        (self.project_dir / "features.db").write_bytes(b"user-created")
        (self.project_dir / ".autoforge").mkdir()

        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        # Should succeed - user files get backed up, autoforge files restored
        self.assertTrue(success)
        self.assertIn("features.db", conflicts)  # User file was backed up
        self.assertGreater(files_restored, 0)


class TestGitignoreUpdate(unittest.TestCase):
    """Tests for update_gitignore function."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_creates_gitignore_if_missing(self):
        """Should create .gitignore if it doesn't exist."""
        detach.update_gitignore(self.project_dir)

        gitignore = self.project_dir / ".gitignore"
        self.assertTrue(gitignore.exists())
        content = gitignore.read_text()
        self.assertIn(detach.BACKUP_DIR, content)

    def test_appends_to_existing_gitignore(self):
        """Should append to existing .gitignore."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text("node_modules/\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        self.assertIn("node_modules/", content)
        self.assertIn(detach.BACKUP_DIR, content)

    def test_does_not_duplicate_entry(self):
        """Should not add duplicate entry."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text(f"{detach.BACKUP_DIR}/\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        # Should only appear once
        self.assertEqual(content.count(detach.BACKUP_DIR), 1)


class TestDetachLock(unittest.TestCase):
    """Tests for detach lock functions."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_acquire_lock(self):
        """Should acquire lock successfully."""
        result = detach.acquire_detach_lock(self.project_dir)
        self.assertTrue(result)
        self.assertTrue((self.project_dir / detach.DETACH_LOCK).exists())

    def test_acquire_lock_writes_pid_and_timestamp(self):
        """Should write PID and timestamp to lock file."""
        import os
        detach.acquire_detach_lock(self.project_dir)
        lock_content = json.loads((self.project_dir / detach.DETACH_LOCK).read_text())
        self.assertEqual(lock_content["pid"], os.getpid())
        self.assertIn("timestamp", lock_content)

    def test_acquire_lock_fails_if_locked_by_live_process(self):
        """Should fail to acquire lock if already locked by live process."""
        import os
        # Create lock with current process PID (which is alive)
        lock_data = {"pid": os.getpid(), "timestamp": 9999999999}
        (self.project_dir / detach.DETACH_LOCK).write_text(json.dumps(lock_data))
        result = detach.acquire_detach_lock(self.project_dir)
        self.assertFalse(result)

    def test_acquire_lock_removes_stale_lock_dead_process(self):
        """Should remove stale lock from dead process."""
        # Create lock with non-existent PID
        lock_data = {"pid": 999999999, "timestamp": 9999999999}
        (self.project_dir / detach.DETACH_LOCK).write_text(json.dumps(lock_data))
        result = detach.acquire_detach_lock(self.project_dir)
        self.assertTrue(result)  # Should succeed after removing stale lock

    def test_acquire_lock_removes_corrupted_lock(self):
        """Should remove corrupted lock file."""
        (self.project_dir / detach.DETACH_LOCK).write_text("not valid json")
        result = detach.acquire_detach_lock(self.project_dir)
        self.assertTrue(result)

    def test_release_lock(self):
        """Should release lock successfully."""
        (self.project_dir / detach.DETACH_LOCK).write_text("{}")
        detach.release_detach_lock(self.project_dir)
        self.assertFalse((self.project_dir / detach.DETACH_LOCK).exists())

    def test_release_lock_handles_missing_file(self):
        """Should handle missing lock file gracefully."""
        # Should not raise
        detach.release_detach_lock(self.project_dir)


class TestSecurityPathTraversal(unittest.TestCase):
    """Security tests for path traversal protection."""

    def setUp(self):
        """Create temporary project with backup."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create backup directory
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_restore_blocks_path_traversal(self):
        """Should reject manifest with path traversal attempt."""
        backup_dir = self.project_dir / detach.BACKUP_DIR

        # Create malicious manifest with path traversal
        manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "malicious",
            "autocoder_version": "1.0.0",
            "files": [
                {
                    "path": "../../../etc/passwd",  # Path traversal attempt
                    "type": "file",
                    "size": 100,
                    "checksum": None,
                    "file_count": None,
                }
            ],
            "total_size_bytes": 100,
            "file_count": 1,
        }
        (backup_dir / detach.MANIFEST_FILE).write_text(json.dumps(manifest))

        # Note: We don't need to create the actual malicious file - the validation
        # catches it during path resolution before attempting to access the source file

        success, _, _ = detach.restore_backup(self.project_dir)
        self.assertFalse(success)

    def test_restore_blocks_absolute_path(self):
        """Should reject manifest with absolute path."""
        backup_dir = self.project_dir / detach.BACKUP_DIR

        manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "malicious",
            "autocoder_version": "1.0.0",
            "files": [
                {
                    "path": "/etc/passwd",  # Absolute path
                    "type": "file",
                    "size": 100,
                    "checksum": None,
                    "file_count": None,
                }
            ],
            "total_size_bytes": 100,
            "file_count": 1,
        }
        (backup_dir / detach.MANIFEST_FILE).write_text(json.dumps(manifest))

        success, _, _ = detach.restore_backup(self.project_dir)
        self.assertFalse(success)

    def test_restore_rejects_unsupported_manifest_version(self):
        """Should reject manifest with unsupported version."""
        backup_dir = self.project_dir / detach.BACKUP_DIR

        manifest = {
            "version": 999,  # Future version
            "detached_at": "2024-01-01T00:00:00Z",
            "files": [],
            "total_size_bytes": 0,
            "file_count": 0,
        }
        (backup_dir / detach.MANIFEST_FILE).write_text(json.dumps(manifest))

        success, _, _ = detach.restore_backup(self.project_dir)
        self.assertFalse(success)

    def test_restore_rejects_invalid_manifest_structure(self):
        """Should reject manifest with missing required keys."""
        backup_dir = self.project_dir / detach.BACKUP_DIR

        # Missing required keys
        manifest = {
            "version": 1,
            # missing "files" and "detached_at"
        }
        (backup_dir / detach.MANIFEST_FILE).write_text(json.dumps(manifest))

        success, _, _ = detach.restore_backup(self.project_dir)
        self.assertFalse(success)


class TestGitignoreLineMatching(unittest.TestCase):
    """Tests for gitignore line-based matching."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_does_not_match_comment(self):
        """Should not match backup dir name in comment."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text(f"# Ignore {detach.BACKUP_DIR} directory\nnode_modules/\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        # Should have added the actual entry
        lines = [line.strip() for line in content.splitlines()]
        self.assertIn(f"{detach.BACKUP_DIR}/", lines)

    def test_does_not_match_path_substring(self):
        """Should not match backup dir name as substring of path."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text(f"some/path/{detach.BACKUP_DIR}/other\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        # Should have added the standalone entry
        lines = [line.strip() for line in content.splitlines()]
        self.assertIn(f"{detach.BACKUP_DIR}/", lines)

    def test_matches_exact_entry(self):
        """Should match exact entry and not duplicate."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text(f"{detach.BACKUP_DIR}/\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        # Should only appear once
        self.assertEqual(content.count(f"{detach.BACKUP_DIR}/"), 1)


class TestBackupAtomicity(unittest.TestCase):
    """Tests for atomic backup operations (copy-then-delete)."""

    def setUp(self):
        """Create temporary project with files."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create AutoForge files (only regular files to test copy2)
        (self.project_dir / "features.db").write_bytes(b"database content")
        (self.project_dir / "CLAUDE.md").write_text("# Test")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_backup_preserves_originals_on_copy_failure(self):
        """Should preserve originals if copy fails."""
        files = detach.get_autoforge_files(self.project_dir)

        # Mock shutil.copy2 to fail on second file
        original_copy2 = shutil.copy2
        call_count = [0]

        def failing_copy2(src, dst):
            call_count[0] += 1
            if call_count[0] > 1:
                raise OSError("Simulated copy failure")
            return original_copy2(src, dst)

        with patch('detach.shutil.copy2', side_effect=failing_copy2):
            with self.assertRaises(OSError):
                detach.create_backup(self.project_dir, "test", files)

        # Original files should still exist
        self.assertTrue((self.project_dir / "CLAUDE.md").exists())
        self.assertTrue((self.project_dir / "features.db").exists())

        # Backup directory should be cleaned up
        self.assertFalse((self.project_dir / detach.BACKUP_DIR).exists())


class TestFileConflictDetection(unittest.TestCase):
    """Tests for file conflict detection and backup during reattach."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_detect_conflicts_no_conflicts(self):
        """Should return empty list when no conflicts exist."""
        manifest: detach.Manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "test",
            "autocoder_version": "1.0.0",
            "files": [
                {"path": "CLAUDE.md", "type": "file", "size": 100, "checksum": None, "file_count": None}
            ],
            "total_size_bytes": 100,
            "file_count": 1,
        }
        conflicts = detach.detect_conflicts(self.project_dir, manifest)
        self.assertEqual(conflicts, [])

    def test_detect_conflicts_with_file(self):
        """Should detect conflicting file."""
        (self.project_dir / "CLAUDE.md").write_text("User content")

        manifest: detach.Manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "test",
            "autocoder_version": "1.0.0",
            "files": [
                {"path": "CLAUDE.md", "type": "file", "size": 100, "checksum": None, "file_count": None}
            ],
            "total_size_bytes": 100,
            "file_count": 1,
        }
        conflicts = detach.detect_conflicts(self.project_dir, manifest)
        self.assertEqual(conflicts, ["CLAUDE.md"])

    def test_detect_conflicts_with_directory(self):
        """Should detect conflicting directory."""
        (self.project_dir / "prompts").mkdir()
        (self.project_dir / "prompts" / "user_file.txt").write_text("User file")

        manifest: detach.Manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "test",
            "autocoder_version": "1.0.0",
            "files": [
                {"path": "prompts", "type": "directory", "size": 100, "checksum": None, "file_count": 1}
            ],
            "total_size_bytes": 100,
            "file_count": 1,
        }
        conflicts = detach.detect_conflicts(self.project_dir, manifest)
        self.assertEqual(conflicts, ["prompts"])

    def test_backup_conflicts_creates_backup(self):
        """Should backup conflicting files to pre-reattach-backup dir."""
        (self.project_dir / "CLAUDE.md").write_text("User content")
        conflicts = ["CLAUDE.md"]

        backup_path = detach.backup_conflicts(self.project_dir, conflicts)

        self.assertEqual(backup_path, self.project_dir / detach.PRE_REATTACH_BACKUP_DIR)
        self.assertTrue((backup_path / "CLAUDE.md").exists())
        self.assertEqual((backup_path / "CLAUDE.md").read_text(), "User content")

    @patch('detach.get_project_path')
    def test_reattach_with_conflicts_preserves_new_files(self, mock_get_path):
        """Should backup user files when they conflict with autoforge files."""
        mock_get_path.return_value = self.project_dir

        # Create AutoForge files and backup them
        (self.project_dir / "CLAUDE.md").write_text("AutoForge content")
        (self.project_dir / "features.db").write_bytes(b"test")
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

        # Simulate user creating CLAUDE.md while detached
        (self.project_dir / "CLAUDE.md").write_text("User content after /init")

        # Reattach
        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertTrue(success)
        self.assertEqual(conflicts, ["CLAUDE.md"])
        self.assertIn("user files saved", message)

        # AutoForge content restored
        self.assertEqual((self.project_dir / "CLAUDE.md").read_text(), "AutoForge content")

        # User content backed up
        backup_path = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        self.assertTrue(backup_path.exists())
        self.assertEqual((backup_path / "CLAUDE.md").read_text(), "User content after /init")

    @patch('detach.get_project_path')
    def test_reattach_no_conflicts_no_backup(self, mock_get_path):
        """Should not create backup directory when no conflicts exist."""
        mock_get_path.return_value = self.project_dir

        # Create AutoForge files and backup them
        (self.project_dir / "CLAUDE.md").write_text("AutoForge content")
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

        # No user files created (no conflict)

        # Reattach
        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertTrue(success)
        self.assertEqual(conflicts, [])
        self.assertNotIn("user files", message)

        # No pre-reattach backup should exist
        backup_path = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        self.assertFalse(backup_path.exists())

    def test_restore_pre_reattach_backup(self):
        """Should restore user files from pre-reattach backup."""
        # Create pre-reattach backup
        backup_dir = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / "CLAUDE.md").write_text("User content")
        (backup_dir / "nested").mkdir()
        (backup_dir / "nested" / "file.txt").write_text("Nested user file")

        # Restore
        files_restored = detach.restore_pre_reattach_backup(self.project_dir)

        self.assertEqual(files_restored, 2)
        self.assertEqual((self.project_dir / "CLAUDE.md").read_text(), "User content")
        self.assertEqual((self.project_dir / "nested" / "file.txt").read_text(), "Nested user file")

        # Backup directory should be removed
        self.assertFalse(backup_dir.exists())

    def test_restore_pre_reattach_backup_path_traversal(self):
        """Should skip files with path traversal in pre-reattach backup."""
        backup_dir = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        backup_dir.mkdir()

        # Create a normal file
        (backup_dir / "safe.txt").write_text("Safe content")

        # Note: Path traversal protection is tested by the restore function
        # which validates each path before restoring. We can't easily create
        # a malicious backup file, but the validation logic ensures safety.

        # Restore should only restore safe.txt
        files_restored = detach.restore_pre_reattach_backup(self.project_dir)
        self.assertEqual(files_restored, 1)
        self.assertEqual((self.project_dir / "safe.txt").read_text(), "Safe content")

    @patch('detach.get_project_path')
    def test_detach_restores_user_files(self, mock_get_path):
        """Should restore user files from pre-reattach backup on detach."""
        mock_get_path.return_value = self.project_dir

        # Create pre-reattach backup (from previous reattach)
        backup_dir = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / "CLAUDE.md").write_text("User content from previous session")

        # Create AutoForge files
        (self.project_dir / ".autoforge").mkdir()
        (self.project_dir / "features.db").touch()

        # Detach
        success, message, manifest, user_files_restored = detach.detach_project("test-project")

        self.assertTrue(success)
        self.assertEqual(user_files_restored, 1)
        self.assertIn("restored 1 user files", message)

        # User file restored
        self.assertEqual((self.project_dir / "CLAUDE.md").read_text(), "User content from previous session")

        # Pre-reattach backup cleaned up
        self.assertFalse(backup_dir.exists())

    @patch('detach.get_project_path')
    def test_full_cycle_preserves_both_files(self, mock_get_path):
        """Full cycle: detach -> create user file -> reattach -> detach preserves both."""
        mock_get_path.return_value = self.project_dir

        # Initial state: AutoForge files
        (self.project_dir / "CLAUDE.md").write_text("AutoForge CLAUDE.md")
        (self.project_dir / "features.db").touch()

        # Step 1: Detach
        success, msg, manifest, user_restored = detach.detach_project("test-project")
        self.assertTrue(success)
        self.assertEqual(user_restored, 0)  # No user files to restore initially

        # Step 2: User creates their own CLAUDE.md (e.g., via /init)
        (self.project_dir / "CLAUDE.md").write_text("User CLAUDE.md from /init")

        # Step 3: Reattach
        success, msg, files_restored, conflicts = detach.reattach_project("test-project")
        self.assertTrue(success)
        self.assertEqual(conflicts, ["CLAUDE.md"])  # User file was backed up

        # AutoForge content restored
        self.assertEqual((self.project_dir / "CLAUDE.md").read_text(), "AutoForge CLAUDE.md")

        # User content in pre-reattach backup
        self.assertEqual(
            (self.project_dir / detach.PRE_REATTACH_BACKUP_DIR / "CLAUDE.md").read_text(),
            "User CLAUDE.md from /init"
        )

        # Step 4: Detach again
        success, msg, manifest, user_restored = detach.detach_project("test-project")
        self.assertTrue(success)
        self.assertEqual(user_restored, 1)  # User file restored

        # User content back in place
        self.assertEqual((self.project_dir / "CLAUDE.md").read_text(), "User CLAUDE.md from /init")

        # Pre-reattach backup cleaned up
        self.assertFalse((self.project_dir / detach.PRE_REATTACH_BACKUP_DIR).exists())

        # Verify features.db is in backup, not in project root (main bug fix verification)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        self.assertFalse((self.project_dir / "features.db").exists())
        self.assertTrue((backup_dir / "features.db").exists())

    @patch('detach.get_project_path')
    def test_reattach_merges_existing_pre_reattach_backup(self, mock_get_path):
        """Should merge new conflicts with existing pre-reattach backup."""
        mock_get_path.return_value = self.project_dir

        # Create existing pre-reattach backup
        backup_dir = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / "old_user_file.txt").write_text("Old user file")

        # Create AutoForge files and backup
        (self.project_dir / "CLAUDE.md").write_text("AutoForge CLAUDE.md")
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test", files)

        # User creates new CLAUDE.md
        (self.project_dir / "CLAUDE.md").write_text("New user CLAUDE.md")

        # Reattach - should merge, not overwrite
        success, msg, files_restored, conflicts = detach.reattach_project("test")
        self.assertTrue(success)
        self.assertEqual(conflicts, ["CLAUDE.md"])

        # Both files should exist in backup
        self.assertEqual((backup_dir / "old_user_file.txt").read_text(), "Old user file")
        self.assertEqual((backup_dir / "CLAUDE.md").read_text(), "New user CLAUDE.md")

    def test_backup_conflicts_does_not_overwrite_existing(self):
        """Backup should not overwrite existing files (merge mode)."""
        # Create pre-reattach backup with existing file
        backup_dir = self.project_dir / detach.PRE_REATTACH_BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / "CLAUDE.md").write_text("Original backup")

        # Create conflicting file
        (self.project_dir / "CLAUDE.md").write_text("New content")

        # Backup conflicts
        detach.backup_conflicts(self.project_dir, ["CLAUDE.md"])

        # Original backup should be preserved
        self.assertEqual((backup_dir / "CLAUDE.md").read_text(), "Original backup")


class TestGitignorePreReattachBackup(unittest.TestCase):
    """Tests for .pre-reattach-backup/ in .gitignore."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_gitignore_includes_both_backup_dirs(self):
        """Should add both backup directories to .gitignore."""
        detach.update_gitignore(self.project_dir)

        gitignore = self.project_dir / ".gitignore"
        content = gitignore.read_text()
        lines = content.splitlines()

        # Both patterns should be present as standalone lines
        self.assertTrue(any(line.strip() == f"{detach.BACKUP_DIR}/" for line in lines))
        self.assertTrue(any(line.strip() == f"{detach.PRE_REATTACH_BACKUP_DIR}/" for line in lines))

    def test_gitignore_appends_missing_patterns(self):
        """Should append only missing patterns to existing .gitignore."""
        gitignore = self.project_dir / ".gitignore"
        gitignore.write_text(f"{detach.BACKUP_DIR}/\n")

        detach.update_gitignore(self.project_dir)

        content = gitignore.read_text()
        # BACKUP_DIR should appear once, PRE_REATTACH_BACKUP_DIR should be added
        self.assertEqual(content.count(f"{detach.BACKUP_DIR}/"), 1)
        self.assertIn(f"{detach.PRE_REATTACH_BACKUP_DIR}/", content)


class TestOrphanedDbCleanup(unittest.TestCase):
    """Tests for orphaned database file cleanup during reattach."""

    def setUp(self):
        """Create temporary project with backup."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create AutoForge files with realistic database
        (self.project_dir / ".autoforge").mkdir()
        # Create a features.db that's larger than an empty one (simulate real data)
        (self.project_dir / "features.db").write_bytes(b"x" * 120000)  # 120KB - realistic size
        (self.project_dir / "features.db-wal").write_bytes(b"wal")
        (self.project_dir / "features.db-shm").write_bytes(b"shm")

        # Create backup
        files = detach.get_autoforge_files(self.project_dir)
        detach.create_backup(self.project_dir, "test-project", files)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    @patch('detach.get_project_path')
    def test_cleanup_removes_recreated_small_db(self, mock_get_path):
        """Should remove recreated empty database before restore."""
        mock_get_path.return_value = self.project_dir

        # Simulate API recreating empty features.db after detach
        (self.project_dir / "features.db").write_bytes(b"x" * 4096)  # 4KB - empty SQLite

        # Reattach should clean up the small file and restore the large one
        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertTrue(success)
        # The restored file should be the large one from backup
        restored_size = (self.project_dir / "features.db").stat().st_size
        self.assertEqual(restored_size, 120000)

    @patch('detach.get_project_path')
    def test_cleanup_removes_orphan_wal_files(self, mock_get_path):
        """Should remove orphaned WAL/SHM files before restore."""
        mock_get_path.return_value = self.project_dir

        # Simulate orphaned WAL files created by API
        (self.project_dir / "features.db-wal").write_bytes(b"orphan wal")
        (self.project_dir / "features.db-shm").write_bytes(b"orphan shm")
        (self.project_dir / "assistant.db-wal").write_bytes(b"orphan wal")

        # Reattach should clean up and restore
        success, message, files_restored, conflicts = detach.reattach_project("test-project")

        self.assertTrue(success)
        # WAL files should be from backup (or not exist if not in backup)
        # In this case they were in original, so should be restored
        self.assertTrue((self.project_dir / "features.db-wal").exists())

    def test_cleanup_helper_function_directly(self):
        """Test _cleanup_orphaned_db_files directly."""
        # Create manifest
        manifest: detach.Manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "test",
            "autocoder_version": "1.0.0",
            "files": [
                {"path": "features.db", "type": "file", "size": 120000, "checksum": "abc", "file_count": None}
            ],
            "total_size_bytes": 120000,
            "file_count": 1,
        }

        # Create small recreated file at root
        (self.project_dir / "features.db").write_bytes(b"x" * 4096)
        (self.project_dir / "features.db-wal").write_bytes(b"wal")

        # Run cleanup
        cleaned = detach._cleanup_orphaned_db_files(self.project_dir, manifest)

        # Both should be cleaned
        self.assertIn("features.db", cleaned)
        self.assertIn("features.db-wal", cleaned)
        self.assertFalse((self.project_dir / "features.db").exists())
        self.assertFalse((self.project_dir / "features.db-wal").exists())

    def test_cleanup_preserves_large_user_db(self):
        """Should NOT remove database if it's larger than backup (user modifications)."""
        manifest: detach.Manifest = {
            "version": 1,
            "detached_at": "2024-01-01T00:00:00Z",
            "project_name": "test",
            "autocoder_version": "1.0.0",
            "files": [
                {"path": "features.db", "type": "file", "size": 50000, "checksum": "abc", "file_count": None}
            ],
            "total_size_bytes": 50000,
            "file_count": 1,
        }

        # Create larger file at root (user added data)
        (self.project_dir / "features.db").write_bytes(b"x" * 100000)

        # Run cleanup
        cleaned = detach._cleanup_orphaned_db_files(self.project_dir, manifest)

        # features.db should NOT be cleaned (it's larger)
        self.assertNotIn("features.db", cleaned)
        self.assertTrue((self.project_dir / "features.db").exists())


class TestServerDependencies(unittest.TestCase):
    """Tests for server/dependencies.py validation functions."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_validate_project_not_detached_raises_on_detached(self):
        """Should raise HTTPException 409 for detached project."""
        # Import here to avoid issues if server not set up
        try:
            from fastapi import HTTPException

            from server.dependencies import validate_project_not_detached
        except ImportError:
            self.skipTest("Server dependencies not available")

        # Create detached state (backup with manifest)
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        with patch('server.dependencies._get_registry_module') as mock_registry:
            mock_registry.return_value = lambda x: self.project_dir

            with self.assertRaises(HTTPException) as ctx:
                validate_project_not_detached("test-project")

            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("detached", ctx.exception.detail)

    def test_validate_project_not_detached_passes_for_attached(self):
        """Should return project_dir for attached project."""
        try:
            from server.dependencies import validate_project_not_detached
        except ImportError:
            self.skipTest("Server dependencies not available")

        # Create attached state (files at root, no backup)
        (self.project_dir / "features.db").touch()

        with patch('server.dependencies._get_registry_module') as mock_registry:
            mock_registry.return_value = lambda x: self.project_dir

            result = validate_project_not_detached("test-project")
            self.assertEqual(result, self.project_dir)

    def test_check_project_detached_for_background_returns_bool(self):
        """Background check should return bool, not raise."""
        try:
            from server.dependencies import check_project_detached_for_background
        except ImportError:
            self.skipTest("Server dependencies not available")

        # Attached state
        (self.project_dir / "features.db").touch()
        result = check_project_detached_for_background(self.project_dir)
        self.assertFalse(result)

        # Detached state
        backup_dir = self.project_dir / detach.BACKUP_DIR
        backup_dir.mkdir()
        (backup_dir / detach.MANIFEST_FILE).write_text("{}")

        result = check_project_detached_for_background(self.project_dir)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
