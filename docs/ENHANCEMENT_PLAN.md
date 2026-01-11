# Autocoder Enhancement Plan

## Overview

This document outlines a comprehensive redesign of the Autocoder system to support:
1. **Hierarchical structure**: Projects → Phases → Features → Tasks
2. **Renamed terminology**: "Features" become "Tasks", new "Features" concept added
3. **Phase-based workflows** with approval gates
4. **Drill-down UI** for project navigation
5. **Usage monitoring** with smart task prioritization

---

## 1. New Terminology & Hierarchy

### Current Model (Flat)
```
Project
  └── Features (flat list, 200+ items)
```

### Proposed Model (Hierarchical)
```
Project
  └── Phases (major milestones)
        └── Features (major work items requiring spec)
              └── Tasks (actionable items the agent works on)
```

### Terminology Changes

| Old Term | New Term | Description |
|----------|----------|-------------|
| Feature | **Task** | Small, actionable item the agent completes |
| (new) | **Feature** | Major work item that triggers spec creation |
| (new) | **Phase** | Collection of features representing a milestone |

---

## 2. New Database Schema

### File: `api/database.py`

```python
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from datetime import datetime

Base = declarative_base()


class Phase(Base):
    """Phase represents a major milestone in the project."""

    __tablename__ = "phases"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0)  # Sort order
    status = Column(String(50), default="pending")  # pending, in_progress, awaiting_approval, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    features = relationship("Feature", back_populates="phase", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "project_name": self.project_name,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "feature_count": len(self.features) if self.features else 0,
        }


class Feature(Base):
    """Feature represents a major work item requiring spec creation."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey("phases.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    spec = Column(Text, nullable=True)  # Generated spec for this feature
    status = Column(String(50), default="pending")  # pending, speccing, ready, in_progress, completed
    priority = Column(Integer, default=0)
    agent_id = Column(String(100), nullable=True)  # Which agent is assigned
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    phase = relationship("Phase", back_populates="features")
    tasks = relationship("Task", back_populates="feature", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "phase_id": self.phase_id,
            "name": self.name,
            "description": self.description,
            "spec": self.spec,
            "status": self.status,
            "priority": self.priority,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "task_count": len(self.tasks) if self.tasks else 0,
            "tasks_completed": sum(1 for t in self.tasks if t.passes) if self.tasks else 0,
        }


class Task(Base):
    """Task represents an actionable item the agent works on (formerly 'Feature')."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)
    estimated_complexity = Column(Integer, default=1)  # 1-5 scale for usage estimation

    # Relationships
    feature = relationship("Feature", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
            "estimated_complexity": self.estimated_complexity,
        }


class UsageLog(Base):
    """Track Claude API usage for monitoring and smart scheduling."""

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    task_id = Column(Integer, nullable=True)  # Which task triggered this
    session_id = Column(String(100), nullable=True)  # Agent session

    def to_dict(self):
        return {
            "id": self.id,
            "project_name": self.project_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "task_id": self.task_id,
        }
```

---

## 3. Phase-Based Workflow

### Phase Statuses

```
pending → in_progress → awaiting_approval → completed
    ↑                         │
    └─────── rejected ────────┘
```

### Workflow Description

1. **pending**: Phase not started yet
2. **in_progress**: Agent actively working on tasks in this phase
3. **awaiting_approval**: All tasks complete, waiting for user to review
4. **completed**: User approved, ready to move to next phase

### Agent Notification System

When a phase completes, the agent will:

```python
# In agent.py - after marking last task passing
def check_phase_completion(project_dir: Path, feature_id: int):
    """Check if completing this task finishes a phase."""
    # Get the feature and its phase
    feature = get_feature(feature_id)
    if not feature.phase_id:
        return

    phase = get_phase(feature.phase_id)

    # Check if all tasks in this phase's features are complete
    all_complete = all(
        task.passes
        for f in phase.features
        for task in f.tasks
    )

    if all_complete:
        # Update phase status
        phase.status = "awaiting_approval"

        # Notify user
        print(f"\n{'='*60}")
        print(f"PHASE COMPLETE: {phase.name}")
        print(f"{'='*60}")
        print(f"All tasks in this phase have been completed.")
        print(f"Please review and approve to continue to the next phase.")
        print(f"{'='*60}\n")

        # Send webhook notification if configured
        notify_phase_complete(phase)

        # Agent should pause and wait for approval
        return "pause_for_approval"
```

---

## 4. Drill-Down UI Architecture

### Navigation Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTOCODER                                    [Usage: 75%] ⚡   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Breadcrumb: Projects > MyApp > Phase 1: Foundation > Auth      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │   CURRENT VIEW (contextual based on drill level)        │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### View Levels

#### Level 1: Projects List
```
┌────────────────────────────────────────────────────────────┐
│ MY PROJECTS                                    [+ New]     │
├────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│ │ E-Commerce   │ │ Blog Engine  │ │ Dashboard    │        │
│ │              │ │              │ │              │        │
│ │ Phase 2/4    │ │ Phase 1/3    │ │ Completed    │        │
│ │ ████████░░   │ │ ██░░░░░░░░   │ │ ██████████   │        │
│ │ 45/60 tasks  │ │ 12/80 tasks  │ │ 120/120      │        │
│ │              │ │              │ │              │        │
│ │ [▶ Resume]   │ │ [▶ Start]    │ │ [View]       │        │
│ └──────────────┘ └──────────────┘ └──────────────┘        │
└────────────────────────────────────────────────────────────┘
```

#### Level 2: Project Phases (Timeline View)
```
┌────────────────────────────────────────────────────────────────┐
│ E-COMMERCE APP                                 [+ Add Phase]   │
│ ← Back to Projects                                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Phase 1          Phase 2          Phase 3          Phase 4    │
│  Foundation       Core Features    Polish            Launch    │
│  ✓ COMPLETED      ▶ IN PROGRESS   ○ PENDING         ○ PENDING │
│                                                                │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌───────┐ │
│  │ Auth    │      │ Cart    │      │ Search  │      │ Deploy│ │
│  │ ✓ Done  │      │ ▶ 3/10  │      │ ○ 0/8   │      │ ○ 0/5 │ │
│  ├─────────┤      ├─────────┤      ├─────────┤      ├───────┤ │
│  │ Users   │      │ Payment │      │ Reviews │      │ Docs  │ │
│  │ ✓ Done  │      │ ○ 0/12  │      │ ○ 0/6   │      │ ○ 0/3 │ │
│  ├─────────┤      ├─────────┤      └─────────┘      └───────┘ │
│  │ Products│      │ Orders  │                                  │
│  │ ✓ Done  │      │ ○ 0/15  │                                  │
│  └─────────┘      └─────────┘                                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

#### Level 3: Feature Tasks (Kanban View)
```
┌────────────────────────────────────────────────────────────────┐
│ FEATURE: Shopping Cart                         [+ Add Task]    │
│ ← Phase 2: Core Features                                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  PENDING (5)         IN PROGRESS (2)        DONE (3)          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │ Add to cart  │   │ Cart persist │   │ Cart UI      │       │
│  │ button       │   │ to storage   │   │ component    │       │
│  │              │   │              │   │              │       │
│  │ Steps: 4     │   │ Steps: 6     │   │ ✓ Passed     │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │ Remove item  │   │ Quantity     │   │ Cart icon    │       │
│  │              │   │ update       │   │ badge        │       │
│  │ Steps: 3     │   │ Steps: 5     │   │ ✓ Passed     │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│  ...               ...                  ...                    │
└────────────────────────────────────────────────────────────────┘
```

### New React Components

```
ui/src/components/
├── navigation/
│   ├── Breadcrumb.tsx           # Navigation breadcrumb
│   └── DrillDownContainer.tsx   # Container managing navigation state
│
├── projects/
│   ├── ProjectGrid.tsx          # Level 1: Project cards
│   └── ProjectCard.tsx          # Individual project summary
│
├── phases/
│   ├── PhaseTimeline.tsx        # Level 2: Phase timeline view
│   ├── PhaseCard.tsx            # Individual phase card
│   ├── PhaseApprovalModal.tsx   # Approval dialog
│   └── AddPhaseModal.tsx        # Create new phase
│
├── features/
│   ├── FeatureList.tsx          # Features within a phase
│   ├── FeatureCard.tsx          # Individual feature card
│   ├── AddFeatureModal.tsx      # Create new feature (triggers spec)
│   └── FeatureSpecChat.tsx      # Spec creation for new feature
│
├── tasks/
│   ├── TaskKanban.tsx           # Level 3: Task kanban board
│   ├── TaskCard.tsx             # Individual task card
│   ├── TaskModal.tsx            # Task details
│   └── AddTaskForm.tsx          # Quick add task
│
└── usage/
    ├── UsageDashboard.tsx       # Usage monitoring panel
    ├── UsageChart.tsx           # Usage over time chart
    └── UsageWarning.tsx         # Low usage alert banner
```

---

## 5. Usage Monitoring System

### API Integration

The Claude API returns usage information in responses. We need to capture this:

```python
# In agent.py - after each API call
async def track_usage(response, project_name: str, task_id: int = None):
    """Track API usage from Claude response."""
    usage = response.usage

    log = UsageLog(
        project_name=project_name,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
        cache_write_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
        task_id=task_id,
        session_id=current_session_id,
    )

    db.add(log)
    db.commit()
```

### Usage Dashboard UI

```
┌────────────────────────────────────────────────────────────────┐
│ USAGE MONITOR                                                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Current Period: Jan 1 - Jan 31, 2025                         │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    TOKEN USAGE                          │  │
│  │                                                         │  │
│  │  ████████████████████████░░░░░░░░░░  75% Used          │  │
│  │  750,000 / 1,000,000 tokens                            │  │
│  │                                                         │  │
│  │  ⚠️ At current rate, limit reached in ~3 days          │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  Today's Usage: 45,230 tokens                                 │
│  Average/Day:   32,150 tokens                                 │
│  Remaining:     250,000 tokens                                │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  USAGE BY PROJECT                                       │  │
│  │                                                         │  │
│  │  E-Commerce    ████████████████  450,000 (60%)         │  │
│  │  Blog Engine   ████████          200,000 (27%)         │  │
│  │  Dashboard     ████              100,000 (13%)         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  [📊 Detailed Report]  [⚙️ Settings]                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Smart Task Prioritization

```python
# In agent.py - task selection logic
class SmartTaskScheduler:
    """Schedules tasks based on usage and complexity."""

    THRESHOLDS = {
        "critical": 0.05,   # 5% remaining - stop new tasks
        "low": 0.10,        # 10% remaining - only simple tasks
        "moderate": 0.25,   # 25% remaining - prioritize completion
    }

    def get_next_task(self, project_dir: Path) -> Task | None:
        """Get the next task considering usage constraints."""
        usage_remaining = self.get_remaining_usage_percentage()

        if usage_remaining <= self.THRESHOLDS["critical"]:
            # Don't start any new tasks - let current ones complete
            logger.warning(
                f"Usage critical ({usage_remaining:.1%}). "
                "Not starting new tasks."
            )
            return None

        if usage_remaining <= self.THRESHOLDS["low"]:
            # Only get simple tasks (complexity 1-2)
            return self._get_simple_task(project_dir)

        if usage_remaining <= self.THRESHOLDS["moderate"]:
            # Prioritize tasks that are close to completion
            # or that complete a feature/phase
            return self._get_completion_priority_task(project_dir)

        # Normal operation - get highest priority task
        return self._get_highest_priority_task(project_dir)

    def _get_simple_task(self, project_dir: Path) -> Task | None:
        """Get a low-complexity task."""
        return db.query(Task).filter(
            Task.passes == False,
            Task.in_progress == False,
            Task.estimated_complexity <= 2,
        ).order_by(Task.priority).first()

    def _get_completion_priority_task(self, project_dir: Path) -> Task | None:
        """Get a task that would complete a feature or phase."""
        # Find features with only 1-2 tasks remaining
        for feature in db.query(Feature).filter(Feature.status == "in_progress"):
            remaining = [t for t in feature.tasks if not t.passes]
            if len(remaining) <= 2:
                # Prioritize completing this feature
                return remaining[0] if remaining else None

        # Fall back to normal priority
        return self._get_highest_priority_task(project_dir)
```

### Usage Settings

```python
# New config in server/config.py
USAGE_CONFIG = {
    "monthly_limit": 1_000_000,  # Token limit (can be set by user)
    "warn_at_percentage": 0.20,  # Show warning at 20% remaining
    "pause_at_percentage": 0.05, # Auto-pause at 5% remaining
    "reset_day": 1,              # Day of month when usage resets
    "track_by": "project",       # "project" or "global"
}
```

---

## 6. New API Endpoints

### Phases API

```
GET    /api/projects/{name}/phases              # List all phases
POST   /api/projects/{name}/phases              # Create phase
GET    /api/projects/{name}/phases/{id}         # Get phase details
PUT    /api/projects/{name}/phases/{id}         # Update phase
DELETE /api/projects/{name}/phases/{id}         # Delete phase
POST   /api/projects/{name}/phases/{id}/approve # Approve phase completion
POST   /api/projects/{name}/phases/{id}/reject  # Reject, return to in_progress
```

### Features API (Enhanced)

```
GET    /api/projects/{name}/features                    # List all features
GET    /api/projects/{name}/phases/{phase_id}/features  # Features in phase
POST   /api/projects/{name}/features                    # Create feature (triggers spec)
GET    /api/projects/{name}/features/{id}               # Get feature details
PUT    /api/projects/{name}/features/{id}               # Update feature
DELETE /api/projects/{name}/features/{id}               # Delete feature
POST   /api/projects/{name}/features/{id}/assign        # Assign to agent
```

### Tasks API (Renamed from Features)

```
GET    /api/projects/{name}/tasks                       # List all tasks
GET    /api/projects/{name}/features/{feature_id}/tasks # Tasks in feature
POST   /api/projects/{name}/tasks                       # Create task (simple add)
GET    /api/projects/{name}/tasks/{id}                  # Get task details
PATCH  /api/projects/{name}/tasks/{id}                  # Update task
DELETE /api/projects/{name}/tasks/{id}                  # Delete task
PATCH  /api/projects/{name}/tasks/{id}/skip             # Skip task
```

### Usage API

```
GET    /api/usage                              # Global usage stats
GET    /api/usage/projects/{name}              # Project-specific usage
GET    /api/usage/history                      # Usage over time
GET    /api/usage/settings                     # Get usage settings
PUT    /api/usage/settings                     # Update usage settings
```

---

## 7. New MCP Tools

### Phase Management Tools

```python
@server.tool()
async def phase_get_current() -> dict:
    """Get the currently active phase."""

@server.tool()
async def phase_mark_complete(phase_id: int) -> dict:
    """Mark a phase as ready for approval."""

@server.tool()
async def phase_check_status(phase_id: int) -> dict:
    """Check if all features in a phase are complete."""
```

### Feature Management Tools

```python
@server.tool()
async def feature_create(
    phase_id: int,
    name: str,
    description: str,
) -> dict:
    """Create a new feature (triggers spec creation workflow)."""

@server.tool()
async def feature_get_spec(feature_id: int) -> dict:
    """Get the spec for a feature."""

@server.tool()
async def feature_create_tasks(
    feature_id: int,
    tasks: list[dict],
) -> dict:
    """Create tasks for a feature (used after spec generation)."""
```

### Task Management Tools (Renamed)

```python
@server.tool()
async def task_get_next() -> dict:
    """Get the highest priority pending task."""

@server.tool()
async def task_mark_passing(task_id: int) -> dict:
    """Mark a task as complete/passing."""

@server.tool()
async def task_get_for_regression(limit: int = 3) -> list[dict]:
    """Get random passing tasks for regression testing."""
```

### Usage Tools

```python
@server.tool()
async def usage_get_remaining() -> dict:
    """Get remaining usage for current period."""

@server.tool()
async def usage_should_continue() -> dict:
    """Check if agent should continue or pause for usage limits."""
```

---

## 8. Migration Strategy

### Database Migration

```python
# api/migrations/001_add_phases_and_rename.py

def upgrade(engine):
    """Migrate from flat features to hierarchical structure."""

    # 1. Create new tables
    create_table("phases")
    create_table("usage_logs")

    # 2. Rename features table to tasks
    rename_table("features", "tasks")

    # 3. Create new features table
    create_table("features")

    # 4. Add foreign keys to tasks
    add_column("tasks", "feature_id", Integer, nullable=True)

    # 5. Create default phase and feature for existing tasks
    create_default_phase_and_feature()

def create_default_phase_and_feature():
    """Wrap existing tasks in a default feature and phase."""

    # Create "Phase 1: Initial Development" for each project
    # Create "Core Features" feature within it
    # Link all existing tasks to this feature
    pass
```

### UI Migration

The React app can be updated incrementally:

1. **Phase 1**: Add new types and API client methods
2. **Phase 2**: Add navigation components (Breadcrumb, DrillDownContainer)
3. **Phase 3**: Build new phase/feature views
4. **Phase 4**: Rename components (Feature → Task)
5. **Phase 5**: Add usage monitoring
6. **Phase 6**: Wire everything together

---

## 9. Multi-Agent Support

### Agent Assignment

Features can be assigned to different agents:

```python
class AgentManager:
    """Manages multiple agents working on a project."""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.agents: dict[str, AgentProcessManager] = {}

    def assign_feature(self, feature_id: int, agent_id: str = None):
        """Assign a feature to an agent."""
        if agent_id is None:
            agent_id = self._create_new_agent()

        feature = get_feature(feature_id)
        feature.agent_id = agent_id

        # Start the agent if not running
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentProcessManager(
                project_name=self.project_name,
                project_dir=self.project_dir,
                agent_id=agent_id,
            )

    def can_run_independently(self, feature: Feature) -> bool:
        """Check if a feature can run on its own agent."""
        # Features in the same phase might have dependencies
        # Features in different phases should be sequential
        # Features with no task overlap can run in parallel
        pass
```

### Agent Communication

```python
# Agents communicate via shared database
# Each agent has its own scope (feature_id filter)

# In task selection:
def get_next_task_for_agent(agent_id: str) -> Task | None:
    """Get next task scoped to this agent's assigned features."""
    assigned_features = db.query(Feature).filter(
        Feature.agent_id == agent_id
    ).all()

    feature_ids = [f.id for f in assigned_features]

    return db.query(Task).filter(
        Task.feature_id.in_(feature_ids),
        Task.passes == False,
        Task.in_progress == False,
    ).order_by(Task.priority).first()
```

---

## 10. Implementation Roadmap

### Milestone 1: Database & API Foundation
- [ ] Create new database models (Phase, enhanced Feature, Task, UsageLog)
- [ ] Write migration script for existing data
- [ ] Implement new API endpoints
- [ ] Update MCP tools with new terminology

### Milestone 2: Phase Management
- [ ] Add phase CRUD operations
- [ ] Implement phase status workflow
- [ ] Add approval gates
- [ ] Update agent to respect phase boundaries

### Milestone 3: Drill-Down UI
- [ ] Add navigation components (Breadcrumb, DrillDownContainer)
- [ ] Build ProjectGrid view
- [ ] Build PhaseTimeline view
- [ ] Rename Kanban components (Feature → Task)

### Milestone 4: Usage Monitoring
- [ ] Implement usage tracking in agent
- [ ] Create UsageDashboard component
- [ ] Add smart task scheduler
- [ ] Add usage warnings/alerts

### Milestone 5: Multi-Agent Support
- [ ] Implement AgentManager for multiple agents
- [ ] Add feature assignment logic
- [ ] Update UI for multi-agent visibility
- [ ] Add agent-scoped task selection

### Milestone 6: Polish & Integration
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation updates
- [ ] Migration guide for existing projects

---

## Appendix: TypeScript Types Update

```typescript
// ui/src/lib/types.ts - New types

// Phase types
export type PhaseStatus = 'pending' | 'in_progress' | 'awaiting_approval' | 'completed'

export interface Phase {
  id: number
  project_name: string
  name: string
  description: string | null
  order: number
  status: PhaseStatus
  created_at: string | null
  completed_at: string | null
  feature_count: number
}

// Feature types (new concept)
export type FeatureStatus = 'pending' | 'speccing' | 'ready' | 'in_progress' | 'completed'

export interface Feature {
  id: number
  phase_id: number | null
  name: string
  description: string | null
  spec: string | null
  status: FeatureStatus
  priority: number
  agent_id: string | null
  created_at: string | null
  completed_at: string | null
  task_count: number
  tasks_completed: number
}

// Task types (renamed from Feature)
export interface Task {
  id: number
  feature_id: number | null
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
  estimated_complexity: number
}

export interface TaskListResponse {
  pending: Task[]
  in_progress: Task[]
  done: Task[]
}

// Usage types
export interface UsageStats {
  total_tokens: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
  limit: number
  remaining: number
  percentage_used: number
  reset_date: string
}

export interface UsageHistory {
  date: string
  tokens: number
}

// Navigation state
export type ViewLevel = 'projects' | 'phases' | 'features' | 'tasks'

export interface NavigationState {
  level: ViewLevel
  projectName: string | null
  phaseId: number | null
  featureId: number | null
}
```

---

This document provides a complete blueprint for implementing the enhanced Autocoder system with phases, hierarchical task management, and usage monitoring.
