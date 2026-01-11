"""
Agent Type Selection
====================

Logic for determining which type of agent should run based on
project state and configuration.

Agent Types:
- architect: Designs system architecture (Session 0, before features exist)
- initializer: Creates features from spec (Session 1, after architecture)
- coding: Implements features (main development loop)
- reviewer: Reviews completed work for quality
- testing: Runs tests and verifies functionality
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text

from api.database import get_database_path, get_database_url


class AgentType(Enum):
    """Types of agents available in the system."""

    ARCHITECT = "architect"
    INITIALIZER = "initializer"
    CODING = "coding"
    REVIEWER = "reviewer"
    TESTING = "testing"


@dataclass
class ProjectState:
    """Current state of a project for agent selection."""

    has_architecture: bool = False
    has_features: bool = False
    has_pending_tasks: bool = False
    has_in_progress_tasks: bool = False
    has_completed_unreviewed: bool = False
    has_completed_untested: bool = False
    tasks_needing_review: int = 0
    tasks_needing_testing: int = 0
    current_phase_complete: bool = False


def get_project_state(project_dir: Path) -> ProjectState:
    """
    Analyze the current state of a project.

    Args:
        project_dir: Path to the project directory

    Returns:
        ProjectState with current status information
    """
    state = ProjectState()

    # Check for architecture document
    architecture_file = project_dir / "architecture.md"
    state.has_architecture = architecture_file.exists()

    # Check database state
    db_path = get_database_path(project_dir)
    if not db_path.exists():
        return state

    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    try:
        with engine.connect() as conn:
            # Check for tables
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result.fetchall()}

            # Handle v2 schema
            if "tasks" in tables:
                # Check for tasks
                total_tasks = conn.execute(
                    text("SELECT COUNT(*) FROM tasks")
                ).scalar() or 0
                state.has_features = total_tasks > 0

                if state.has_features:
                    # Check pending/in-progress
                    pending = conn.execute(
                        text("SELECT COUNT(*) FROM tasks WHERE passes = 0 AND in_progress = 0 AND is_blocked = 0")
                    ).scalar() or 0
                    in_progress = conn.execute(
                        text("SELECT COUNT(*) FROM tasks WHERE in_progress = 1")
                    ).scalar() or 0

                    state.has_pending_tasks = pending > 0
                    state.has_in_progress_tasks = in_progress > 0

                    # Check for completed but unreviewed tasks
                    unreviewed = conn.execute(
                        text("SELECT COUNT(*) FROM tasks WHERE passes = 1 AND reviewed = 0")
                    ).scalar() or 0
                    state.tasks_needing_review = unreviewed
                    state.has_completed_unreviewed = unreviewed > 0

                    # For testing, we'd check a 'tested' or 'verified' column
                    # For now, we'll use reviewed as a proxy
                    state.tasks_needing_testing = unreviewed
                    state.has_completed_untested = unreviewed > 0

                    # Check if current phase is complete
                    if "phases" in tables:
                        current_phase = conn.execute(
                            text("""
                                SELECT p.id,
                                       (SELECT COUNT(*) FROM tasks t
                                        JOIN features_v2 f ON t.feature_id = f.id
                                        WHERE f.phase_id = p.id AND t.passes = 0) as pending
                                FROM phases p
                                WHERE p.status = 'in_progress'
                                ORDER BY p.order
                                LIMIT 1
                            """)
                        ).fetchone()
                        if current_phase and current_phase[1] == 0:
                            state.current_phase_complete = True

            # Handle legacy schema
            elif "features" in tables:
                total_features = conn.execute(
                    text("SELECT COUNT(*) FROM features")
                ).scalar() or 0
                state.has_features = total_features > 0

                if state.has_features:
                    pending = conn.execute(
                        text("SELECT COUNT(*) FROM features WHERE passes = 0 AND in_progress = 0")
                    ).scalar() or 0
                    in_progress = conn.execute(
                        text("SELECT COUNT(*) FROM features WHERE in_progress = 1")
                    ).scalar() or 0

                    state.has_pending_tasks = pending > 0
                    state.has_in_progress_tasks = in_progress > 0

    except Exception as e:
        print(f"Warning: Could not analyze project state: {e}")

    return state


def determine_agent_type(
    project_dir: Path,
    force_type: Optional[AgentType] = None,
    enable_multi_agent: bool = True,
    review_threshold: int = 5,
) -> AgentType:
    """
    Determine which agent type should run for a project.

    Selection Logic:
    1. If force_type is specified, use that
    2. If no architecture.md exists, run ARCHITECT
    3. If no features exist, run INITIALIZER
    4. If enable_multi_agent and enough tasks need review, run REVIEWER
    5. If enable_multi_agent and enough tasks need testing, run TESTING
    6. Otherwise, run CODING agent

    Args:
        project_dir: Path to the project directory
        force_type: Optional agent type to force (overrides logic)
        enable_multi_agent: Whether to enable reviewer/testing agents
        review_threshold: Number of unreviewed tasks before triggering review

    Returns:
        The AgentType that should run
    """
    # Force type overrides all logic
    if force_type:
        return force_type

    # Get current project state
    state = get_project_state(project_dir)

    # No architecture yet - run architect first
    if not state.has_architecture and not state.has_features:
        return AgentType.ARCHITECT

    # No features yet - run initializer
    if not state.has_features:
        return AgentType.INITIALIZER

    # Multi-agent mode logic
    if enable_multi_agent:
        # If a phase is complete and has unreviewed tasks, prioritize review
        if state.current_phase_complete and state.has_completed_unreviewed:
            return AgentType.REVIEWER

        # If enough tasks need review, run reviewer
        if state.tasks_needing_review >= review_threshold:
            return AgentType.REVIEWER

        # Periodically run testing (could be based on different criteria)
        # For now, testing runs when reviewer would but we alternate
        # This is a simple heuristic - could be more sophisticated

    # Default: run coding agent
    return AgentType.CODING


def get_agent_prompt_name(agent_type: AgentType) -> str:
    """
    Get the prompt template name for an agent type.

    Args:
        agent_type: The type of agent

    Returns:
        The prompt template name (without extension)
    """
    prompt_names = {
        AgentType.ARCHITECT: "architect_prompt",
        AgentType.INITIALIZER: "initializer_prompt",
        AgentType.CODING: "coding_prompt",
        AgentType.REVIEWER: "reviewer_prompt",
        AgentType.TESTING: "testing_prompt",
    }
    return prompt_names[agent_type]


def get_agent_description(agent_type: AgentType) -> str:
    """
    Get a human-readable description of an agent type.

    Args:
        agent_type: The type of agent

    Returns:
        Description string
    """
    descriptions = {
        AgentType.ARCHITECT: "Architect Agent - Designing system architecture",
        AgentType.INITIALIZER: "Initializer Agent - Creating features from specification",
        AgentType.CODING: "Coding Agent - Implementing features",
        AgentType.REVIEWER: "Reviewer Agent - Reviewing code quality",
        AgentType.TESTING: "Testing Agent - Running tests and verification",
    }
    return descriptions[agent_type]


class AgentOrchestrator:
    """
    Orchestrates multi-agent sessions for a project.

    The orchestrator manages the flow between different agent types,
    ensuring proper handoffs and shared context.
    """

    def __init__(
        self,
        project_dir: Path,
        enable_multi_agent: bool = True,
        review_threshold: int = 5,
    ):
        """
        Initialize the orchestrator.

        Args:
            project_dir: Path to the project directory
            enable_multi_agent: Whether to enable multi-agent mode
            review_threshold: Tasks needed before triggering review
        """
        self.project_dir = project_dir
        self.enable_multi_agent = enable_multi_agent
        self.review_threshold = review_threshold
        self._current_agent: Optional[AgentType] = None
        self._session_count: dict[AgentType, int] = {t: 0 for t in AgentType}

    def get_next_agent(self, force_type: Optional[AgentType] = None) -> AgentType:
        """
        Determine the next agent to run.

        Args:
            force_type: Optional agent type to force

        Returns:
            The next AgentType to run
        """
        agent_type = determine_agent_type(
            self.project_dir,
            force_type=force_type,
            enable_multi_agent=self.enable_multi_agent,
            review_threshold=self.review_threshold,
        )
        self._current_agent = agent_type
        return agent_type

    def record_session(self, agent_type: AgentType) -> None:
        """Record that a session was run for an agent type."""
        self._session_count[agent_type] += 1

    def get_session_counts(self) -> dict[AgentType, int]:
        """Get the count of sessions run for each agent type."""
        return self._session_count.copy()

    @property
    def current_agent(self) -> Optional[AgentType]:
        """Get the currently selected agent type."""
        return self._current_agent

    def get_shared_context_path(self) -> Path:
        """Get the path to the shared context file for inter-agent communication."""
        return self.project_dir / ".agent_context.json"

    def get_progress_file_path(self) -> Path:
        """Get the path to the progress tracking file."""
        return self.project_dir / "claude-progress.txt"
