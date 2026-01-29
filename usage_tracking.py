"""
Usage Tracking Module
=====================

Tracks API usage, token consumption, and costs for the autonomous coding agent.
Provides analytics for understanding resource consumption and optimizing costs.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON

logger = logging.getLogger(__name__)

Base = declarative_base()


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class UsageRecord(Base):
    """Individual API call usage record."""

    __tablename__ = "usage_records"

    __table_args__ = (
        Index("ix_usage_project_time", "project_name", "timestamp"),
        Index("ix_usage_model_time", "model_id", "timestamp"),
        Index("ix_usage_agent_type", "agent_type", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)
    model_id = Column(String(100), nullable=False, index=True)
    agent_type = Column(String(20), nullable=False)  # initializer, coder, tester
    feature_id = Column(Integer, nullable=True)  # Can be null for initializer
    feature_name = Column(String(255), nullable=True)

    # Token counts
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cache_write_tokens = Column(Integer, nullable=False, default=0)

    # Cost calculation (in USD)
    estimated_cost = Column(Float, nullable=False, default=0.0)

    # Timing
    timestamp = Column(DateTime, nullable=False, default=_utc_now)
    duration_ms = Column(Integer, nullable=True)  # API call duration

    # Additional metadata
    call_metadata = Column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "projectName": self.project_name,
            "modelId": self.model_id,
            "agentType": self.agent_type,
            "featureId": self.feature_id,
            "featureName": self.feature_name,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "cacheWriteTokens": self.cache_write_tokens,
            "estimatedCost": self.estimated_cost,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "durationMs": self.duration_ms,
            "metadata": self.call_metadata,
        }


class DailyUsageSummary(Base):
    """Aggregated daily usage statistics per project/model."""

    __tablename__ = "daily_usage_summary"

    __table_args__ = (
        Index("ix_daily_project_date", "project_name", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)
    model_id = Column(String(100), nullable=False)
    date = Column(DateTime, nullable=False, index=True)  # Date only (midnight UTC)

    # Aggregated counts
    total_calls = Column(Integer, nullable=False, default=0)
    total_input_tokens = Column(Integer, nullable=False, default=0)
    total_output_tokens = Column(Integer, nullable=False, default=0)
    total_cache_read_tokens = Column(Integer, nullable=False, default=0)
    total_cache_write_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)

    # Feature stats
    features_completed = Column(Integer, nullable=False, default=0)
    features_attempted = Column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "projectName": self.project_name,
            "modelId": self.model_id,
            "date": self.date.isoformat() if self.date else None,
            "totalCalls": self.total_calls,
            "totalInputTokens": self.total_input_tokens,
            "totalOutputTokens": self.total_output_tokens,
            "totalCacheReadTokens": self.total_cache_read_tokens,
            "totalCacheWriteTokens": self.total_cache_write_tokens,
            "totalCost": self.total_cost,
            "featuresCompleted": self.features_completed,
            "featuresAttempted": self.features_attempted,
        }


class FeatureAttempt(Base):
    """Tracks individual feature implementation attempts for learning."""

    __tablename__ = "feature_attempts"

    __table_args__ = (
        Index("ix_attempt_project_feature", "project_name", "feature_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)
    feature_id = Column(Integer, nullable=False, index=True)
    feature_name = Column(String(255), nullable=True)
    feature_category = Column(String(100), nullable=True)

    # Attempt details
    attempt_number = Column(Integer, nullable=False, default=1)
    model_id = Column(String(100), nullable=False)
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    completed_at = Column(DateTime, nullable=True)

    # Outcome
    success = Column(Integer, nullable=False, default=0)  # 0=failed, 1=success
    failure_reason = Column(Text, nullable=True)

    # Resource consumption
    total_input_tokens = Column(Integer, nullable=False, default=0)
    total_output_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)
    total_duration_ms = Column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "projectName": self.project_name,
            "featureId": self.feature_id,
            "featureName": self.feature_name,
            "featureCategory": self.feature_category,
            "attemptNumber": self.attempt_number,
            "modelId": self.model_id,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "success": bool(self.success),
            "failureReason": self.failure_reason,
            "totalInputTokens": self.total_input_tokens,
            "totalOutputTokens": self.total_output_tokens,
            "totalCost": self.total_cost,
            "totalDurationMs": self.total_duration_ms,
        }


# =============================================================================
# Usage Tracking Service
# =============================================================================


class UsageTracker:
    """
    Service for tracking and analyzing API usage.

    Provides methods to:
    - Record individual API calls
    - Aggregate daily statistics
    - Query usage history
    - Calculate costs
    """

    # Model pricing (per 1K tokens, in USD)
    MODEL_PRICING: dict[str, dict[str, float]] = {
        "claude-opus-4-5-20251101": {"input": 0.015, "output": 0.075},
        "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    }

    def __init__(self, db_path: Path):
        """
        Initialize the usage tracker.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
    ) -> float:
        """
        Calculate estimated cost for an API call.

        Cache read tokens are typically charged at 10% of input rate.
        """
        pricing = self.MODEL_PRICING.get(
            model_id,
            {"input": 0.003, "output": 0.015},  # Default to Sonnet pricing
        )

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        cache_cost = (cache_read_tokens / 1000) * pricing["input"] * 0.1

        return input_cost + output_cost + cache_cost

    def record_usage(
        self,
        project_name: str,
        model_id: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        feature_id: int | None = None,
        feature_name: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord:
        """
        Record a single API usage event.

        Args:
            project_name: Name of the project
            model_id: Model identifier
            agent_type: Type of agent (initializer, coder, tester)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Tokens read from cache
            cache_write_tokens: Tokens written to cache
            feature_id: Optional feature ID
            feature_name: Optional feature name
            duration_ms: API call duration in milliseconds
            metadata: Additional metadata

        Returns:
            The created UsageRecord
        """
        estimated_cost = self.calculate_cost(
            model_id, input_tokens, output_tokens, cache_read_tokens
        )

        record = UsageRecord(
            project_name=project_name,
            model_id=model_id,
            agent_type=agent_type,
            feature_id=feature_id,
            feature_name=feature_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            estimated_cost=estimated_cost,
            duration_ms=duration_ms,
            call_metadata=metadata,
        )

        with self._get_session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def record_feature_attempt(
        self,
        project_name: str,
        feature_id: int,
        model_id: str,
        feature_name: str | None = None,
        feature_category: str | None = None,
    ) -> FeatureAttempt:
        """
        Record the start of a feature implementation attempt.

        Returns:
            The created FeatureAttempt
        """
        with self._get_session() as session:
            # Count previous attempts
            attempt_count = (
                session.query(func.count(FeatureAttempt.id))
                .filter(
                    FeatureAttempt.project_name == project_name,
                    FeatureAttempt.feature_id == feature_id,
                )
                .scalar()
            )

            attempt = FeatureAttempt(
                project_name=project_name,
                feature_id=feature_id,
                feature_name=feature_name,
                feature_category=feature_category,
                attempt_number=attempt_count + 1,
                model_id=model_id,
            )

            session.add(attempt)
            session.commit()
            session.refresh(attempt)
            return attempt

    def complete_feature_attempt(
        self,
        attempt_id: int,
        success: bool,
        failure_reason: str | None = None,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        total_cost: float = 0.0,
        total_duration_ms: int = 0,
    ) -> FeatureAttempt | None:
        """
        Mark a feature attempt as complete.

        Returns:
            The updated FeatureAttempt or None if not found
        """
        with self._get_session() as session:
            attempt = session.query(FeatureAttempt).filter_by(id=attempt_id).first()
            if attempt:
                attempt.completed_at = _utc_now()
                attempt.success = 1 if success else 0
                attempt.failure_reason = failure_reason
                attempt.total_input_tokens = total_input_tokens
                attempt.total_output_tokens = total_output_tokens
                attempt.total_cost = total_cost
                attempt.total_duration_ms = total_duration_ms
                session.commit()
                session.refresh(attempt)
            return attempt

    def get_project_usage_summary(
        self,
        project_name: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get usage summary for a project over the specified period.

        Returns:
            Dictionary with usage statistics
        """
        cutoff = _utc_now() - timedelta(days=days)

        with self._get_session() as session:
            # Get totals
            totals = (
                session.query(
                    func.count(UsageRecord.id).label("total_calls"),
                    func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
                    func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
                    func.sum(UsageRecord.estimated_cost).label("total_cost"),
                )
                .filter(
                    UsageRecord.project_name == project_name,
                    UsageRecord.timestamp >= cutoff,
                )
                .first()
            )

            # Get usage by model
            by_model = (
                session.query(
                    UsageRecord.model_id,
                    func.count(UsageRecord.id).label("calls"),
                    func.sum(UsageRecord.input_tokens).label("input_tokens"),
                    func.sum(UsageRecord.output_tokens).label("output_tokens"),
                    func.sum(UsageRecord.estimated_cost).label("cost"),
                )
                .filter(
                    UsageRecord.project_name == project_name,
                    UsageRecord.timestamp >= cutoff,
                )
                .group_by(UsageRecord.model_id)
                .all()
            )

            # Get usage by agent type
            by_agent = (
                session.query(
                    UsageRecord.agent_type,
                    func.count(UsageRecord.id).label("calls"),
                    func.sum(UsageRecord.estimated_cost).label("cost"),
                )
                .filter(
                    UsageRecord.project_name == project_name,
                    UsageRecord.timestamp >= cutoff,
                )
                .group_by(UsageRecord.agent_type)
                .all()
            )

            # Get feature attempt stats
            feature_stats = (
                session.query(
                    func.count(FeatureAttempt.id).label("total_attempts"),
                    func.sum(FeatureAttempt.success).label("successful"),
                )
                .filter(
                    FeatureAttempt.project_name == project_name,
                    FeatureAttempt.started_at >= cutoff,
                )
                .first()
            )

            return {
                "projectName": project_name,
                "periodDays": days,
                "totals": {
                    "calls": totals[0] or 0,
                    "inputTokens": totals[1] or 0,
                    "outputTokens": totals[2] or 0,
                    "cost": round(totals[3] or 0, 4),
                },
                "byModel": [
                    {
                        "modelId": row[0],
                        "calls": row[1],
                        "inputTokens": row[2] or 0,
                        "outputTokens": row[3] or 0,
                        "cost": round(row[4] or 0, 4),
                    }
                    for row in by_model
                ],
                "byAgentType": [
                    {
                        "agentType": row[0],
                        "calls": row[1],
                        "cost": round(row[2] or 0, 4),
                    }
                    for row in by_agent
                ],
                "featureStats": {
                    "totalAttempts": feature_stats[0] or 0,
                    "successful": feature_stats[1] or 0,
                    "successRate": (
                        round((feature_stats[1] or 0) / feature_stats[0] * 100, 1)
                        if feature_stats[0]
                        else 0
                    ),
                },
            }

    def get_daily_usage(
        self,
        project_name: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Get daily usage breakdown for a project.

        Returns:
            List of daily usage dictionaries
        """
        cutoff = _utc_now() - timedelta(days=days)

        with self._get_session() as session:
            # Group by date
            daily = (
                session.query(
                    func.date(UsageRecord.timestamp).label("date"),
                    func.count(UsageRecord.id).label("calls"),
                    func.sum(UsageRecord.input_tokens).label("input_tokens"),
                    func.sum(UsageRecord.output_tokens).label("output_tokens"),
                    func.sum(UsageRecord.estimated_cost).label("cost"),
                )
                .filter(
                    UsageRecord.project_name == project_name,
                    UsageRecord.timestamp >= cutoff,
                )
                .group_by(func.date(UsageRecord.timestamp))
                .order_by(func.date(UsageRecord.timestamp))
                .all()
            )

            return [
                {
                    "date": str(row[0]),
                    "calls": row[1],
                    "inputTokens": row[2] or 0,
                    "outputTokens": row[3] or 0,
                    "cost": round(row[4] or 0, 4),
                }
                for row in daily
            ]

    def get_feature_attempts(
        self,
        project_name: str,
        feature_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get feature attempt history.

        Args:
            project_name: Project name
            feature_id: Optional filter by feature ID
            limit: Maximum records to return

        Returns:
            List of feature attempt dictionaries
        """
        with self._get_session() as session:
            query = session.query(FeatureAttempt).filter(
                FeatureAttempt.project_name == project_name
            )

            if feature_id is not None:
                query = query.filter(FeatureAttempt.feature_id == feature_id)

            attempts = (
                query.order_by(FeatureAttempt.started_at.desc()).limit(limit).all()
            )

            return [a.to_dict() for a in attempts]

    def get_recent_usage(
        self,
        project_name: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get recent usage records.

        Returns:
            List of recent usage record dictionaries
        """
        with self._get_session() as session:
            records = (
                session.query(UsageRecord)
                .filter(UsageRecord.project_name == project_name)
                .order_by(UsageRecord.timestamp.desc())
                .limit(limit)
                .all()
            )

            return [r.to_dict() for r in records]


# =============================================================================
# Global Usage Tracker Instance
# =============================================================================

_usage_trackers: dict[str, UsageTracker] = {}


def get_usage_tracker(project_path: Path) -> UsageTracker:
    """
    Get or create a UsageTracker for a project.

    Args:
        project_path: Path to the project directory

    Returns:
        UsageTracker instance for the project
    """
    db_path = project_path / ".autocoder" / "usage.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    path_str = str(db_path)
    if path_str not in _usage_trackers:
        _usage_trackers[path_str] = UsageTracker(db_path)

    return _usage_trackers[path_str]
