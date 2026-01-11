"""
Agent Communication MCP Server
==============================

MCP tools for inter-agent communication and coordination.

These tools allow agents to:
- Send and receive messages to/from other agents
- Record and query architecture decisions
- Log and manage review findings
- Access shared context and metrics
"""

import json
from pathlib import Path
from typing import Optional

from mcp import Tool
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# Will be set during server initialization
_project_dir: Optional[Path] = None
_shared_context = None


def get_context():
    """Get or create the shared context."""
    global _shared_context
    if _shared_context is None:
        if _project_dir is None:
            raise RuntimeError("Agent MCP server not initialized with project directory")
        from shared_context import SharedContext
        _shared_context = SharedContext(_project_dir)
    return _shared_context


# Create MCP server
mcp = Server("agent-communication")


# =============================================================================
# Message Tools
# =============================================================================


@mcp.tool()
def agent_send_message(
    to_agent: str,
    message_type: str,
    content: str,
    metadata: str | None = None,
) -> str:
    """Send a message to another agent.

    Use this to communicate information, warnings, or action items
    between different agent types.

    Args:
        to_agent: Target agent type (architect, initializer, coding, reviewer, testing)
                  Use "*" to broadcast to all agents.
        message_type: Type of message:
                     - "info": General information
                     - "warning": Something to be aware of
                     - "action_required": Something that needs to be done
                     - "decision": A decision that was made
        content: The message content
        metadata: Optional JSON string with additional data

    Returns:
        Confirmation of message sent
    """
    ctx = get_context()
    meta = json.loads(metadata) if metadata else {}

    # Determine current agent (from context or default)
    from_agent = ctx.get_global("current_agent", "coding")

    msg = ctx.send_message(
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=message_type,
        content=content,
        metadata=meta,
    )

    return json.dumps({
        "status": "sent",
        "to": to_agent,
        "type": message_type,
        "timestamp": msg.timestamp,
    })


@mcp.tool()
def agent_get_messages(unacknowledged_only: bool = True) -> str:
    """Get messages intended for the current agent.

    Args:
        unacknowledged_only: Only return messages not yet acknowledged

    Returns:
        JSON list of messages for this agent
    """
    ctx = get_context()
    current_agent = ctx.get_global("current_agent", "coding")

    messages = ctx.get_messages_for_agent(current_agent, unacknowledged_only)

    return json.dumps({
        "agent": current_agent,
        "message_count": len(messages),
        "messages": [m.to_dict() for m in messages],
    })


@mcp.tool()
def agent_acknowledge_messages() -> str:
    """Acknowledge all pending messages for the current agent.

    Call this after processing messages to mark them as handled.

    Returns:
        Number of messages acknowledged
    """
    ctx = get_context()
    current_agent = ctx.get_global("current_agent", "coding")

    count = ctx.acknowledge_all_for_agent(current_agent)

    return json.dumps({
        "acknowledged": count,
        "agent": current_agent,
    })


# =============================================================================
# Architecture Decision Tools
# =============================================================================


@mcp.tool()
def agent_record_decision(
    decision_id: str,
    title: str,
    decision: str,
    rationale: str,
    alternatives: str | None = None,
) -> str:
    """Record an architecture or design decision.

    Use this to document important decisions that other agents
    should be aware of and follow.

    Args:
        decision_id: Unique ID (e.g., "ADR-001", "DB-001")
        title: Short descriptive title
        decision: What was decided
        rationale: Why this decision was made
        alternatives: JSON array of alternatives considered (optional)

    Returns:
        Confirmation of recorded decision
    """
    ctx = get_context()
    current_agent = ctx.get_global("current_agent", "architect")

    alts = json.loads(alternatives) if alternatives else []

    decision_obj = ctx.add_decision(
        decision_id=decision_id,
        title=title,
        decision=decision,
        rationale=rationale,
        alternatives=alts,
        decided_by=current_agent,
    )

    return json.dumps({
        "status": "recorded",
        "decision": decision_obj.to_dict(),
    })


@mcp.tool()
def agent_get_decisions() -> str:
    """Get all recorded architecture decisions.

    Use this to understand decisions made by previous agents
    that should guide your work.

    Returns:
        JSON list of all architecture decisions
    """
    ctx = get_context()
    decisions = ctx.get_decisions()

    return json.dumps({
        "count": len(decisions),
        "decisions": [d.to_dict() for d in decisions],
    })


@mcp.tool()
def agent_get_decision(decision_id: str) -> str:
    """Get a specific architecture decision by ID.

    Args:
        decision_id: The decision ID to look up

    Returns:
        The decision details or not found message
    """
    ctx = get_context()
    decision = ctx.get_decision(decision_id)

    if decision:
        return json.dumps({"found": True, "decision": decision.to_dict()})
    else:
        return json.dumps({"found": False, "decision_id": decision_id})


# =============================================================================
# Review Finding Tools
# =============================================================================


@mcp.tool()
def agent_add_finding(
    task_id: int,
    severity: str,
    category: str,
    description: str,
    file_path: str | None = None,
    line_number: int | None = None,
    recommendation: str | None = None,
) -> str:
    """Record a review finding for a task.

    Use this to document issues found during code review.

    Args:
        task_id: The task this finding relates to
        severity: One of: "critical", "major", "minor", "info"
        category: One of: "bug", "security", "performance", "style", "architecture"
        description: Description of the issue
        file_path: File where issue was found (optional)
        line_number: Line number in the file (optional)
        recommendation: Suggested fix (optional)

    Returns:
        Confirmation of recorded finding
    """
    ctx = get_context()

    finding = ctx.add_finding(
        task_id=task_id,
        severity=severity,
        category=category,
        description=description,
        file_path=file_path,
        line_number=line_number,
        recommendation=recommendation,
    )

    return json.dumps({
        "status": "recorded",
        "finding": finding.to_dict(),
    })


@mcp.tool()
def agent_get_findings(
    task_id: int | None = None,
    severity: str | None = None,
    unresolved_only: bool = False,
) -> str:
    """Get review findings with optional filters.

    Args:
        task_id: Filter by task ID (optional)
        severity: Filter by severity level (optional)
        unresolved_only: Only return unresolved findings

    Returns:
        JSON list of matching findings
    """
    ctx = get_context()

    findings = ctx.get_findings(
        task_id=task_id,
        severity=severity,
        unresolved_only=unresolved_only,
    )

    return json.dumps({
        "count": len(findings),
        "findings": [f.to_dict() for f in findings],
    })


@mcp.tool()
def agent_resolve_finding(task_id: int, finding_index: int = 0) -> str:
    """Mark a finding as resolved.

    Args:
        task_id: The task ID
        finding_index: Which finding for that task (0-indexed)

    Returns:
        Success or failure message
    """
    ctx = get_context()

    success = ctx.resolve_finding(task_id, finding_index)

    return json.dumps({
        "resolved": success,
        "task_id": task_id,
        "finding_index": finding_index,
    })


# =============================================================================
# Session and Metrics Tools
# =============================================================================


@mcp.tool()
def agent_record_session(
    summary: str,
    tasks_completed: int = 0,
    tasks_created: int = 0,
    issues_found: int = 0,
) -> str:
    """Record completion of the current agent session.

    Call this at the end of your session to log what was accomplished.

    Args:
        summary: Brief summary of what was done
        tasks_completed: Number of tasks completed
        tasks_created: Number of new tasks created
        issues_found: Number of issues found

    Returns:
        Confirmation of recorded session
    """
    ctx = get_context()
    current_agent = ctx.get_global("current_agent", "coding")
    session_num = ctx.get_global("session_number", 1)

    ctx.record_session(
        agent_type=current_agent,
        session_number=session_num,
        summary=summary,
        tasks_completed=tasks_completed,
        tasks_created=tasks_created,
        issues_found=issues_found,
    )

    return json.dumps({
        "status": "recorded",
        "agent": current_agent,
        "session": session_num,
    })


@mcp.tool()
def agent_get_session_history(
    agent_type: str | None = None,
    limit: int = 10,
) -> str:
    """Get recent session history.

    Args:
        agent_type: Filter by agent type (optional)
        limit: Maximum sessions to return

    Returns:
        JSON list of recent sessions
    """
    ctx = get_context()

    history = ctx.get_session_history(agent_type=agent_type, limit=limit)

    return json.dumps({
        "count": len(history),
        "sessions": history,
    })


@mcp.tool()
def agent_get_quality_metrics() -> str:
    """Get current quality metrics.

    Returns metrics like average review scores, findings count, etc.

    Returns:
        JSON object with quality metrics
    """
    ctx = get_context()
    return json.dumps(ctx.get_quality_metrics())


@mcp.tool()
def agent_get_context_summary() -> str:
    """Get a summary of the shared context.

    Returns overview of messages, decisions, findings, and sessions.

    Returns:
        JSON object with context summary
    """
    ctx = get_context()
    return json.dumps(ctx.get_summary())


# =============================================================================
# Global Context Tools
# =============================================================================


@mcp.tool()
def agent_set_context(key: str, value: str) -> str:
    """Set a value in the shared global context.

    Use this to share information between agent sessions.

    Args:
        key: The key to store under
        value: The value to store (as JSON string for complex types)

    Returns:
        Confirmation
    """
    ctx = get_context()

    # Try to parse as JSON, otherwise store as string
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    ctx.set_global(key, parsed_value)

    return json.dumps({"status": "set", "key": key})


@mcp.tool()
def agent_get_context(key: str) -> str:
    """Get a value from the shared global context.

    Args:
        key: The key to retrieve

    Returns:
        The stored value or null if not found
    """
    ctx = get_context()
    value = ctx.get_global(key)

    return json.dumps({"key": key, "value": value, "found": value is not None})


# =============================================================================
# Task Review Tools (Integration with feature MCP)
# =============================================================================


@mcp.tool()
def task_get_for_review(limit: int = 5) -> str:
    """Get completed tasks that need review.

    Returns tasks that are passing but haven't been reviewed yet.

    Args:
        limit: Maximum number of tasks to return

    Returns:
        JSON list of tasks needing review
    """
    from api.database import Task, get_database_url, create_engine
    from sqlalchemy.orm import sessionmaker

    if _project_dir is None:
        return json.dumps({"error": "Project directory not set"})

    db_url = get_database_url(_project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        tasks = (
            db.query(Task)
            .filter(Task.passes == True, Task.reviewed == False)
            .order_by(Task.priority.asc())
            .limit(limit)
            .all()
        )

        return json.dumps({
            "count": len(tasks),
            "tasks": [t.to_dict() for t in tasks],
        })
    finally:
        db.close()


@mcp.tool()
def task_mark_reviewed(
    task_id: int,
    review_score: int,
    review_notes: str,
) -> str:
    """Mark a task as reviewed with score and notes.

    Args:
        task_id: The task to mark as reviewed
        review_score: Quality score from 1-5
        review_notes: Detailed review notes

    Returns:
        Confirmation of review recorded
    """
    from api.database import Task, get_database_url, create_engine
    from sqlalchemy.orm import sessionmaker

    if _project_dir is None:
        return json.dumps({"error": "Project directory not set"})

    if not 1 <= review_score <= 5:
        return json.dumps({"error": "Review score must be between 1 and 5"})

    db_url = get_database_url(_project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            return json.dumps({"error": f"Task {task_id} not found"})

        task.reviewed = True
        task.review_score = review_score
        task.review_notes = review_notes
        db.commit()

        # Update quality metrics
        ctx = get_context()
        ctx.update_review_metrics(review_score)

        return json.dumps({
            "status": "reviewed",
            "task_id": task_id,
            "score": review_score,
        })
    finally:
        db.close()


# =============================================================================
# Server Initialization
# =============================================================================


def initialize_server(project_dir: Path) -> None:
    """Initialize the MCP server with project directory."""
    global _project_dir, _shared_context
    _project_dir = project_dir
    _shared_context = None  # Will be created on first access


async def run_server():
    """Run the MCP server over stdio."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="agent-communication",
                server_version="1.0.0",
                capabilities=mcp.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent_mcp.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    initialize_server(project_dir)
    asyncio.run(run_server())
