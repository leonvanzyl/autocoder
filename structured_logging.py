"""
Structured Logging Module
=========================

Enhanced logging with structured JSON format, filtering, and export capabilities.

Features:
- JSON-formatted logs with consistent schema
- Filter by agent, feature, level
- Full-text search
- Timeline view for agent activity
- Export logs for offline analysis

Log Format:
{
    "timestamp": "2025-01-21T10:30:00.000Z",
    "level": "info|warn|error",
    "agent_id": "coding-42",
    "feature_id": 42,
    "tool_name": "feature_mark_passing",
    "duration_ms": 150,
    "message": "Feature marked as passing"
}
"""

import hashlib
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional, cast

# Type aliases
# Note: Python's logging uses "warning" but we normalize to "warn" for consistency
LogLevel = Literal["debug", "info", "warn", "warning", "error"]


def _format_ts(dt: datetime) -> str:
    """
    Format a datetime to ISO 8601 string with UTC "Z" suffix.

    Ensures timezone-aware datetimes are converted to UTC first.
    Naive datetimes are assumed to be UTC and get tzinfo set.

    Args:
        dt: Datetime to format

    Returns:
        ISO 8601 string with "Z" suffix (e.g., "2025-01-21T10:30:00.000Z")
    """
    if dt.tzinfo is None:
        # Treat naive datetimes as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if timezone-aware
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


@dataclass
class StructuredLogEntry:
    """A structured log entry with all metadata."""

    timestamp: str
    level: LogLevel
    message: str
    agent_id: Optional[str] = None
    feature_id: Optional[int] = None
    tool_name: Optional[str] = None
    duration_ms: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
        }
        if self.agent_id:
            result["agent_id"] = self.agent_id
        if self.feature_id is not None:
            result["feature_id"] = self.feature_id
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.extra:
            result["extra"] = self.extra
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class StructuredLogHandler(logging.Handler):
    """
    Custom logging handler that stores structured logs in SQLite.

    Thread-safe for concurrent agent logging.
    """

    def __init__(
        self,
        db_path: Path,
        agent_id: Optional[str] = None,
        max_entries: int = 10000,
    ):
        super().__init__()
        self.db_path = db_path
        self.agent_id = agent_id
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._insert_count = 0
        self._cleanup_interval = 100  # Run cleanup every N inserts
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database for logs."""
        with self._lock:
            # Use context manager to ensure connection is closed on errors
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Enable WAL mode for better concurrency with parallel agents
                # WAL allows readers and writers to work concurrently without blocking
                cursor.execute("PRAGMA journal_mode=WAL")

                # Create logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        agent_id TEXT,
                        feature_id INTEGER,
                        tool_name TEXT,
                        duration_ms INTEGER,
                        extra TEXT
                    )
                """)

                # Create indexes for common queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_timestamp
                    ON logs(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_level
                    ON logs(level)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_agent_id
                    ON logs(agent_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_logs_feature_id
                    ON logs(feature_id)
                """)

                conn.commit()

    def emit(self, record: logging.LogRecord) -> None:
        """Store a log record in the database."""
        try:
            # Extract structured data from record
            # Normalize "warning" -> "warn" for consistency
            level_str = record.levelname.lower()
            if level_str == "warning":
                level_str = "warn"
            # Cast to LogLevel since we know the value is valid after normalization
            level: LogLevel = cast(LogLevel, level_str)
            entry = StructuredLogEntry(
                timestamp=_format_ts(datetime.now(timezone.utc)),
                level=level,
                message=self.format(record),
                agent_id=getattr(record, "agent_id", self.agent_id),
                feature_id=getattr(record, "feature_id", None),
                tool_name=getattr(record, "tool_name", None),
                duration_ms=getattr(record, "duration_ms", None),
                extra=getattr(record, "extra", {}),
            )

            with self._lock:
                # Use context manager to ensure connection is closed on errors
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        INSERT INTO logs
                        (timestamp, level, message, agent_id, feature_id, tool_name, duration_ms, extra)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry.timestamp,
                            entry.level,
                            entry.message,
                            entry.agent_id,
                            entry.feature_id,
                            entry.tool_name,
                            entry.duration_ms,
                            json.dumps(entry.extra) if entry.extra else None,
                        ),
                    )

                    # Cleanup old entries periodically (not on every insert)
                    self._insert_count += 1
                    if self._insert_count >= self._cleanup_interval:
                        self._insert_count = 0
                        cursor.execute("SELECT COUNT(*) FROM logs")
                        count = cursor.fetchone()[0]
                        if count > self.max_entries:
                            delete_count = count - self.max_entries
                            cursor.execute(
                                """
                                DELETE FROM logs WHERE id IN (
                                    SELECT id FROM logs ORDER BY timestamp ASC LIMIT ?
                                )
                                """,
                                (delete_count,),
                            )

                    conn.commit()

        except Exception:
            self.handleError(record)


class StructuredLogger:
    """
    Enhanced logger with structured logging capabilities.

    Usage:
        logger = StructuredLogger(project_dir, agent_id="coding-1")
        logger.info("Starting feature", feature_id=42)
        logger.error("Test failed", feature_id=42, tool_name="playwright")
    """

    def __init__(
        self,
        project_dir: Path,
        agent_id: Optional[str] = None,
        console_output: bool = True,
    ):
        self.project_dir = Path(project_dir)
        self.agent_id = agent_id
        self.db_path = self.project_dir / ".autocoder" / "logs.db"

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup logger with unique name per instance to avoid handler accumulation
        # across tests and multiple invocations. Include project path hash for uniqueness.
        path_hash = hashlib.md5(str(self.project_dir).encode()).hexdigest()[:8]
        logger_name = f"autocoder.{agent_id or 'main'}.{path_hash}.{id(self)}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers (for safety, though names should be unique)
        self.logger.handlers.clear()

        # Add structured handler
        self.handler = StructuredLogHandler(self.db_path, agent_id)
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(self.handler)

        # Add console handler if requested
        if console_output:
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            console.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            self.logger.addHandler(console)

    def _log(
        self,
        level: str,
        message: str,
        feature_id: Optional[int] = None,
        tool_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
        **extra,
    ) -> None:
        """Internal logging method with structured data."""
        record_extra = {
            "agent_id": self.agent_id,
            "feature_id": feature_id,
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "extra": extra,
        }

        # Use LogRecord extras
        getattr(self.logger, level)(
            message,
            extra=record_extra,
        )

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log("info", message, **kwargs)

    def warn(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log("warning", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message (alias)."""
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log("error", message, **kwargs)


class LogQuery:
    """
    Query interface for structured logs.

    Supports filtering, searching, and aggregation.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(
        self,
        level: Optional[LogLevel] = None,
        agent_id: Optional[str] = None,
        feature_id: Optional[int] = None,
        tool_name: Optional[str] = None,
        search: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Query logs with filters.

        Args:
            level: Filter by log level
            agent_id: Filter by agent ID
            feature_id: Filter by feature ID
            tool_name: Filter by tool name
            search: Full-text search in message
            since: Start datetime
            until: End datetime
            limit: Max results
            offset: Pagination offset

        Returns:
            List of log entries as dicts
        """
        with self._connect() as conn:
            cursor = conn.cursor()

            conditions: list[str] = []
            params: list[Any] = []

            if level:
                conditions.append("level = ?")
                params.append(level)

            if agent_id:
                conditions.append("agent_id = ?")
                params.append(agent_id)

            if feature_id is not None:
                conditions.append("feature_id = ?")
                params.append(feature_id)

            if tool_name:
                conditions.append("tool_name = ?")
                params.append(tool_name)

            if search:
                conditions.append("message LIKE ? ESCAPE '\\'")
                # Escape LIKE wildcards to prevent unexpected query behavior
                # Escape backslash FIRST, then LIKE wildcards
                escaped_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                params.append(f"%{escaped_search}%")

            if since:
                conditions.append("timestamp >= ?")
                params.append(_format_ts(since))

            if until:
                conditions.append("timestamp <= ?")
                params.append(_format_ts(until))

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT * FROM logs
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def count(
        self,
        level: Optional[LogLevel] = None,
        agent_id: Optional[str] = None,
        feature_id: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count logs matching filters."""
        with self._connect() as conn:
            cursor = conn.cursor()

            conditions: list[str] = []
            params: list[Any] = []

            if level:
                conditions.append("level = ?")
                params.append(level)
            if agent_id:
                conditions.append("agent_id = ?")
                params.append(agent_id)
            if feature_id is not None:
                conditions.append("feature_id = ?")
                params.append(feature_id)
            if since:
                conditions.append("timestamp >= ?")
                params.append(_format_ts(since))

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            cursor.execute(f"SELECT COUNT(*) FROM logs WHERE {where_clause}", params)
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def get_timeline(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        bucket_minutes: int = 5,
    ) -> list[dict]:
        """
        Get activity timeline bucketed by time intervals.

        Returns list of buckets with counts per agent.
        """
        # Default to last 24 hours
        if not since:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
        if not until:
            until = datetime.now(timezone.utc)

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    strftime('%Y-%m-%d %H:', timestamp) ||
                    printf('%02d', (CAST(strftime('%M', timestamp) AS INTEGER) / ?) * ?) || ':00' as bucket,
                    agent_id,
                    COUNT(*) as count,
                    SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as errors
                FROM logs
                WHERE timestamp >= ? AND timestamp <= ?
                GROUP BY bucket, agent_id
                ORDER BY bucket
                """,
                (bucket_minutes, bucket_minutes, _format_ts(since), _format_ts(until)),
            )

            rows = cursor.fetchall()

        # Group by bucket
        buckets = {}
        for row in rows:
            bucket = row["bucket"]
            if bucket not in buckets:
                buckets[bucket] = {"timestamp": bucket, "agents": {}, "total": 0, "errors": 0}
            agent = row["agent_id"] or "main"
            buckets[bucket]["agents"][agent] = row["count"]
            buckets[bucket]["total"] += row["count"]
            buckets[bucket]["errors"] += row["errors"]

        return list(buckets.values())

    def get_agent_stats(self, since: Optional[datetime] = None) -> list[dict]:
        """Get log statistics per agent."""
        params = []
        where_clause = "1=1"
        if since:
            where_clause = "timestamp >= ?"
            params.append(_format_ts(since))

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT
                    agent_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN level = 'info' THEN 1 ELSE 0 END) as info_count,
                    SUM(CASE WHEN level = 'warn' OR level = 'warning' THEN 1 ELSE 0 END) as warn_count,
                    SUM(CASE WHEN level = 'error' THEN 1 ELSE 0 END) as error_count,
                    MIN(timestamp) as first_log,
                    MAX(timestamp) as last_log
                FROM logs
                WHERE {where_clause}
                GROUP BY agent_id
                ORDER BY total DESC
                """,
                params,
            )

            rows = cursor.fetchall()

        # Normalize timestamps to use "Z" suffix for UTC consistency
        results = [dict(row) for row in rows]
        for entry in results:
            if entry.get("first_log"):
                entry["first_log"] = entry["first_log"].replace("+00:00", "Z")
            if entry.get("last_log"):
                entry["last_log"] = entry["last_log"].replace("+00:00", "Z")

        return results

    def _iter_logs(
        self,
        batch_size: int = 1000,
        **filters,
    ):
        """
        Iterate over logs in batches using cursor-based pagination.

        This avoids loading all logs into memory at once.

        Args:
            batch_size: Number of rows to fetch per batch
            **filters: Query filters passed to query()

        Yields:
            Log entries as dicts
        """
        offset = 0
        while True:
            batch = self.query(limit=batch_size, offset=offset, **filters)
            if not batch:
                break
            yield from batch
            offset += len(batch)
            # If we got fewer than batch_size, we've reached the end
            if len(batch) < batch_size:
                break

    def export_logs(
        self,
        output_path: Path,
        output_format: Literal["json", "jsonl", "csv"] = "jsonl",
        batch_size: int = 1000,
        **filters,
    ) -> int:
        """
        Export logs to file using cursor-based streaming.

        Args:
            output_path: Output file path
            output_format: Export format (json, jsonl, csv)
            batch_size: Number of rows to fetch per batch (default 1000)
            **filters: Query filters

        Returns:
            Number of exported entries
        """
        import csv

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0

        if output_format == "json":
            # For JSON format, we still need to collect all to produce valid JSON
            # but we stream to avoid massive single query
            with open(output_path, "w") as f:
                f.write("[\n")
                first = True
                for log in self._iter_logs(batch_size=batch_size, **filters):
                    if not first:
                        f.write(",\n")
                    f.write("  " + json.dumps(log))
                    first = False
                    count += 1
                f.write("\n]")

        elif output_format == "jsonl":
            with open(output_path, "w") as f:
                for log in self._iter_logs(batch_size=batch_size, **filters):
                    f.write(json.dumps(log) + "\n")
                    count += 1

        elif output_format == "csv":
            fieldnames = None
            with open(output_path, "w", newline="") as f:
                writer = None
                for log in self._iter_logs(batch_size=batch_size, **filters):
                    if writer is None:
                        fieldnames = list(log.keys())
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                    writer.writerow(log)
                    count += 1

        return count


def get_logger(
    project_dir: Path,
    agent_id: Optional[str] = None,
    console_output: bool = True,
) -> StructuredLogger:
    """
    Get or create a structured logger for a project.

    Args:
        project_dir: Project directory
        agent_id: Agent identifier (e.g., "coding-1", "initializer")
        console_output: Whether to also log to console

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(project_dir, agent_id, console_output)


def get_log_query(project_dir: Path) -> LogQuery:
    """
    Get log query interface for a project.

    Args:
        project_dir: Project directory

    Returns:
        LogQuery instance
    """
    db_path = Path(project_dir) / ".autocoder" / "logs.db"
    return LogQuery(db_path)
