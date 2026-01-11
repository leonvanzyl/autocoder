"""
Shared Context Manager
======================

Manages shared state and communication between agents in the multi-agent system.

The SharedContext provides:
- Persistent storage for decisions, findings, and recommendations
- Message passing between agents
- Architecture decisions tracking
- Review notes and quality metrics
- Session history for context continuity
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class AgentMessage:
    """A message from one agent to another."""

    from_agent: str
    to_agent: str  # Use "*" for broadcast to all agents
    message_type: str  # "info", "warning", "action_required", "decision"
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    acknowledged: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """Create from dictionary."""
        return cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            acknowledged=data.get("acknowledged", False),
        )


@dataclass
class ArchitectureDecision:
    """A recorded architecture decision."""

    id: str
    title: str
    decision: str
    rationale: str
    alternatives_considered: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    decided_by: str = "architect"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives_considered": self.alternatives_considered,
            "timestamp": self.timestamp,
            "decided_by": self.decided_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArchitectureDecision":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            decision=data["decision"],
            rationale=data["rationale"],
            alternatives_considered=data.get("alternatives_considered", []),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            decided_by=data.get("decided_by", "architect"),
        )


@dataclass
class ReviewFinding:
    """A finding from a code review."""

    task_id: int
    severity: str  # "critical", "major", "minor", "info"
    category: str  # "bug", "security", "performance", "style", "architecture"
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: Optional[str] = None
    resolved: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "recommendation": self.recommendation,
            "resolved": self.resolved,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewFinding":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            severity=data["severity"],
            category=data["category"],
            description=data["description"],
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            recommendation=data.get("recommendation"),
            resolved=data.get("resolved", False),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )


class SharedContext:
    """
    Manages shared context between agents.

    This class provides persistent storage for:
    - Messages between agents
    - Architecture decisions
    - Review findings
    - Session metadata
    - Quality metrics
    """

    def __init__(self, project_dir: Path):
        """
        Initialize shared context for a project.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = project_dir
        self.context_file = project_dir / ".agent_context.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict:
        """Load context from file or create new."""
        if self.context_file.exists():
            try:
                with open(self.context_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load context file: {e}")

        # Default structure
        return {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "messages": [],
            "architecture_decisions": [],
            "review_findings": [],
            "session_history": [],
            "quality_metrics": {
                "average_review_score": None,
                "total_reviews": 0,
                "total_findings": 0,
                "resolved_findings": 0,
            },
            "globals": {},  # Arbitrary key-value storage
        }

    def _save(self) -> None:
        """Save context to file."""
        self._data["updated_at"] = datetime.utcnow().isoformat()
        try:
            with open(self.context_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save context file: {e}")

    # =========================================================================
    # Message Management
    # =========================================================================

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> AgentMessage:
        """
        Send a message from one agent to another.

        Args:
            from_agent: The sending agent type
            to_agent: The receiving agent type (or "*" for all)
            message_type: Type of message (info, warning, action_required, decision)
            content: The message content
            metadata: Optional additional data

        Returns:
            The created message
        """
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
        )
        self._data["messages"].append(message.to_dict())
        self._save()
        return message

    def get_messages_for_agent(
        self,
        agent_type: str,
        unacknowledged_only: bool = True,
    ) -> list[AgentMessage]:
        """
        Get messages intended for a specific agent.

        Args:
            agent_type: The agent type to get messages for
            unacknowledged_only: Only return unacknowledged messages

        Returns:
            List of messages for the agent
        """
        messages = []
        for msg_data in self._data["messages"]:
            msg = AgentMessage.from_dict(msg_data)
            if msg.to_agent in (agent_type, "*"):
                if not unacknowledged_only or not msg.acknowledged:
                    messages.append(msg)
        return messages

    def acknowledge_message(self, message_index: int) -> None:
        """Mark a message as acknowledged."""
        if 0 <= message_index < len(self._data["messages"]):
            self._data["messages"][message_index]["acknowledged"] = True
            self._save()

    def acknowledge_all_for_agent(self, agent_type: str) -> int:
        """
        Acknowledge all messages for an agent.

        Returns:
            Number of messages acknowledged
        """
        count = 0
        for msg in self._data["messages"]:
            if msg["to_agent"] in (agent_type, "*") and not msg["acknowledged"]:
                msg["acknowledged"] = True
                count += 1
        if count > 0:
            self._save()
        return count

    # =========================================================================
    # Architecture Decisions
    # =========================================================================

    def add_decision(
        self,
        decision_id: str,
        title: str,
        decision: str,
        rationale: str,
        alternatives: Optional[list[str]] = None,
        decided_by: str = "architect",
    ) -> ArchitectureDecision:
        """
        Record an architecture decision.

        Args:
            decision_id: Unique ID for the decision (e.g., "ADR-001")
            title: Short title
            decision: What was decided
            rationale: Why this decision was made
            alternatives: Other options considered
            decided_by: Which agent made the decision

        Returns:
            The created decision record
        """
        decision_obj = ArchitectureDecision(
            id=decision_id,
            title=title,
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives or [],
            decided_by=decided_by,
        )
        self._data["architecture_decisions"].append(decision_obj.to_dict())
        self._save()
        return decision_obj

    def get_decisions(self) -> list[ArchitectureDecision]:
        """Get all architecture decisions."""
        return [
            ArchitectureDecision.from_dict(d)
            for d in self._data["architecture_decisions"]
        ]

    def get_decision(self, decision_id: str) -> Optional[ArchitectureDecision]:
        """Get a specific decision by ID."""
        for d in self._data["architecture_decisions"]:
            if d["id"] == decision_id:
                return ArchitectureDecision.from_dict(d)
        return None

    # =========================================================================
    # Review Findings
    # =========================================================================

    def add_finding(
        self,
        task_id: int,
        severity: str,
        category: str,
        description: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        recommendation: Optional[str] = None,
    ) -> ReviewFinding:
        """
        Record a review finding.

        Args:
            task_id: The task this finding relates to
            severity: Severity level (critical, major, minor, info)
            category: Category (bug, security, performance, style, architecture)
            description: Description of the finding
            file_path: Optional file where issue was found
            line_number: Optional line number
            recommendation: Optional fix recommendation

        Returns:
            The created finding
        """
        finding = ReviewFinding(
            task_id=task_id,
            severity=severity,
            category=category,
            description=description,
            file_path=file_path,
            line_number=line_number,
            recommendation=recommendation,
        )
        self._data["review_findings"].append(finding.to_dict())
        self._data["quality_metrics"]["total_findings"] += 1
        self._save()
        return finding

    def get_findings(
        self,
        task_id: Optional[int] = None,
        severity: Optional[str] = None,
        unresolved_only: bool = False,
    ) -> list[ReviewFinding]:
        """
        Get review findings with optional filters.

        Args:
            task_id: Filter by task ID
            severity: Filter by severity
            unresolved_only: Only return unresolved findings

        Returns:
            List of matching findings
        """
        findings = []
        for f_data in self._data["review_findings"]:
            finding = ReviewFinding.from_dict(f_data)
            if task_id is not None and finding.task_id != task_id:
                continue
            if severity is not None and finding.severity != severity:
                continue
            if unresolved_only and finding.resolved:
                continue
            findings.append(finding)
        return findings

    def resolve_finding(self, task_id: int, index: int = 0) -> bool:
        """
        Mark a finding as resolved.

        Args:
            task_id: The task ID
            index: The finding index for that task (if multiple)

        Returns:
            True if finding was found and resolved
        """
        count = 0
        for f in self._data["review_findings"]:
            if f["task_id"] == task_id:
                if count == index and not f["resolved"]:
                    f["resolved"] = True
                    self._data["quality_metrics"]["resolved_findings"] += 1
                    self._save()
                    return True
                count += 1
        return False

    # =========================================================================
    # Session History
    # =========================================================================

    def record_session(
        self,
        agent_type: str,
        session_number: int,
        summary: str,
        tasks_completed: int = 0,
        tasks_created: int = 0,
        issues_found: int = 0,
    ) -> None:
        """
        Record a completed agent session.

        Args:
            agent_type: The type of agent that ran
            session_number: Session number
            summary: Brief summary of what was done
            tasks_completed: Number of tasks completed
            tasks_created: Number of new tasks created
            issues_found: Number of issues found
        """
        session = {
            "agent_type": agent_type,
            "session_number": session_number,
            "summary": summary,
            "tasks_completed": tasks_completed,
            "tasks_created": tasks_created,
            "issues_found": issues_found,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._data["session_history"].append(session)
        self._save()

    def get_session_history(
        self,
        agent_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get recent session history.

        Args:
            agent_type: Filter by agent type
            limit: Maximum sessions to return

        Returns:
            List of session records (most recent first)
        """
        sessions = self._data["session_history"]
        if agent_type:
            sessions = [s for s in sessions if s["agent_type"] == agent_type]
        return sessions[-limit:][::-1]  # Most recent first

    # =========================================================================
    # Quality Metrics
    # =========================================================================

    def update_review_metrics(self, review_score: int) -> None:
        """
        Update quality metrics after a review.

        Args:
            review_score: The review score (1-5)
        """
        metrics = self._data["quality_metrics"]
        total = metrics["total_reviews"]
        current_avg = metrics["average_review_score"] or 0

        # Calculate new average
        new_avg = ((current_avg * total) + review_score) / (total + 1)
        metrics["average_review_score"] = round(new_avg, 2)
        metrics["total_reviews"] = total + 1
        self._save()

    def get_quality_metrics(self) -> dict:
        """Get current quality metrics."""
        return self._data["quality_metrics"].copy()

    # =========================================================================
    # Global Key-Value Storage
    # =========================================================================

    def set_global(self, key: str, value: Any) -> None:
        """Set a global value accessible to all agents."""
        self._data["globals"][key] = value
        self._save()

    def get_global(self, key: str, default: Any = None) -> Any:
        """Get a global value."""
        return self._data["globals"].get(key, default)

    def delete_global(self, key: str) -> bool:
        """Delete a global value."""
        if key in self._data["globals"]:
            del self._data["globals"][key]
            self._save()
            return True
        return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_summary(self) -> dict:
        """Get a summary of the shared context."""
        return {
            "created_at": self._data["created_at"],
            "updated_at": self._data["updated_at"],
            "pending_messages": len([
                m for m in self._data["messages"] if not m["acknowledged"]
            ]),
            "total_decisions": len(self._data["architecture_decisions"]),
            "total_findings": self._data["quality_metrics"]["total_findings"],
            "unresolved_findings": (
                self._data["quality_metrics"]["total_findings"]
                - self._data["quality_metrics"]["resolved_findings"]
            ),
            "total_sessions": len(self._data["session_history"]),
            "quality_metrics": self._data["quality_metrics"],
        }

    def clear(self) -> None:
        """Clear all shared context (use with caution)."""
        self._data = self._load()  # Reset to defaults
        self._save()
