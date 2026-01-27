"""
Database Models
===============

SQLAlchemy ORM models for the Autocoder system.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

Base = declarative_base()


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    # Composite index for common status query pattern (passes, in_progress)
    # Used by feature_get_stats, get_ready_features, and other status queries
    __table_args__ = (
        Index('ix_feature_status', 'passes', 'in_progress'),
    )

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, nullable=False, default=False, index=True)
    in_progress = Column(Boolean, nullable=False, default=False, index=True)
    # Dependencies: list of feature IDs that must be completed before this feature
    # NULL/empty = no dependencies (backwards compatible)
    dependencies = Column(JSON, nullable=True, default=None)

    # Timestamps for analytics and tracking
    created_at = Column(DateTime, nullable=True, default=_utc_now)  # When feature was created
    started_at = Column(DateTime, nullable=True)  # When work started (in_progress=True)
    completed_at = Column(DateTime, nullable=True)  # When marked passing
    last_failed_at = Column(DateTime, nullable=True)  # Last time feature failed

    # Error tracking
    last_error = Column(Text, nullable=True)  # Last error message when feature failed

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            # Handle legacy NULL values gracefully - treat as False
            "passes": self.passes if self.passes is not None else False,
            "in_progress": self.in_progress if self.in_progress is not None else False,
            # Dependencies: NULL/empty treated as empty list for backwards compat
            "dependencies": self.dependencies if self.dependencies else [],
            # Timestamps (ISO format strings or None)
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_failed_at": self.last_failed_at.isoformat() if self.last_failed_at else None,
            # Error tracking
            "last_error": self.last_error,
        }

    def get_dependencies_safe(self) -> list[int]:
        """Safely extract dependencies, handling NULL and malformed data."""
        if self.dependencies is None:
            return []
        if isinstance(self.dependencies, list):
            return [d for d in self.dependencies if isinstance(d, int)]
        return []

    # Relationship to attempts (for agent attribution)
    attempts = relationship("FeatureAttempt", back_populates="feature", cascade="all, delete-orphan")

    # Relationship to error history
    errors = relationship("FeatureError", back_populates="feature", cascade="all, delete-orphan")


class FeatureAttempt(Base):
    """Tracks individual agent attempts on features for attribution and analytics.

    Each time an agent claims a feature and works on it, a new attempt record is created.
    This allows tracking:
    - Which agent worked on which feature
    - How long each attempt took
    - Success/failure outcomes
    - Error messages from failed attempts
    """

    __tablename__ = "feature_attempts"

    __table_args__ = (
        Index('ix_attempt_feature', 'feature_id'),
        Index('ix_attempt_agent', 'agent_type', 'agent_id'),
        Index('ix_attempt_outcome', 'outcome'),
    )

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(
        Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )

    # Agent identification
    agent_type = Column(String(20), nullable=False)  # "initializer", "coding", "testing"
    agent_id = Column(String(100), nullable=True)  # e.g., "feature-5", "testing-12345"
    agent_index = Column(Integer, nullable=True)  # For parallel agents: 0, 1, 2, etc.

    # Timing
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime, nullable=True)

    # Outcome: "success", "failure", "abandoned", "in_progress"
    outcome = Column(String(20), nullable=False, default="in_progress")

    # Error tracking (if outcome is "failure")
    error_message = Column(Text, nullable=True)

    # Relationship
    feature = relationship("Feature", back_populates="attempts")

    def to_dict(self) -> dict:
        """Convert attempt to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "agent_index": self.agent_index,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "outcome": self.outcome,
            "error_message": self.error_message,
        }

    @property
    def duration_seconds(self) -> float | None:
        """Calculate attempt duration in seconds."""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None


class FeatureError(Base):
    """Tracks error history for features.

    Each time a feature fails, an error record is created to maintain
    a full history of all errors encountered. This is useful for:
    - Debugging recurring issues
    - Understanding failure patterns
    - Tracking error resolution over time
    """

    __tablename__ = "feature_errors"

    __table_args__ = (
        Index('ix_error_feature', 'feature_id'),
        Index('ix_error_type', 'error_type'),
        Index('ix_error_timestamp', 'occurred_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(
        Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False
    )

    # Error details
    error_type = Column(String(50), nullable=False)  # "test_failure", "lint_error", "runtime_error", "timeout", "other"
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)  # Optional full stack trace

    # Context
    agent_type = Column(String(20), nullable=True)  # Which agent encountered the error
    agent_id = Column(String(100), nullable=True)
    attempt_id = Column(Integer, ForeignKey("feature_attempts.id", ondelete="SET NULL"), nullable=True)

    # Timing
    occurred_at = Column(DateTime, nullable=False, default=_utc_now)

    # Resolution tracking
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Relationship
    feature = relationship("Feature", back_populates="errors")

    def to_dict(self) -> dict:
        """Convert error to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "attempt_id": self.attempt_id,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
        }


class Schedule(Base):
    """Time-based schedule for automated agent start/stop."""

    __tablename__ = "schedules"

    # Database-level CHECK constraints for data integrity
    __table_args__ = (
        CheckConstraint('duration_minutes >= 1 AND duration_minutes <= 1440', name='ck_schedule_duration'),
        CheckConstraint('days_of_week >= 0 AND days_of_week <= 127', name='ck_schedule_days'),
        CheckConstraint('max_concurrency >= 1 AND max_concurrency <= 5', name='ck_schedule_concurrency'),
        CheckConstraint('crash_count >= 0', name='ck_schedule_crash_count'),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)

    # Timing (stored in UTC)
    start_time = Column(String(5), nullable=False)  # "HH:MM" format
    duration_minutes = Column(Integer, nullable=False)  # 1-1440

    # Day filtering (bitfield: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)
    days_of_week = Column(Integer, nullable=False, default=127)  # 127 = all days

    # State
    enabled = Column(Boolean, nullable=False, default=True, index=True)

    # Agent configuration for scheduled runs
    yolo_mode = Column(Boolean, nullable=False, default=False)
    model = Column(String(50), nullable=True)  # None = use global default
    max_concurrency = Column(Integer, nullable=False, default=3)  # 1-5 concurrent agents

    # Crash recovery tracking
    crash_count = Column(Integer, nullable=False, default=0)  # Resets at window start

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    overrides = relationship(
        "ScheduleOverride", back_populates="schedule", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert schedule to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "days_of_week": self.days_of_week,
            "enabled": self.enabled,
            "yolo_mode": self.yolo_mode,
            "model": self.model,
            "max_concurrency": self.max_concurrency,
            "crash_count": self.crash_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_active_on_day(self, weekday: int) -> bool:
        """Check if schedule is active on given weekday (0=Monday, 6=Sunday)."""
        day_bit = 1 << weekday
        return bool(self.days_of_week & day_bit)


class ScheduleOverride(Base):
    """Persisted manual override for a schedule window."""

    __tablename__ = "schedule_overrides"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )

    # Override details
    override_type = Column(String(10), nullable=False)  # "start" or "stop"
    expires_at = Column(DateTime, nullable=False)  # When this window ends (UTC)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    schedule = relationship("Schedule", back_populates="overrides")

    def to_dict(self) -> dict:
        """Convert override to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "override_type": self.override_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
