# Backend Core Modules - Context Documentation

## Overview

The Python backend core provides the autonomous agent orchestration system using Claude Agent SDK.

## Module Index

| Module | Lines | Purpose |
|--------|-------|---------|
| `agent.py` | 230 | Core agent session loop |
| `client.py` | 200 | Claude SDK client configuration |
| `security.py` | 374 | Bash command security validation |
| `prompts.py` | 228 | Prompt template loading |
| `progress.py` | 223 | Progress tracking and webhooks |
| `registry.py` | 366 | Project registry (SQLite) |
| `autonomous_agent_demo.py` | 148 | Entry point with args |
| `start.py` | 411 | CLI launcher menu |

---

## 1. agent.py - Agent Session Logic

### Key Constants
```python
AUTO_CONTINUE_DELAY_SECONDS = 3
```

### Functions

#### `run_agent_session(client, message, project_dir) -> tuple[str, str]`
Runs a single agent session using Claude Agent SDK.

**Parameters:**
- `client`: ClaudeSDKClient instance
- `message`: Prompt to send
- `project_dir`: Project directory Path

**Returns:** `(status, response_text)` where status is "continue" or "error"

**Flow:**
1. Send prompt via `await client.query(message)`
2. Stream response via `async for msg in client.receive_response()`
3. Handle AssistantMessage blocks (TextBlock, ToolUseBlock)
4. Handle UserMessage blocks (ToolResultBlock)
5. Detect blocked commands and errors

#### `run_autonomous_agent(project_dir, model, max_iterations, yolo_mode) -> None`
Main autonomous agent loop.

**Parameters:**
- `project_dir`: Path - Directory for the project
- `model`: str - Claude model to use
- `max_iterations`: Optional[int] - Limit iterations (None = unlimited)
- `yolo_mode`: bool - Skip browser testing if True

**Flow:**
```
1. Check has_features(project_dir)
   ├─ If False → INITIALIZER AGENT (first session)
   └─ If True → CODING AGENT (continuation)

2. Main Loop:
   ├─ Create client via create_client()
   ├─ Select prompt:
   │   ├─ First run: get_initializer_prompt()
   │   └─ Continuation: get_coding_prompt() or get_coding_prompt_yolo()
   ├─ Run session: async with client: await run_agent_session()
   ├─ Handle status (continue/error)
   └─ Auto-continue after 3 seconds
```

**Key Decision Point (line 145-159):**
```python
is_first_run = not has_features(project_dir)

if is_first_run:
    prompt = get_initializer_prompt(project_dir)
    is_first_run = False  # Only use initializer once
else:
    if yolo_mode:
        prompt = get_coding_prompt_yolo(project_dir)
    else:
        prompt = get_coding_prompt(project_dir)
```

---

## 2. client.py - Claude SDK Client Configuration

### Tool Sets

```python
FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_next",
    "mcp__features__feature_get_for_regression",
    "mcp__features__feature_mark_in_progress",
    "mcp__features__feature_mark_passing",
    "mcp__features__feature_skip",
    "mcp__features__feature_create_bulk",
]

PLAYWRIGHT_TOOLS = [...]  # Browser automation (disabled in YOLO mode)

BUILTIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"]
```

### Function

#### `create_client(project_dir, model, yolo_mode=False) -> ClaudeSDKClient`

**Security Configuration:**
1. **Sandbox:** OS-level bash command isolation
2. **Permissions:** File ops restricted to `./**` (project dir only)
3. **Security Hooks:** Pre-tool-use validation via `bash_security_hook`

**MCP Servers:**
- `features`: Always included - feature database management
- `playwright`: Only if NOT yolo_mode - browser automation

**Settings File:** Writes `.claude_settings.json` in project dir

---

## 3. security.py - Bash Command Security

### ALLOWED_COMMANDS Set
```python
{
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep",
    # File operations
    "cp", "mkdir", "chmod", "pwd", "echo", "mv", "rm", "touch",
    # Development
    "npm", "npx", "pnpm", "node",
    # Version control
    "git",
    # Docker
    "docker",
    # Process management
    "ps", "lsof", "sleep", "kill", "pkill",
    # Network
    "curl",
    # Shell
    "sh", "bash",
    # Scripts
    "init.sh",
}
```

### Commands Requiring Extra Validation
```python
COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "init.sh"}
```

### Functions

#### `extract_commands(command_string) -> list[str]`
Extracts base command names from shell command strings.
Handles pipes, command chaining (`&&`, `||`, `;`), subshells.

#### `validate_pkill_command(command_string) -> tuple[bool, str]`
Only allows: `{"node", "npm", "npx", "vite", "next"}`

#### `validate_chmod_command(command_string) -> tuple[bool, str]`
Only allows `+x` variants (making files executable).

#### `validate_init_script(command_string) -> tuple[bool, str]`
Only allows `./init.sh` or paths ending with `/init.sh`.

#### `bash_security_hook(input_data, tool_use_id, context) -> dict`
Pre-tool-use hook for Bash commands.

**Returns:**
- `{}` - Allow command
- `{"decision": "block", "reason": "..."}` - Block command

---

## 4. prompts.py - Template Loading

### Fallback Chain
```
1. Project-specific: {project_dir}/prompts/{name}.md
2. Base template: .claude/templates/{name}.template.md
```

### Functions

#### `load_prompt(name, project_dir) -> str`
Load prompt with fallback to template.

#### `get_initializer_prompt(project_dir) -> str`
Loads `initializer_prompt.md`

#### `get_coding_prompt(project_dir) -> str`
Loads `coding_prompt.md` (standard mode with testing)

#### `get_coding_prompt_yolo(project_dir) -> str`
Loads `coding_prompt_yolo.md` (rapid prototyping, no testing)

#### `scaffold_project_prompts(project_dir) -> Path`
Creates prompts/ directory and copies templates:
- `app_spec.template.txt` → `app_spec.txt`
- `coding_prompt.template.md` → `coding_prompt.md`
- `coding_prompt_yolo.template.md` → `coding_prompt_yolo.md`
- `initializer_prompt.template.md` → `initializer_prompt.md`

#### `copy_spec_to_project(project_dir) -> None`
Copies spec from `prompts/app_spec.txt` to project root.

---

## 5. progress.py - Progress Tracking

### Functions

#### `has_features(project_dir) -> bool`
Returns True if features exist in database.

**Checks:**
1. Legacy: `feature_list.json` exists
2. SQLite: `features.db` exists AND has ≥1 feature

**Used to determine:** Initializer vs Coding agent

#### `count_passing_tests(project_dir) -> tuple[int, int, int]`
Returns `(passing_count, in_progress_count, total_count)`

#### `send_progress_webhook(passing, total, project_dir) -> None`
Sends progress to N8N webhook (if configured).

**Cache:** `.progress_cache` file tracks previous state.

---

## 6. registry.py - Project Registry

### Storage
- Location: `~/.autocoder/registry.db`
- Format: SQLite with SQLAlchemy ORM

### Model
```python
class Project(Base):
    __tablename__ = "projects"
    name = Column(String(50), primary_key=True)
    path = Column(String, nullable=False)  # POSIX format
    created_at = Column(DateTime, nullable=False)
```

### Functions

#### `register_project(name, path) -> None`
Validates and registers a new project.

#### `unregister_project(name) -> bool`
Removes project from registry.

#### `get_project_path(name) -> Path | None`
Lookup project by name.

#### `list_registered_projects() -> dict[str, dict]`
Returns all registered projects.

---

## 7. autonomous_agent_demo.py - Entry Point

### Default Model
```python
DEFAULT_MODEL = "claude-opus-4-5-20251101"
```

### Arguments
- `--project-dir` (required): Absolute path OR registered project name
- `--max-iterations` (optional): Limit iterations
- `--model` (optional): Claude model
- `--yolo` (flag): Enable YOLO mode

### Main Logic
1. Parse arguments
2. Resolve project path (registry or absolute)
3. Call `asyncio.run(run_autonomous_agent(...))`

---

## 8. start.py - CLI Launcher

### Menu Flow
```
Main Menu:
[1] Create new project
[2] Continue existing project
[q] Quit
```

### Key Functions

#### `create_new_project_flow() -> tuple[str, Path] | None`
1. Get project name and path
2. Call `ensure_project_scaffolded()`
3. Ask: Create spec with Claude or manually?
4. Validate spec exists
5. Return `(name, path)`

#### `ensure_project_scaffolded(name, path) -> Path`
1. Create project directory
2. Call `scaffold_project_prompts()`
3. Call `register_project()`

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     ENTRY POINT                              │
│  autonomous_agent_demo.py → parse_args() → resolve path     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                 AGENT LOOP (agent.py)                        │
│  run_autonomous_agent()                                     │
│  ├─ Check has_features() → INITIALIZER or CODING           │
│  ├─ ITERATION LOOP:                                         │
│  │  ├─ Choose prompt based on session type                  │
│  │  ├─ create_client() [with security settings]             │
│  │  ├─ run_agent_session()                                  │
│  │  └─ Auto-continue with 3s delay                          │
│  └─ Print final progress summary                            │
└─────────────────────────────────────────────────────────────┘
     ↓                    ↓                    ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Prompts      │  │ Client       │  │ Security         │
│ (prompts.py) │  │ (client.py)  │  │ (security.py)    │
├──────────────┤  ├──────────────┤  ├──────────────────┤
│- Templates   │  │- MCP servers │  │- Bash validation │
│- Fallback    │  │- Tools       │  │- Allowlist       │
│- load_prompt │  │- Hooks       │  │- Extra checks    │
└──────────────┘  └──────────────┘  └──────────────────┘
```

---

## Extension Points

### Adding a New Agent Type (e.g., Analyzer Agent)

1. **Create template:** `.claude/templates/analyzer_prompt.template.md`

2. **Add to prompts.py:**
```python
def get_analyzer_prompt(project_dir: Path | None = None) -> str:
    return load_prompt("analyzer_prompt", project_dir)
```

3. **Modify agent.py decision logic:**
```python
def determine_agent_type(project_dir: Path) -> str:
    if not has_features(project_dir):
        if (project_dir / ".analyze_mode").exists():
            return "analyzer"
        return "initializer"
    return "coding"
```

4. **Add prompt selection:**
```python
if agent_type == "analyzer":
    prompt = get_analyzer_prompt(project_dir)
elif agent_type == "initializer":
    prompt = get_initializer_prompt(project_dir)
else:
    prompt = get_coding_prompt(project_dir)
```
