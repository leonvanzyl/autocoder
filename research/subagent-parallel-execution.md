# Parallel Subagent Execution Research

## Overview

Research into using multiple Claude Code subagents to work on different aspects of a project simultaneously, reducing total development time.

## Key Findings

### 1. **Parallel Execution is Supported**

Multiple Task tool calls in a single message execute **in parallel**:

```python
# In agent.py or prompts.py
# Multiple independent agents can be spawned simultaneously
result1 = Task(subagent_type="general-purpose", prompt="Build feature A", ...)
result2 = Task(subagent_type="general-purpose", prompt="Build feature B", ...)
result3 = Task(subagent_type="general-purpose", prompt="Build feature C", ...)
# All three run concurrently
```

### 2. **Coordination Mechanisms**

To prevent conflicts when working on the same codebase, use:

#### A. Database-Based Coordination (Recommended for Autocoder)
```python
# Features database already exists!
# agents can claim features via MCP server
- feature_claim(feature_id) - Mark feature as "in_progress" by agent
- feature_release(feature_id, status) - Mark feature as completed/failed
- feature_get_next() - Atomic operation to get next unclaimed feature
```

#### B. File-Based Locking
```python
# .agent.lock already exists in project
# Could extend to support multiple agents:
# .agent.locks/
#   - agent_1.lock (working on feature 5)
#   - agent_2.lock (working on feature 7)
```

#### C. MCP Server for Coordination
Create new MCP server: `mcp_server/coordination_mcp.py`
```python
tools = {
  "claim_feature": "Atomically claim a feature from the queue",
  "release_feature": "Mark feature as completed/failed",
  "get_agent_status": "Get what other agents are working on",
  "register_agent": "Register a new agent instance"
}
```

### 3. **Specialized Agent Types**

Different agents for different tasks:

```python
agents = {
  'feature-builder': {
    'description': 'Implements features one at a time',
    'tools': ['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep'],
    'model': 'sonnet'
  },
  'test-runner': {
    'description': 'Runs tests and validates features',
    'tools': ['Read', 'Bash', 'Grep'],
    'model': 'haiku'  # Faster for test runs
  },
  'code-reviewer': {
    'description': 'Reviews completed features for quality',
    'tools': ['Read', 'Grep', 'Glob'],
    'model': 'sonnet'
  },
  'ui-tester': {
    'description': 'Uses Playwright to test UI functionality',
    'tools': ['Read', 'Bash'],  # Playwright via Bash
    'model': 'sonnet'
  }
}
```

### 4. **Parallel Patterns for Autocoder**

#### Pattern 1: Feature-Level Parallelism
```python
# Main agent spawns N feature-builders
features = get_next_pending_features(count=3)
for feature in features:
    Task(
        subagent_type="feature-builder",
        prompt=f"Implement feature {feature['id']}: {feature['description']}",
        run_in_background=True
    )
# Monitor all agents, spawn more as they complete
```

#### Pattern 2: Pipeline Parallelism
```python
# Three specialized agents working together
Task(subagent_type="feature-builder", prompt="Build next feature")
Task(subagent_type="test-runner", prompt="Test completed features")
Task(subagent_type="code-reviewer", prompt="Review recent changes")
# Each runs independently on different features
```

#### Pattern 3: Component-Level Parallelism
```python
# For projects with clear separation
Task(subagent_type="frontend-builder", prompt="Build UI components")
Task(subagent_type="backend-builder", prompt="Build API endpoints")
Task(subagent_type="database-builder", prompt="Build database schema")
```

### 5. **Implementation Requirements**

#### Modify `mcp_server/feature_mcp.py`:
```python
# Add atomic claim mechanism
@tool
def feature_claim_batch(count: int = 1) -> list[Feature]:
    """Atomically claim multiple features for parallel processing"""
    with get_db() as db:
        features = db.query(Feature)\
            .filter_by(status="pending")\
            .order_by(Feature.priority.desc(), Feature.id)\
            .limit(count)\
            .all()
        for f in features:
            f.status = "in_progress"
            f.agent_id = current_agent_id()
        db.commit()
        return features

@tool
def feature_release(feature_id: int, status: str, notes: str = ""):
    """Release a feature with completion status"""
    with get_db() as db:
        feature = db.query(Feature).get(feature_id)
        feature.status = status  # "passing", "failed", "pending"
        feature.notes = notes
        feature.agent_id = None
        db.commit()
```

#### Modify `agent.py`:
```python
# Add parallel mode
PARALLEL_AGENTS = os.getenv("PARALLEL_AGENTS", "1")  # Default 1

async def session_loop():
    if PARALLEL_AGENTS == "1":
        # Current sequential behavior
        process_single_feature()
    else:
        # Parallel mode
        process_features_parallel(int(PARALLEL_AGENTS))

def process_features_parallel(num_agents: int):
    """Spawn N agents to work on features in parallel"""
    running_agents = []

    while has_pending_features():
        # Claim batch of features
        features = feature_claim_batch(num_agents)

        # Spawn agents for each feature
        for feature in features:
            agent = Task(
                subagent_type="feature-builder",
                prompt=f"Implement feature: {feature.description}",
                run_in_background=True
            )
            running_agents.append((agent, feature.id))

        # Monitor completion
        for agent, feature_id in running_agents:
            result = agent.wait_for_completion()
            feature_release(feature_id, result.status)

        running_agents.clear()
```

### 6. **UI Changes**

#### Add Parallel Mode Control (`ui/src/App.tsx`):
```tsx
<ParallelAgentControl>
  <Label>Number of Parallel Agents:</Label>
  <Slider min={1} max={5} value={parallelCount} onChange={setParallelCount} />
  <Toggle>YOLO Mode</Toggle>
  <Button onClick={startAgents}>
    Start {parallelCount} Agents
  </Button>
</ParallelAgentControl>
```

#### Display Multiple Agent Streams:
```tsx
<AgentStatusPanel>
  <AgentStream agentId={1} feature="Auth System" status="running" />
  <AgentStream agentId={2} feature="Database Schema" status="running" />
  <AgentStream agentId={3} feature="UI Components" status="completed" />
</AgentStatusPanel>
```

### 7. **Limitations and Considerations**

#### Limitations:
- **No nested subagents**: Subagents cannot spawn other subagents
- **Context isolation**: Each agent has separate context (no shared conversation history)
- **File conflicts**: Multiple agents writing to same file could cause conflicts
- **Resource usage**: Each agent consumes API quota separately

#### Mitigation Strategies:
1. **Atomic feature claiming**: Use database transactions
2. **File locking**: Detect when files are being modified by other agents
3. **Clear boundaries**: Assign agents to different components/features
4. **Agent specialization**: Restrict tools to prevent overlap (e.g., frontend agents can't edit backend files)

### 8. **When to Use Parallel Agents**

#### ✅ Good Use Cases:
- **Independent features**: User auth, database schema, UI components (no shared code)
- **Clear separation**: Frontend vs backend vs database
- **Large projects**: 10+ features where most are independent
- **Specialized tasks**: One agent for features, one for tests, one for docs

#### ❌ Avoid When:
- **Highly coupled features**: Changes will conflict
- **Shared files**: Multiple agents need to edit same file
- **Sequential dependencies**: Feature B requires Feature A
- **Small projects**: Overhead outweighs benefits

### 9. **Recommended Implementation Path**

#### Phase 1: Foundation
1. Add atomic feature claiming to `feature_mcp.py`
2. Add agent registration/tracking
3. Test with 2 parallel agents on simple project

#### Phase 2: Agent Manager
1. Create `agent_manager.py` to spawn/monitor agents
2. Implement background task execution
3. Add parallel mode to CLI (`--parallel 3`)

#### Phase 3: UI Support
1. Add parallel mode controls to UI
2. Display multiple agent streams
3. Add per-feature agent assignment view

#### Phase 4: Optimization
1. Implement smart feature grouping (group independent features)
2. Add conflict detection (warn if agents edit same files)
3. Dynamic scaling (add/remove agents based on workload)

### 10. **Testing Parallel Agents**

```bash
# Test with simple project
python autonomous_agent_demo.py \
  --project-dir test-project \
  --parallel 2 \
  --max-features 4

# Expected behavior:
# - Agent 1: Feature 1 (Auth) → Feature 3 (UI)
# - Agent 2: Feature 2 (Database) → Feature 4 (API)
# - Total time: ~50% of sequential (if no conflicts)
```

## Conclusion

Parallel subagent execution is **feasible and supported** by Claude Code. The key requirements are:

1. **Atomic coordination** via the features database
2. **Clear agent boundaries** to prevent conflicts
3. **UI support** for monitoring multiple agents
4. **Smart feature selection** to maximize parallelism

For the Autocoder project, implementing 2-3 parallel agents could reduce development time by 40-60% for projects with 10+ independent features.

## Next Steps

1. Implement atomic feature claiming in `feature_mcp.py`
2. Create prototype with 2 parallel agents
3. Test on sample project with independent features
4. Measure performance improvement
5. Add UI controls for parallel mode

## Resources

- Claude Agent SDK Documentation: https://docs.anthropic.com/en/docs/build-with-claude/agent-sdk
- Task tool parallel execution (available in Claude Code)
- MCP server pattern for coordination
