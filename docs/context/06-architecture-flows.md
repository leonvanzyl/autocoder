# Architecture & Data Flows - Context Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     REACT WEB UI                             │
│  Components: ProjectSelector, KanbanBoard, AgentControl     │
│  Hooks: useProjects, useWebSocket, useSpecChat              │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST + WebSocket
┌─────────────────────────────▼───────────────────────────────┐
│                    FASTAPI SERVER                            │
│  Routers: /api/projects, /api/agent, /api/features          │
│  WebSocket: /ws/projects/{name}, /api/spec/ws/{name}        │
│  Services: process_manager, spec_chat_session               │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                  AGENT SUBPROCESS                            │
│  autonomous_agent_demo.py → agent.py → client.py            │
│                              │                               │
│  ┌───────────────────────────▼─────────────────────────┐    │
│  │ DECISION POINT (agent.py:145)                       │    │
│  │                                                      │    │
│  │ if not has_features(project_dir):                   │    │
│  │     → INITIALIZER AGENT (create features)           │    │
│  │ else:                                                │    │
│  │     → CODING AGENT (implement features)             │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    MCP SERVERS                               │
│  features: feature_get_next, feature_mark_passing, etc.     │
│  playwright: browser_navigate, browser_click, etc.          │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                      STORAGE                                 │
│  ~/.autocoder/registry.db (projects)                        │
│  {project}/features.db (features)                           │
│  {project}/prompts/ (templates)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 1: New Project Creation

```
UI: NewProjectModal
    ↓ Step 1: Enter name
    ↓ Step 2: Select folder (FolderBrowser)
    ↓ Step 3: Choose method (Claude/Manual)
    │
    ├─ [Claude Method]
    │   ↓ POST /api/projects {name, path, specMethod: "claude"}
    │   │   → validate_project_name()
    │   │   → is_path_blocked() check
    │   │   → mkdir project_path
    │   │   → scaffold_project_prompts()
    │   │   → register_project()
    │   ↓ WebSocket /api/spec/ws/{name}
    │   │   → SpecChatSession.start()
    │   │   → Interactive conversation with Claude
    │   │   → Claude writes app_spec.txt
    │   │   → Claude writes initializer_prompt.md (with feature count)
    │   ↓ POST /api/projects/{name}/agent/start
    │       → AgentProcessManager.start()
    │       → Subprocess: python autonomous_agent_demo.py
    │
    └─ [Manual Method]
        ↓ POST /api/projects {name, path, specMethod: "manual"}
            → Same as above but no spec chat
            → User edits templates manually
```

---

## Flow 2: Agent Session Loop

```
autonomous_agent_demo.py
    ↓ Parse args: --project-dir, --model, --yolo
    ↓ Resolve project path (registry or absolute)
    ↓ asyncio.run(run_autonomous_agent(...))

agent.py::run_autonomous_agent()
    │
    ├─ Check: has_features(project_dir)?
    │   ├─ No → is_first_run = True (INITIALIZER)
    │   └─ Yes → is_first_run = False (CODING)
    │
    └─ Main Loop (while True):
        ├─ iteration++
        ├─ Check max_iterations
        │
        ├─ Create client: create_client(project_dir, model, yolo_mode)
        │   ├─ Configure security settings
        │   ├─ Setup MCP servers (features, playwright)
        │   ├─ Setup hooks (bash_security_hook)
        │   └─ Write .claude_settings.json
        │
        ├─ Select prompt:
        │   ├─ First run: get_initializer_prompt()
        │   └─ Continuation: get_coding_prompt() or get_coding_prompt_yolo()
        │
        ├─ Run session: async with client:
        │   └─ await run_agent_session(client, prompt, project_dir)
        │       ├─ client.query(message)
        │       ├─ Stream response
        │       ├─ Handle tools
        │       └─ Return (status, response_text)
        │
        ├─ Handle status:
        │   ├─ "continue" → sleep 3s, next iteration
        │   └─ "error" → retry with fresh session
        │
        └─ Print progress summary
```

---

## Flow 3: Feature Lifecycle

```
State Machine:
                              feature_create_bulk()
                                      ↓
                              ┌───────────────┐
                              │    PENDING    │
                              │ passes=false  │
                              │ in_progress=  │
                              │    false      │
                              └───────┬───────┘
                                      │
                    feature_mark_in_progress(id)
                                      ↓
                              ┌───────────────┐
                              │  IN_PROGRESS  │
                              │ passes=false  │
                              │ in_progress=  │
                              │    true       │
                              └───────┬───────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
feature_mark_passing(id)      feature_skip(id)        feature_clear_in_progress(id)
        │                             │                             │
        ↓                             ↓                             ↓
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│     DONE      │             │    PENDING    │             │    PENDING    │
│ passes=true   │             │ (end of queue)│             │ (same place)  │
│ in_progress=  │             │ priority=max+1│             │               │
│    false      │             └───────────────┘             └───────────────┘
└───────────────┘
```

---

## Flow 4: Real-time Updates (WebSocket)

```
Agent Subprocess
    ↓ stdout
process_manager.py::_stream_output()
    ↓ sanitize_output() [redact secrets]
    ↓ for callback in output_callbacks:
        callback(line)
    ↓
websocket.py::broadcast_to_project()
    ↓ JSON: {"type": "log", "line": "...", "timestamp": "..."}
    ↓
WebSocket connection(s)
    ↓
React: useProjectWebSocket hook
    ↓ Update logs state
    ↓
DebugLogViewer component re-render


Progress Polling (every 2 seconds):
    poll_progress() task
        ↓ count_passing_tests(project_dir)
        ↓ Compare with last value
        ↓ If changed: broadcast_to_project()
            JSON: {"type": "progress", "passing": X, "total": Y, "percentage": Z}
        ↓
    React: useProjectWebSocket
        ↓ Update progress state
        ↓
    ProgressDashboard + KanbanBoard re-render
```

---

## Flow 5: Security Enforcement

```
Layer 1: OS-Level Sandbox
    client.py: sandbox.enabled = true
    → OS isolates subprocess

Layer 2: Filesystem Permissions
    client.py: permissions.allow = ["Read(./**)", "Write(./**)", ...]
    → Paths relative to project_dir only

Layer 3: Bash Security Hook
    security.py::bash_security_hook()
    → Extract commands from command string
    → Check each against ALLOWED_COMMANDS
    → Extra validation for pkill, chmod, init.sh
    → Return {"decision": "block"} if invalid

Layer 4: Output Sanitization
    process_manager.py::sanitize_output()
    → Regex patterns for API keys, tokens
    → Replace with [REDACTED]

Layer 5: Filesystem Browser
    server/routers/filesystem.py::is_path_blocked()
    → Block system dirs, sensitive paths
    → Prevent project creation in dangerous locations
```

---

## Integration Points: Import Existing Project

### Files to Modify

| Layer | File | Change |
|-------|------|--------|
| API | `server/routers/projects.py` | Add `POST /api/projects/import` |
| Backend | `prompts.py` | Add `migrate_project_prompts()` |
| Backend | `api/database.py` | Add `ensure_database_exists()` |
| UI | `NewProjectModal.tsx` | Add "Import" option |
| UI | `lib/api.ts` | Add `importProject()` |
| UI | `hooks/useProjects.ts` | Add `useImportProject()` |
| CLI | `start.py` | Add [3] Import option |

### Import Flow

```
UI: NewProjectModal
    ↓ New option: "Import Existing Project"
    ↓ FolderBrowser: Select existing project folder
    ↓ Validation:
    │   ├─ Check path exists
    │   ├─ Check not blocked
    │   ├─ Check has source code
    │   ├─ Check for existing features.db
    │   └─ Check for app_spec.txt
    ↓
    POST /api/projects/import
    │   Body: {name, path}
    │
    ↓ Backend:
    │   ├─ validate_project_name()
    │   ├─ is_path_blocked()
    │   ├─ migrate_project_prompts() [create if missing]
    │   ├─ ensure_database_exists() [create if missing]
    │   └─ register_project()
    │
    ↓ Response: ProjectSummary
    │
    ↓ Agent Decision (automatic):
    │   has_features()?
    │   ├─ Yes → CODING AGENT (implement/improve)
    │   └─ No → INITIALIZER AGENT (analyze codebase, create features)
```

### Key Insight

The existing `agent.py` decision logic already handles imports:
- **With features.db**: Skip initializer, go to coding
- **Without features.db**: Run initializer to create features

For **Analyzer Agent** (Option B), add:
1. New template: `analyzer_prompt.template.md`
2. New detection: Check for `.analyze_mode` file
3. New prompt loader: `get_analyzer_prompt()`
