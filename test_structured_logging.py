"""
Unit Tests for Structured Logging Module
=========================================

Tests for the structured logging system that saves logs to SQLite.
"""

import json
import sqlite3
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import TestCase

from structured_logging import (
    StructuredLogEntry,
    StructuredLogHandler,
    get_log_query,
    get_logger,
)


class TestStructuredLogEntry(TestCase):
    """Tests for StructuredLogEntry dataclass."""

    def test_to_dict_minimal(self):
        """Test minimal entry conversion."""
        entry = StructuredLogEntry(
            timestamp="2025-01-21T10:30:00.000Z",
            level="info",
            message="Test message",
        )
        result = entry.to_dict()
        self.assertEqual(result["timestamp"], "2025-01-21T10:30:00.000Z")
        self.assertEqual(result["level"], "info")
        self.assertEqual(result["message"], "Test message")
        # Optional fields should not be present when None
        self.assertNotIn("agent_id", result)
        self.assertNotIn("feature_id", result)
        self.assertNotIn("tool_name", result)

    def test_to_dict_full(self):
        """Test full entry with all fields."""
        entry = StructuredLogEntry(
            timestamp="2025-01-21T10:30:00.000Z",
            level="error",
            message="Test error",
            agent_id="coding-42",
            feature_id=42,
            tool_name="playwright",
            duration_ms=150,
            extra={"key": "value"},
        )
        result = entry.to_dict()
        self.assertEqual(result["agent_id"], "coding-42")
        self.assertEqual(result["feature_id"], 42)
        self.assertEqual(result["tool_name"], "playwright")
        self.assertEqual(result["duration_ms"], 150)
        self.assertEqual(result["extra"], {"key": "value"})

    def test_to_json(self):
        """Test JSON serialization."""
        entry = StructuredLogEntry(
            timestamp="2025-01-21T10:30:00.000Z",
            level="info",
            message="Test",
        )
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["message"], "Test")


class TestStructuredLogHandler(TestCase):
    """Tests for StructuredLogHandler."""

    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "logs.db"

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creates_database(self):
        """Test that handler creates database file."""
        _handler = StructuredLogHandler(self.db_path)  # noqa: F841 - handler triggers DB creation
        self.assertTrue(self.db_path.exists())

    def test_creates_tables(self):
        """Test that handler creates logs table."""
        _handler = StructuredLogHandler(self.db_path)  # noqa: F841 - handler triggers table creation
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
        result = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(result)

    def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled for concurrency."""
        _handler = StructuredLogHandler(self.db_path)  # noqa: F841 - handler triggers WAL mode
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(result.lower(), "wal")


class TestStructuredLogger(TestCase):
    """Tests for StructuredLogger."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creates_logs_directory(self):
        """Test that logger creates .autocoder directory."""
        _logger = get_logger(self.project_dir, agent_id="test", console_output=False)  # noqa: F841
        autocoder_dir = self.project_dir / ".autocoder"
        self.assertTrue(autocoder_dir.exists())

    def test_creates_logs_db(self):
        """Test that logger creates logs.db file."""
        _logger = get_logger(self.project_dir, agent_id="test", console_output=False)  # noqa: F841
        db_path = self.project_dir / ".autocoder" / "logs.db"
        self.assertTrue(db_path.exists())

    def test_log_info(self):
        """Test info level logging."""
        logger = get_logger(self.project_dir, agent_id="test-agent", console_output=False)
        logger.info("Test info message", feature_id=42)

        # Query the database
        query = get_log_query(self.project_dir)
        logs = query.query(level="info")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Test info message")
        self.assertEqual(logs[0]["agent_id"], "test-agent")
        self.assertEqual(logs[0]["feature_id"], 42)

    def test_log_warn(self):
        """Test warning level logging."""
        logger = get_logger(self.project_dir, agent_id="test", console_output=False)
        logger.warn("Test warning")

        query = get_log_query(self.project_dir)
        logs = query.query(level="warn")
        self.assertEqual(len(logs), 1)
        # Assert on level field, not message content (more robust)
        self.assertEqual(logs[0]["level"], "warn")

    def test_log_error(self):
        """Test error level logging."""
        logger = get_logger(self.project_dir, agent_id="test", console_output=False)
        logger.error("Test error", tool_name="playwright")

        query = get_log_query(self.project_dir)
        logs = query.query(level="error")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["tool_name"], "playwright")

    def test_log_debug(self):
        """Test debug level logging."""
        logger = get_logger(self.project_dir, agent_id="test", console_output=False)
        logger.debug("Debug message")

        query = get_log_query(self.project_dir)
        logs = query.query(level="debug")
        self.assertEqual(len(logs), 1)

    def test_extra_fields(self):
        """Test that extra fields are stored as JSON."""
        logger = get_logger(self.project_dir, agent_id="test", console_output=False)
        logger.info("Test", custom_field="value", count=42)

        query = get_log_query(self.project_dir)
        logs = query.query()
        self.assertEqual(len(logs), 1)
        extra = json.loads(logs[0]["extra"]) if logs[0]["extra"] else {}
        self.assertEqual(extra.get("custom_field"), "value")
        self.assertEqual(extra.get("count"), 42)


class TestLogQuery(TestCase):
    """Tests for LogQuery."""

    def setUp(self):
        """Create temporary project directory with sample logs."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

        # Create sample logs
        logger = get_logger(self.project_dir, agent_id="coding-1", console_output=False)
        logger.info("Feature started", feature_id=1)
        logger.debug("Tool used", feature_id=1, tool_name="bash")
        logger.error("Test failed", feature_id=1, tool_name="playwright")

        logger2 = get_logger(self.project_dir, agent_id="coding-2", console_output=False)
        logger2.info("Feature started", feature_id=2)
        logger2.info("Feature completed", feature_id=2)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_by_level(self):
        """Test filtering by log level."""
        query = get_log_query(self.project_dir)
        errors = query.query(level="error")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["level"], "error")

    def test_query_by_agent_id(self):
        """Test filtering by agent ID."""
        query = get_log_query(self.project_dir)
        logs = query.query(agent_id="coding-2")
        self.assertEqual(len(logs), 2)
        for log in logs:
            self.assertEqual(log["agent_id"], "coding-2")

    def test_query_by_feature_id(self):
        """Test filtering by feature ID."""
        query = get_log_query(self.project_dir)
        logs = query.query(feature_id=1)
        self.assertEqual(len(logs), 3)
        for log in logs:
            self.assertEqual(log["feature_id"], 1)

    def test_query_by_tool_name(self):
        """Test filtering by tool name."""
        query = get_log_query(self.project_dir)
        logs = query.query(tool_name="playwright")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["tool_name"], "playwright")

    def test_query_full_text_search(self):
        """Test full-text search in messages."""
        query = get_log_query(self.project_dir)
        logs = query.query(search="Feature started")
        self.assertEqual(len(logs), 2)

    def test_query_with_limit(self):
        """Test query with limit."""
        query = get_log_query(self.project_dir)
        logs = query.query(limit=2)
        self.assertEqual(len(logs), 2)

    def test_query_with_offset(self):
        """Test query with offset for pagination."""
        query = get_log_query(self.project_dir)
        all_logs = query.query()
        offset_logs = query.query(offset=2, limit=10)
        self.assertEqual(len(offset_logs), len(all_logs) - 2)

    def test_count(self):
        """Test count method."""
        query = get_log_query(self.project_dir)
        total = query.count()
        self.assertEqual(total, 5)

        error_count = query.count(level="error")
        self.assertEqual(error_count, 1)

    def test_get_agent_stats(self):
        """Test agent statistics."""
        query = get_log_query(self.project_dir)
        stats = query.get_agent_stats()
        self.assertEqual(len(stats), 2)  # coding-1 and coding-2

        # Find coding-1 stats
        coding1_stats = next((s for s in stats if s["agent_id"] == "coding-1"), None)
        self.assertIsNotNone(coding1_stats)
        self.assertEqual(coding1_stats["error_count"], 1)


class TestLogExport(TestCase):
    """Tests for log export functionality."""

    def setUp(self):
        """Create temporary project directory with sample logs."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)
        self.export_dir = Path(self.temp_dir) / "exports"
        self.export_dir.mkdir()

        logger = get_logger(self.project_dir, agent_id="test", console_output=False)
        logger.info("Test log 1")
        logger.info("Test log 2")
        logger.error("Test error")

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_json(self):
        """Test JSON export."""
        query = get_log_query(self.project_dir)
        output_path = self.export_dir / "logs.json"
        count = query.export_logs(output_path, format="json")

        self.assertEqual(count, 3)
        self.assertTrue(output_path.exists())

        with open(output_path) as f:
            data = json.load(f)
        self.assertEqual(len(data), 3)

    def test_export_jsonl(self):
        """Test JSONL export."""
        query = get_log_query(self.project_dir)
        output_path = self.export_dir / "logs.jsonl"
        count = query.export_logs(output_path, format="jsonl")

        self.assertEqual(count, 3)
        self.assertTrue(output_path.exists())

        with open(output_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 3)
        # Verify each line is valid JSON
        for line in lines:
            json.loads(line)

    def test_export_csv(self):
        """Test CSV export."""
        query = get_log_query(self.project_dir)
        output_path = self.export_dir / "logs.csv"
        count = query.export_logs(output_path, format="csv")

        self.assertEqual(count, 3)
        self.assertTrue(output_path.exists())

        import csv
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)


class TestThreadSafety(TestCase):
    """Tests for thread safety of the logging system."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_writes(self):
        """Test that concurrent writes don't cause database corruption."""
        num_threads = 10
        logs_per_thread = 50

        def write_logs(thread_id):
            logger = get_logger(self.project_dir, agent_id=f"thread-{thread_id}", console_output=False)
            for i in range(logs_per_thread):
                logger.info(f"Log {i} from thread {thread_id}", count=i)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_logs, i) for i in range(num_threads)]
            for future in futures:
                future.result()  # Wait for all to complete

        # Verify all logs were written
        query = get_log_query(self.project_dir)
        total = query.count()
        expected = num_threads * logs_per_thread
        self.assertEqual(total, expected)

    def test_concurrent_read_write(self):
        """Test that reads and writes can happen concurrently."""
        logger = get_logger(self.project_dir, agent_id="writer", console_output=False)
        query = get_log_query(self.project_dir)

        # Pre-populate some logs
        for i in range(10):
            logger.info(f"Initial log {i}")

        read_results = []
        write_done = threading.Event()

        def writer():
            for i in range(50):
                logger.info(f"Concurrent log {i}")
            write_done.set()

        def reader():
            while not write_done.is_set():
                count = query.count()
                read_results.append(count)

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)

        writer_thread.start()
        reader_thread.start()

        writer_thread.join()
        reader_thread.join()

        # Verify no errors occurred and reads returned valid counts
        self.assertTrue(len(read_results) > 0)
        self.assertTrue(all(r >= 10 for r in read_results))  # At least initial logs

        # Final count should be 60 (10 initial + 50 concurrent)
        final_count = query.count()
        self.assertEqual(final_count, 60)


class TestCleanup(TestCase):
    """Tests for automatic log cleanup."""

    def setUp(self):
        """Create temporary project directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cleanup_old_entries(self):
        """Test that old entries are cleaned up when max_entries is exceeded."""
        # Create handler with low max_entries
        db_path = self.project_dir / ".autocoder" / "logs.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        handler = StructuredLogHandler(db_path, max_entries=10)

        # Create a logger using this handler
        import logging
        logger = logging.getLogger("test_cleanup")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Write more than max_entries
        for i in range(20):
            logger.info(f"Log message {i}")

        # Query the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM logs")
        count = cursor.fetchone()[0]
        conn.close()

        # Should have at most max_entries
        self.assertLessEqual(count, 10)


if __name__ == "__main__":
    import unittest
    unittest.main()
