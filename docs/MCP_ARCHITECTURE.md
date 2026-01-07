# MCP + Direct Import Architecture (Hybrid Approach)

## 🎯 The Architecture (As Recommended by External AI)

### Key Insight: System Code vs. Agent Code

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM CODE (Python)                      │
│  Orchestrator, Gatekeeper, WorktreeManager                 │
│  ✅ Can use direct Python imports (FAST, EFFICIENT)         │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Coordinates
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    AGENTS (LLMs)                            │
│  Worker agents implementing features                       │
│  ✅ Can ONLY call MCP tools (LLM limitation)               │
└─────────────────────────────────────────────────────────────┘
```

### Why This Hybrid Approach?

**System (Orchestrator/Gatekeeper):**
- Written in Python by you
- Can import modules directly: `from knowledge_base import KnowledgeBase`
- Fast, efficient, full Python capabilities
- Used for coordination and decision-making

**Agents (Workers):**
- Claude LLM running code
- **Cannot** import Python modules
- **Can** call MCP tools
- Need tools to access capabilities

---

## 📦 MCP Servers (For Agents)

### 1. Test MCP Server ✅
**File:** `mcp_server/test_mcp.py`

**Tools:**
- `detect_project_framework()` - Learn which framework to use
- `generate_test_file()` - Create test scaffolding
- `run_tests()` - Execute tests with CI-safe flags
- `get_framework_info()` - Get detailed setup info

**Agent Usage:**
```python
# Agent calls tools naturally:
agent.call_tool("test_mcp", "detect_project_framework")
agent.call_tool("test_mcp", "generate_test_file", feature_name="User Login")
agent.call_tool("test_mcp", "run_tests")
```

### 2. Knowledge MCP Server ✅
**File:** `mcp_server/knowledge_mcp.py`

**Tools:**
- `get_similar_features()` - Find similar past features
- `get_reference_prompt()` - Get examples before implementing
- `get_best_model()` - Learn which model works best
- `store_pattern()` - Teach system after completing feature

**Agent Usage:**
```python
# Agent learns before implementing:
agent.call_tool("knowledge_mcp", "get_reference_prompt",
    feature_category="backend",
    feature_name="User Auth"
)

# Agent teaches after completing:
agent.call_tool("knowledge_mcp", "store_pattern",
    implementation_approach="JWT with refresh tokens",
    success=true
)
```

### 3. Model Settings MCP Server ✅
**File:** `mcp_server/model_settings_mcp.py`

**Tools:**
- `get_presets()` - List available model presets
- `apply_preset()` - Apply quality/balanced/economy preset
- `get_best_model()` - Get recommended model for category
- `update_settings()` - Configure model selection

**Agent Usage:**
```python
# Agent gets model recommendation:
agent.call_tool("model_settings_mcp", "get_best_model",
    category="testing"
)  # Returns: haiku
```

### 4. Feature MCP Server (Already Exists)
**File:** `mcp_server/feature_mcp.py`

**Tools:**
- `feature_get_stats()` - Progress tracking
- `feature_get_next()` - Get next feature to work on
- `feature_claim_batch()` - Claim features (parallel execution)
- `feature_mark_passing()` - Mark feature complete

**Agent Usage:**
```python
# Agent claims feature work:
agent.call_tool("feature_mcp", "feature_claim_batch",
    count=3,
    agent_id="agent-1"
)
```

---

## 🔧 Direct Imports (For System Code)

### Orchestrator (Python - You Write This)
```python
class Orchestrator:
    def __init__(self):
        # ✅ Direct imports - FAST!
        from knowledge_base import KnowledgeBase
        from model_settings import ModelSettings
        from worktree_manager import WorktreeManager

        self.kb = KnowledgeBase()
        self.model_settings = ModelSettings()
        self.worktree = WorktreeManager(project_dir)

    def assign_feature(self, agent_id, feature):
        # System logic uses direct imports
        best_model = self.model_settings.get_best_model(feature.category)
        similar = self.kb.get_similar_features(feature)

        # Create worktree
        worktree_path = self.worktree.create_worktree(agent_id, feature.id)

        # Agent will use MCP tools during implementation
        return {
            "worktree_path": worktree_path,
            "model": best_model
        }
```

**Why Direct Imports Here?**
- Orchestrator is Python code you write
- Has full Python capabilities
- Direct imports are faster and more efficient
- No need for MCP overhead

### Gatekeeper (Python Script - Not an Agent!)
```python
class Gatekeeper:
    """Gatekeeper is deterministic logic, not an LLM agent."""

    def __init__(self, project_path):
        # ✅ Direct imports
        from test_framework_detector import TestFrameworkDetector
        from worktree_manager import WorktreeManager

        self.test_detector = TestFrameworkDetector(project_path)
        self.worktree = WorktreeManager(project_path)

    def verify_feature(self, branch_name):
        # Run tests (direct Python call)
        cmd = self.test_detector.get_test_command(ci_mode=True)
        result = subprocess.run(cmd, ...)

        if result.returncode == 0:
            # Merge to main
            return {"approved": true}
        else:
            # Reject
            return {"approved": false, "errors": result.stderr}
```

**Why Not an Agent?**
- Gatekeeper is deterministic: run tests → pass/fail → merge/reject
- No LLM reasoning needed
- Python script is faster and more reliable

---

## 🎯 Complete Workflow Example

### Step 1: Orchestrator (System - Python)
```python
# Orchestrator uses direct imports
orchestrator = Orchestrator()

# Claim feature for agent
feature = orchestrator.get_next_feature()
model = orchestrator.model_settings.get_best_model(feature.category)

# Create isolated worktree
worktree = orchestrator.worktree.create_worktree("agent-1", feature.id)

# Launch agent with MCP tools available
agent = create_agent(
    model=model,
    mcp_servers={
        "knowledge": knowledge_mcp,
        "model_settings": model_settings_mcp,
        "test": test_mcp,
        "feature": feature_mcp
    }
)
```

### Step 2: Agent (Worker - LLM with MCP Tools)
```python
# Agent receives task and uses MCP tools

# 1. Learn from knowledge base
agent.call_tool("knowledge_mcp", "get_reference_prompt",
    feature_category=feature.category,
    feature_name=feature.name
)

# 2. Detect testing framework
agent.call_tool("test_mcp", "detect_project_framework")

# 3. Generate test file
agent.call_tool("test_mcp", "generate_test_file",
    feature_name=feature.name,
    feature_description=feature.description
)

# 4. Run tests (RED phase)
agent.call_tool("test_mcp", "run_tests")

# 5. Implement feature (code writing happens here)

# 6. Run tests again (GREEN phase)
agent.call_tool("test_mcp", "run_tests")

# 7. Store pattern in knowledge base
agent.call_tool("knowledge_mcp", "store_pattern",
    implementation_approach="JWT with refresh tokens",
    files_changed='["auth.py", "models.py"]',
    success=true,
    attempts=1,
    lessons_learned="Refresh tokens prevent re-auth"
)

# 8. Mark feature complete
agent.call_tool("feature_mcp", "feature_mark_passing",
    feature_id=feature.id
)
```

### Step 3: Gatekeeper (System - Python Script)
```python
# Gatekeeper verifies work (Python script, not agent)
gatekeeper = Gatekeeper(project_path)

# Run tests (direct Python, no MCP)
verification = gatekeeper.verify_feature(branch_name)

if verification["approved"]:
    # Merge to main
    gatekeeper.merge_to_main(branch_name)
    gatekeeper.delete_worktree(agent_id)
else:
    # Reject and retry
    gatekeeper.reject_feature(branch_name, verification["errors"])
```

---

## 📊 Summary: What Uses What

| Component | Type | Access Method |
|-----------|------|---------------|
| **KnowledgeBase** | System (Orchestrator) | Direct import: `from knowledge_base import KnowledgeBase` |
| **KnowledgeBase** | Agents (Workers) | MCP tool: `call_tool("knowledge_mcp", "get_reference_prompt")` |
| **ModelSettings** | System (Orchestrator) | Direct import: `from model_settings import ModelSettings` |
| **ModelSettings** | Agents (Workers) | MCP tool: `call_tool("model_settings_mcp", "get_best_model")` |
| **TestDetector** | System (Gatekeeper) | Direct import: `from test_framework_detector import TestFrameworkDetector` |
| **TestDetector** | Agents (Workers) | MCP tool: `call_tool("test_mcp", "run_tests")` |
| **WorktreeManager** | System (Orchestrator/Gatekeeper) | Direct import: `from worktree_manager import WorktreeManager` |
| **FeatureDB** | System (Orchestrator) | Direct import: `from api.database import Feature` |
| **FeatureDB** | Agents (Workers) | MCP tool: `call_tool("feature_mcp", "feature_claim_batch")` |

---

## ✅ Benefits of This Architecture

1. **Speed** - System code uses fast direct imports
2. **Flexibility** - Agents can discover and use tools naturally
3. **Separation of Concerns** - System coordinates, agents implement
4. **No Prompt Engineering** - MCP tools are self-documenting
5. **Production Ready** - Proven pattern (used in real CI/CD)

---

## 🚀 Next Steps

Now we build:

1. **Orchestrator** (Python with direct imports)
   - Coordinates agents
   - Uses direct imports for speed
   - Manages worktrees and heartbeats

2. **Gatekeeper** (Python script, not agent)
   - Runs tests directly
   - Merges or rejects deterministically
   - No LLM overhead

3. **Database Schema**
   - Add heartbeats table
   - Add branch tracking
   - Add review status

**Result:** Complete system with both approaches used optimally! 🎯
