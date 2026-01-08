# MCP Server & Database - Context Documentation

## Overview

The MCP (Model Context Protocol) Server provides feature management tools for autonomous agents.

---

## MCP Tools Reference

### 1. feature_get_stats()
**Returns:** `{passing, in_progress, total, percentage}`
**Use:** Display progress dashboards

### 2. feature_get_next()
**Returns:** Next pending feature (lowest priority, passes=false)
**Use:** Determine what to implement next

### 3. feature_get_for_regression(limit=3)
**Params:** `limit` (1-10, default 3)
**Returns:** Random passing features for testing
**Use:** Verify previous work still functions

### 4. feature_mark_passing(feature_id)
**Params:** `feature_id` (int, ≥1)
**Effect:** Sets `passes=true`, clears `in_progress`
**Use:** After successful implementation and testing

### 5. feature_skip(feature_id)
**Params:** `feature_id` (int, ≥1)
**Effect:** Sets priority to max+1, clears `in_progress`
**Use:** When blocked by external dependencies

### 6. feature_mark_in_progress(feature_id)
**Params:** `feature_id` (int, ≥1)
**Effect:** Sets `in_progress=true`
**Use:** Lock feature to prevent concurrent work

### 7. feature_clear_in_progress(feature_id)
**Params:** `feature_id` (int, ≥1)
**Effect:** Clears `in_progress` flag
**Use:** When abandoning or unsticking feature

### 8. feature_create_bulk(features)
**Params:** List of `{category, name, description, steps[]}`
**Effect:** Creates all features with sequential priorities
**Use:** Initializer agent creates all features at once

---

## Database Schema

### Feature Table (features.db)

```sql
CREATE TABLE features (
    id INTEGER PRIMARY KEY,
    priority INTEGER NOT NULL DEFAULT 999,
    category VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    steps JSON NOT NULL,
    passes BOOLEAN DEFAULT FALSE,
    in_progress BOOLEAN DEFAULT FALSE
);

CREATE INDEX ix_features_priority ON features(priority);
CREATE INDEX ix_features_passes ON features(passes);
CREATE INDEX ix_features_in_progress ON features(in_progress);
```

### SQLAlchemy Model (api/database.py)

```python
class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
        }
```

---

## Migration Logic (api/migration.py)

### JSON to SQLite Migration

```python
def migrate_json_to_sqlite(project_dir, session_maker) -> bool:
    """
    Auto-migrate legacy feature_list.json to SQLite.

    1. Check if feature_list.json exists
    2. Check if database already has data
    3. Import all features from JSON
    4. Backup original: feature_list.json.backup.{timestamp}
    """
```

### Schema Migration

```python
def _migrate_add_in_progress_column(engine):
    """Add in_progress column to existing databases."""
    # ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0
```

---

## Prompt Templates

### Template Location
`.claude/templates/`

### Fallback Chain
```
1. {project_dir}/prompts/{name}.md (project-specific)
2. .claude/templates/{name}.template.md (fallback)
```

### Key Templates

#### app_spec.template.txt
XML format with sections:
- `<project_name>`
- `<overview>`
- `<technology_stack>`
- `<core_features>`
- `<database_schema>`
- `<api_endpoints_summary>`
- `<ui_layout>`
- `<design_system>`
- `<implementation_steps>`
- `<success_criteria>`

#### initializer_prompt.template.md
First session prompt that:
- Reads app_spec.txt
- Creates features via `feature_create_bulk`
- Creates init.sh, README.md
- Initializes git repository

**Critical Placeholder:**
```
**CRITICAL:** You must create exactly **[FEATURE_COUNT]** features
```

#### coding_prompt.template.md
Continuation session prompt:
1. Get bearings (pwd, ls, read files)
2. Start servers (init.sh)
3. Verification test (regression)
4. Choose feature (`feature_get_next`)
5. Implement feature
6. Verify with browser automation
7. Update feature status
8. Commit progress
9. Update progress notes
10. End session cleanly

#### coding_prompt_yolo.template.md
YOLO mode - skips browser testing:
- Uses lint/type-check only
- No regression testing
- Faster iteration for prototyping

---

## Adding New MCP Tools

### Step 1: Define Tool
```python
@mcp.tool()
def my_new_tool(
    param: Annotated[int, Field(description="...", ge=1)]
) -> str:
    """Tool description for agent context."""
    session = get_session()
    try:
        # Implementation
        return json.dumps({"result": "..."})
    finally:
        session.close()
```

### Step 2: Follow Conventions
- Naming: `feature_*` prefix
- Return: Always JSON string
- Errors: `{"error": "message"}`
- Sessions: Open, try/except, finally close

---

## Feature Lifecycle

```
[PENDING] ← Created by initializer
    ↓ feature_mark_in_progress(id)
[IN_PROGRESS] ← Agent working on it
    ├─ feature_mark_passing(id) → [DONE] ✓
    ├─ feature_skip(id) → [PENDING] (end of queue)
    └─ feature_clear_in_progress(id) → [PENDING]
```
