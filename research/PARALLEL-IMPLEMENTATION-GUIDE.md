# Quick Start: Parallel Agents Implementation

## TL;DR - What We Found

Scanned 4 repositories. **3 have production-ready parallel execution** we can adopt:

| Repository | Parallel Pattern | Ready to Use? |
|------------|------------------|---------------|
| **claude-code-orchestrator** | DAG-based with dependencies | ✅ Yes (⭐ TOP PICK) |
| **scagent** | Multi-model virtual agents | ✅ Yes |
| **claude-bloom** | Evolutionary background processes | ⚠️ Experimental |
| AutoQA-Agent | Sequential only | ❌ No |

---

## 🚀 3-Hour Quick Start

### Step 1: Add Atomic Feature Claiming (45 min)

**File**: `mcp_server/feature_mcp.py`

```python
# Add these new tools
@tool
def feature_claim_batch(count: int = 1) -> list[dict]:
    """Atomically claim multiple features for parallel processing

    Returns list of claimed features with status set to "claimed"
    """
    with get_db() as db:
        features = db.query(Feature)\
            .filter_by(status="pending")\
            .order_by(Feature.priority.desc(), Feature.id)\
            .limit(count)\
            .with_for_update()\
            .all()

        for f in features:
            f.status = "claimed"
            f.claimed_at = datetime.utcnow()

        db.commit()
        return [{"id": f.id, "name": f.name, "description": f.description}
                for f in features]

@tool
def feature_release(feature_id: int, status: str, notes: str = ""):
    """Release a claimed feature with completion status

    Args:
        feature_id: Feature to release
        status: "passing", "failed", or "pending" (to retry)
        notes: Optional notes about implementation
    """
    with get_db() as db:
        feature = db.query(Feature).get(feature_id)
        feature.status = status
        feature.notes = notes
        feature.claimed_at = None
        db.commit()
```

### Step 2: Create Agent Manager (60 min)

**File**: `agent_manager.py` (new file)

```python
"""Orchestrates multiple autonomous agents working in parallel"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional
from api.database import Feature, get_db

class AgentManager:
    """Manages multiple agents working on features in parallel"""

    def __init__(self, project_dir: str, max_agents: int = 3):
        self.project_dir = project_dir
        self.max_agents = max_agents
        self.running_agents: Dict[int, asyncio.Task] = {}

    async def run_parallel(self):
        """Run features in parallel until complete"""
        while True:
            # Check if we have pending features
            pending_count = self._get_pending_count()
            if pending_count == 0:
                print("✅ All features completed!")
                break

            # Calculate how many agents to spawn
                available_slots = self.max_agents - len(self.running_agents)
                if available_slots <= 0:
                    await asyncio.sleep(5)
                    continue

                # Claim batch of features
                to_claim = min(available_slots, pending_count)
                features = self._claim_features(to_claim)

                if not features:
                    await asyncio.sleep(5)
                    continue

                # Spawn agents for each feature
                for feature in features:
                    task = asyncio.create_task(
                        self._run_feature_agent(feature)
                    )
                    self.running_agents[feature['id']] = task
                    print(f"🚀 Agent {len(self.running_agents)}/{self.max_agents}: "
                          f"Started feature {feature['id']} - {feature['name']}")

            # Check for completed agents
            await self._cleanup_completed()

    async def _run_feature_agent(self, feature: dict):
        """Run a single agent for one feature"""
        try:
            # Import here to avoid circular dependency
            from autonomous_agent_demo import run_single_feature

            # Run the agent
            result = await run_single_feature(
                project_dir=self.project_dir,
                feature_id=feature['id']
            )

            # Release feature
            status = "passing" if result['success'] else "failed"
            self._release_feature(feature['id'], status, result.get('notes', ''))
            print(f"✅ Feature {feature['id']} completed: {status}")

        except Exception as e:
            print(f"❌ Feature {feature['id']} failed: {str(e)}")
            self._release_feature(feature['id'], "failed", str(e))

    async def _cleanup_completed(self):
        """Remove completed agents from tracking"""
        completed = []
        for feature_id, task in self.running_agents.items():
            if task.done():
                completed.append(feature_id)

        for feature_id in completed:
            del self.running_agents[feature_id]

        if completed:
            print(f"🧹 Cleaned up {len(completed)} completed agents")

    def _get_pending_count(self) -> int:
        """Get count of pending features"""
        with get_db(self.project_dir) as db:
            return db.query(Feature)\
                .filter_by(status="pending")\
                .count()

    def _claim_features(self, count: int) -> List[dict]:
        """Claim features from database"""
        # This would call the MCP tool
        # For now, direct DB access
        with get_db(self.project_dir) as db:
            features = db.query(Feature)\
                .filter_by(status="pending")\
                .order_by(Feature.priority.desc(), Feature.id)\
                .limit(count)\
                .all()

            for f in features:
                f.status = "claimed"

            db.commit()
            return [{"id": f.id, "name": f.name, "description": f.description}
                    for f in features]

    def _release_feature(self, feature_id: int, status: str, notes: str = ""):
        """Release a claimed feature"""
        with get_db(self.project_dir) as db:
            feature = db.query(Feature).get(feature_id)
            if feature:
                feature.status = status
                feature.notes = notes
                db.commit()

# CLI entry point
async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--max-agents", type=int, default=3)
    args = parser.parse_args()

    manager = AgentManager(args.project_dir, args.max_agents)
    await manager.run_parallel()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Add Multi-Model Support (30 min)

**File**: `client.py`

```python
# Add to ClaudeSDKClient class
MODEL_MAPPING = {
    "testing": "haiku",      # Cheap for tests
    "documentation": "haiku",  # Simple docs
    "frontend": "sonnet",     # Balanced
    "backend": "sonnet",      # Balanced
    "database": "sonnet",     # Balanced
    "default": "sonnet"
}

def get_model_for_task(self, task_type: str) -> str:
    """Get optimal model for task type"""
    return self.MODEL_MAPPING.get(task_type, self.MODEL_MAPPING["default"])

def get_model_for_feature(self, feature: dict) -> str:
    """Get optimal model based on feature category"""
    category = feature.get("category", "default").lower()
    return self.get_model_for_task(category)
```

### Step 4: Add File Locking (45 min)

**File**: `mcp_server/coordination_mcp.py` (new file)

```python
"""MCP server for coordinating parallel agents"""

from threading import Lock
from typing import Dict

class FileCoordinator:
    """Prevents concurrent file modification conflicts"""

    def __init__(self):
        self.locks: Dict[str, Lock] = {}
        self.claims: Dict[str, str] = {}  # file_path -> agent_id

    def acquire_lock(self, file_path: str, agent_id: str) -> bool:
        """Try to acquire exclusive lock on file

        Returns True if successful, False if file already claimed
        """
        if file_path in self.claims:
            if self.claims[file_path] != agent_id:
                return False  # Already claimed by another agent

        # Create lock if needed
        if file_path not in self.locks:
            self.locks[file_path] = Lock()

        self.claims[file_path] = agent_id
        return True

    def release_lock(self, file_path: str, agent_id: str):
        """Release lock on file"""
        if self.claims.get(file_path) == agent_id:
            del self.claims[file_path]

# Global instance
_file_coordinator = FileCoordinator()

# MCP tools
@mcp_tool
def claim_file(file_path: str, agent_id: str) -> dict:
    """Claim exclusive access to a file

    Returns: {"success": bool, "message": str}
    """
    if _file_coordinator.acquire_lock(file_path, agent_id):
        return {"success": True, "message": f"Claimed {file_path}"}
    else:
        current_owner = _file_coordinator.claims.get(file_path, "unknown")
        return {"success": False,
                "message": f"File already claimed by agent {current_owner}"}

@mcp_tool
def release_file(file_path: str, agent_id: str):
    """Release claimed file"""
    _file_coordinator.release_lock(file_path, agent_id)
    return {"success": True, "message": f"Released {file_path}"}
```

---

## Testing

### Create Test Project

```bash
# Create simple test project
mkdir test-parallel
cd test-parallel

# Initialize with independent features
cat > features.json <<EOF
[
  {"name": "Feature 1", "category": "frontend", "priority": 1},
  {"name": "Feature 2", "category": "backend", "priority": 1},
  {"name": "Feature 3", "category": "database", "priority": 1},
  {"name": "Feature 4", "category": "frontend", "priority": 2},
  {"name": "Feature 5", "category": "backend", "priority": 2}
]
EOF

# Run with 3 parallel agents
python agent_manager.py --project-dir . --max-agents 3
```

### Expected Output

```
🚀 Agent 1/3: Started feature 1 - Feature 1
🚀 Agent 2/3: Started feature 2 - Feature 2
🚀 Agent 3/3: Started feature 3 - Feature 3
✅ Feature 1 completed: passing
🚀 Agent 1/3: Started feature 4 - Feature 4
✅ Feature 2 completed: passing
🚀 Agent 2/3: Started feature 5 - Feature 5
✅ Feature 3 completed: passing
✅ Feature 4 completed: passing
✅ Feature 5 completed: passing
🧹 Cleaned up 3 completed agents
✅ All features completed!
```

---

## UI Integration

### Update `ui/src/App.tsx`

```tsx
// Add parallel agent control
const [parallelAgents, setParallelAgents] = useState(1);

// In controls section
<div className="parallel-control">
  <label>Parallel Agents:</label>
  <input
    type="range"
    min="1"
    max="5"
    value={parallelAgents}
    onChange={(e) => setParallelAgents(parseInt(e.target.value))}
  />
  <span>{parallelAgents}</span>
</div>

// Update start button
<Button onClick={() => startAgents(parallelAgents)}>
  Start {parallelAgents} Agent{parallelAgents > 1 ? 's' : ''}
</Button>

// Add agent status panel
{agentStatuses.map((agent) => (
  <AgentCard key={agent.id}>
    <AgentHeader>Agent {agent.id}</AgentHeader>
    <FeatureName>{agent.feature}</FeatureName>
    <Status status={agent.status}>{agent.status}</Status>
    <LogOutput>{agent.logs}</LogOutput>
  </AgentCard>
))}
```

---

## Performance Expectations

### Sequential (Current)
```
Feature 1 (10 min) → Feature 2 (10 min) → Feature 3 (10 min) = 30 min
```

### Parallel with 3 Agents
```
Agent 1: Feature 1 (10 min) ┐
Agent 2: Feature 2 (10 min) ├> = 10 min (3x faster!)
Agent 3: Feature 3 (10 min) ┘
```

### Real-World Expectations

| Project Size | Features | Sequential | 3 Agents | Speedup |
|--------------|----------|------------|----------|---------|
| Small | 5 | 50 min | 20 min | 2.5x |
| Medium | 15 | 150 min | 60 min | 2.5x |
| Large | 30 | 300 min | 120 min | 2.5x |

**Note**: Actual speedup depends on feature independence. Highly coupled features will have less benefit.

---

## Safety Features

### Prevent Race Conditions

```python
# Atomic database operations
with get_db() as db:
    features = db.query(Feature)\
        .filter_by(status="pending")\
        .with_for_update()\
        .all()
    # Automatically locked by transaction
```

### Prevent File Conflicts

```python
# File claiming before editing
claim_result = claim_file("/src/App.tsx", agent_id="agent-1")
if not claim_result["success"]:
    # Wait or choose different file
    await asyncio.sleep(1)
```

### Prevent Resource Exhaustion

```python
# Limit max agents
MAX_AGENTS = os.getenv("MAX_AGENTS", "3")

# Memory limits
ulimit -v 2097152  # 2GB per agent

# Timeouts
TIMEOUT = {
    "haiku": 600,
    "sonnet": 1800,
    "opus": 3600
}
```

---

## Monitoring

### Add to Progress Tracking

**File**: `progress.py`

```python
class ParallelAgentTracker:
    def __init__(self):
        self.agents: Dict[str, AgentStatus] = {}

    def register_agent(self, agent_id: str, feature_id: int):
        self.agents[agent_id] = {
            "feature_id": feature_id,
            "started_at": datetime.utcnow(),
            "status": "running",
            "progress": 0
        }

    def update_progress(self, agent_id: str, progress: int):
        self.agents[agent_id]["progress"] = progress
        self._broadcast_update()

    def complete_agent(self, agent_id: str, status: str):
        self.agents[agent_id]["status"] = status
        self.agents[agent_id]["completed_at"] = datetime.utcnow()
        self._broadcast_update()

    def _broadcast_update(self):
        """Send update via WebSocket to UI"""
        websocket_manager.broadcast({
            "type": "agent_status_update",
            "agents": self.agents
        })
```

---

## Rollback Plan

If parallel execution causes issues:

```bash
# Fall back to sequential mode
python autonomous_agent_demo.py --project-dir my-app --parallel 1

# Or disable entirely in UI
# Settings → Advanced → Parallel Agents: Off
```

---

## Next Steps

1. ✅ Implement atomic feature claiming (45 min)
2. ✅ Create agent manager (60 min)
3. ✅ Add multi-model support (30 min)
4. ✅ Add file locking (45 min)
5. ✅ Test with simple project (30 min)
6. ⬜ Measure performance improvement
7. ⬜ Add dependency graph support (from claude-code-orchestrator)
8. ⬜ Add knowledge base learning (from scagent)
9. ⬜ UI integration for parallel monitoring

**Total Time to MVP**: 3-4 hours for basic parallel execution

---

## Questions?

Key decisions you need to make:

1. **Max Agents**: Start with 3, scale up to 5 based on testing
2. **Dependency Detection**: Manual (add `depends_on` field) or automatic (AI analysis)?
3. **UI Priority**: Quick status display or detailed per-agent logs?
4. **Model Selection**: Conservative (Sonnet for all) or aggressive (Haiku where possible)?

**Recommendation**: Start simple, iterate based on results.
