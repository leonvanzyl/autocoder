# Knowledge Base Integration Guide

This guide shows how to integrate the knowledge base system into the autonomous agent workflow.

## Quick Start

### 1. Basic Usage in Agent

```python
from knowledge_base import get_knowledge_base, ImplementationTracker
from prompts import enhance_prompt_with_knowledge

# Get current feature from database
feature = {
    "id": 1,
    "category": "authentication",
    "name": "login form",
    "description": "Create login form with email/password",
    "steps": ["create form", "add validation", "connect to API"]
}

# Enhance prompt with past examples
base_prompt = get_coding_prompt(project_dir)
enhanced_prompt = enhance_prompt_with_knowledge(base_prompt, feature)

# Send enhanced prompt to agent
await client.query(enhanced_prompt)
```

### 2. Track Implementation

```python
# Start tracking when agent begins feature
tracker = ImplementationTracker(feature, project_dir)
tracker.set_model("claude-opus-4-5")

# During agent session, track via tool use hooks
# (see Advanced Integration below)

# After feature passes tests
tracker.save_to_knowledge_base(
    success=True,
    attempts=1,
    lessons_learned="Formik reduces validation code significantly"
)
```

## Integration Points

### Point 1: Prompt Enhancement

**Location**: `agent.py` - `run_agent_session()`

```python
from prompts import enhance_prompt_with_knowledge
from api.database import get_database_path
from progress import get_feature_from_db  # Helper to get feature

async def run_agent_session(client, message, project_dir):
    # Get current feature from database
    feature = get_current_feature(project_dir)

    # Enhance prompt with knowledge base
    enhanced_message = enhance_prompt_with_knowledge(message, feature)

    # Send enhanced prompt
    await client.query(enhanced_message)
```

### Point 2: File Change Tracking

**Location**: `client.py` - Tool use hooks

```python
class TrackedClaudeSDKClient(ClaudeSDKClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tracker = None

    def set_tracker(self, tracker):
        self.tracker = tracker

    async def use_tool(self, tool_name, tool_input):
        result = await super().use_tool(tool_name, tool_input)

        # Track file changes
        if self.tracker and tool_name in ["write", "edit"]:
            file_path = tool_input.get("file_path")
            self.tracker.record_file_change(file_path, "modified")

        return result
```

### Point 3: Result Storage

**Location**: `autonomous_agent_demo.py` - Main loop

```python
from knowledge_base import ImplementationTracker

async def main():
    tracker = None

    while not all_tests_passing():
        if not tracker:
            # Start tracking for new feature
            feature = get_current_feature(project_dir)
            tracker = ImplementationTracker(feature, project_dir)
            tracker.set_model(model_used)

        # Run agent session
        status, response = await run_agent_session(client, prompt, project_dir)

        # Record approach from response
        if "approach" in response:
            tracker.record_approach(response["approach"])

        # Check if feature passes
        if feature_passing():
            # Save to knowledge base
            tracker.save_to_knowledge_base(
                success=True,
                attempts=attempt_count,
                lessons_learned=response.get("lessons_learned", "")
            )
            tracker = None  # Reset for next feature
```

## MCP Integration (Future)

Expose knowledge base as MCP tools:

```python
# mcp_server/knowledge_mcp.py

@mcp.tool()
def knowledge_get_similar(category: str, name: str, description: str) -> str:
    """Get similar past features for reference."""
    kb = get_knowledge_base()
    feature = {"category": category, "name": name, "description": description}
    similar = kb.get_similar_features(feature, limit=3)
    return json.dumps(similar)

@mcp.tool()
def knowledge_store_pattern(
    category: str,
    feature_name: str,
    description: str,
    approach: str,
    files_changed: list[str],
    model_used: str,
    success: bool,
    lessons_learned: str
) -> str:
    """Store an implementation pattern."""
    kb = get_knowledge_base()
    feature = {"category": category, "name": feature_name, "description": description}
    implementation = {
        "approach": approach,
        "files_changed": files_changed,
        "model_used": model_used
    }
    pattern_id = kb.store_pattern(feature, implementation, success, 1, lessons_learned)
    return f"Stored pattern ID: {pattern_id}"

@mcp.tool()
def knowledge_get_best_model(category: str) -> str:
    """Get the best model for a category."""
    kb = get_knowledge_base()
    return kb.get_best_model(category)

@mcp.tool()
def knowledge_get_reference_prompt(category: str, name: str, description: str) -> str:
    """Get reference examples for prompt enhancement."""
    kb = get_knowledge_base()
    feature = {"category": category, "name": name, "description": description}
    return kb.get_reference_prompt(feature)
```

## Helper Functions

### Get Current Feature

```python
# progress.py (add this function)

def get_current_feature(project_dir: Path) -> dict:
    """Get the current feature being implemented."""
    db_file = project_dir / "features.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get feature that's in_progress or highest priority pending
    cursor.execute("""
        SELECT id, category, name, description, steps
        FROM features
        WHERE in_progress = 1
        ORDER BY priority ASC
        LIMIT 1
    """)

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "id": result[0],
            "category": result[1],
            "name": result[2],
            "description": result[3],
            "steps": json.loads(result[4])
        }

    # If no in_progress, get highest priority pending
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, category, name, description, steps
        FROM features
        WHERE passes = 0 AND in_progress = 0
        ORDER BY priority ASC
        LIMIT 1
    """)

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "id": result[0],
            "category": result[1],
            "name": result[2],
            "description": result[3],
            "steps": json.loads(result[4])
        }

    return None
```

### Check Feature Passing

```python
# progress.py (add this function)

def feature_passing(project_dir: Path, feature_id: int) -> bool:
    """Check if a specific feature is passing."""
    db_file = project_dir / "features.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT passes FROM features WHERE id = ?", (feature_id,))
    result = cursor.fetchone()
    conn.close()

    return result[0] if result else False
```

## Configuration

### Environment Variables (Optional)

```bash
# Disable knowledge base learning
KNOWLEDGE_BASE_ENABLED=false

# Use project-specific knowledge base instead of global
KNOWLEDGE_BASE_TYPE=project

# Customize max similar features
KNOWLEDGE_BASE_MAX_SIMILAR=5
```

### Implementation

```python
# knowledge_base.py (modify __init__)

class KnowledgeBase:
    def __init__(self, project_dir: Optional[Path] = None):
        # Check environment
        enabled = os.environ.get("KNOWLEDGE_BASE_ENABLED", "true").lower() == "true"
        if not enabled:
            self.disabled = True
            return

        kb_type = os.environ.get("KNOWLEDGE_BASE_TYPE", "global")
        if kb_type == "project" and project_dir:
            # Project-specific knowledge base
            self.db_path = project_dir / "knowledge.db"
        else:
            # Global knowledge base
            kb_dir = Path.home() / ".autocoder"
            kb_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = kb_dir / "knowledge.db"
```

## Testing Integration

```python
# test_integration.py

def test_knowledge_base_integration():
    """Test knowledge base integration with agent."""
    from knowledge_base import get_knowledge_base, ImplementationTracker
    from prompts import enhance_prompt_with_knowledge

    # Setup
    feature = {
        "category": "authentication",
        "name": "login form",
        "description": "Create login form"
    }

    # Test prompt enhancement
    base_prompt = "Implement this feature"
    enhanced = enhance_prompt_with_knowledge(base_prompt, feature)
    assert len(enhanced) >= len(base_prompt)

    # Test tracking
    tracker = ImplementationTracker(feature)
    tracker.record_approach("Used Formik")
    tracker.record_file_change("src/Login.tsx", "created")
    tracker.save_to_knowledge_base(success=True)

    # Verify storage
    kb = get_knowledge_base()
    similar = kb.get_similar_features(feature, limit=1)
    assert len(similar) > 0
    assert similar[0]["feature_name"] == "login form"

    print("Integration test passed!")
```

## Best Practices

1. **Always track both successes and failures**
   - Failures teach what doesn't work
   - Record attempt count for difficulty assessment

2. **Be specific with approaches**
   - Instead of "created form", use "Created React form with Formik and Tailwind"
   - Include library names, patterns used

3. **Record lessons learned**
   - What would you tell yourself next time?
   - What surprised you? What would you do differently?

4. **Use categories consistently**
   - Standard categories: authentication, ui, api, database, deployment, testing
   - Helps with pattern recognition across projects

5. **Review knowledge base periodically**
   - Use `inspect_knowledge.py` to see what's been learned
   - Look for patterns in successes and failures
   - Identify areas needing more data

## Troubleshooting

### Knowledge base not enhancing prompts

```python
# Check if knowledge base has data
kb = get_knowledge_base()
summary = kb.get_summary()
print(f"Total patterns: {summary['total_patterns']}")

# If 0 patterns, need to store some first
# If patterns exist but no matches, check similarity matching
```

### Similar features not found

```python
# Check category matching
feature = {"category": "authentication", ...}
similar = kb.get_similar_features(feature)

# If no results, try without category
feature_no_cat = {"category": "", ...}
similar = kb.get_similar_features(feature_no_cat)
```

### Database locked

```python
# Ensure only one connection at a time
# Use context manager for connections
with sqlite3.connect(db_path) as conn:
    # ... operations ...
# Connection auto-closes
```

## Next Steps

1. **Add to agent loop**: Integrate tracking into `autonomous_agent_demo.py`
2. **Add MCP tools**: Expose knowledge base via MCP server
3. **Auto-tracking**: Track file changes via tool use hooks
4. **Analytics**: Add dashboard for knowledge base insights
5. **Embeddings**: Upgrade to vector-based similarity search
