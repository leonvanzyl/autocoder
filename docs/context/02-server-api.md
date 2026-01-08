# FastAPI Server API - Context Documentation

## Overview

The FastAPI server provides REST endpoints and WebSocket connections for the React UI.

**Base URL:** `http://127.0.0.1:8888`

## File Index

| File | Purpose |
|------|---------|
| `server/main.py` | FastAPI app setup, middleware, routes |
| `server/schemas.py` | Pydantic request/response models |
| `server/websocket.py` | WebSocket connection management |
| `server/routers/projects.py` | Project CRUD endpoints |
| `server/routers/features.py` | Feature management endpoints |
| `server/routers/agent.py` | Agent control (start/stop/pause/resume) |
| `server/routers/filesystem.py` | Filesystem browser API |
| `server/routers/spec_creation.py` | Spec creation WebSocket |
| `server/routers/assistant_chat.py` | Assistant chat WebSocket |
| `server/services/process_manager.py` | Agent subprocess management |
| `server/services/spec_chat_session.py` | Spec chat with Claude |
| `server/services/assistant_chat_session.py` | Assistant conversations |
| `server/services/assistant_database.py` | Chat persistence |

---

## REST API Reference

### Projects (`/api/projects`)

#### List All Projects
```
GET /api/projects
Response: ProjectSummary[]
```

#### Create Project
```
POST /api/projects
Body: { name, path, spec_method: "claude"|"manual" }
Response: ProjectSummary
```

#### Get Project Details
```
GET /api/projects/{name}
Response: ProjectDetail
```

#### Delete Project
```
DELETE /api/projects/{name}?delete_files=false
Response: { success, message }
```

#### Get/Update Prompts
```
GET /api/projects/{name}/prompts
PUT /api/projects/{name}/prompts
```

#### Get Stats
```
GET /api/projects/{name}/stats
Response: { passing, in_progress, total, percentage }
```

---

### Features (`/api/projects/{project_name}/features`)

#### List Features
```
GET /api/projects/{project_name}/features
Response: { pending: [], in_progress: [], done: [] }
```

#### Create Feature
```
POST /api/projects/{project_name}/features
Body: { category, name, description, steps[], priority? }
```

#### Delete Feature
```
DELETE /api/projects/{project_name}/features/{id}
```

#### Skip Feature
```
PATCH /api/projects/{project_name}/features/{id}/skip
```

---

### Agent Control (`/api/projects/{project_name}/agent`)

#### Get Status
```
GET /api/projects/{project_name}/agent/status
Response: { status, pid, started_at, yolo_mode }
Status: "stopped" | "running" | "paused" | "crashed"
```

#### Start Agent
```
POST /api/projects/{project_name}/agent/start
Body: { yolo_mode: false }
```

#### Stop/Pause/Resume
```
POST /api/projects/{project_name}/agent/stop
POST /api/projects/{project_name}/agent/pause
POST /api/projects/{project_name}/agent/resume
```

---

### Filesystem (`/api/filesystem`)

#### List Directory
```
GET /api/filesystem/list?path={path}&show_hidden=false
Response: { current_path, parent_path, entries[], drives[] }
```

#### Validate Path
```
POST /api/filesystem/validate?path={path}
Response: { valid, exists, is_directory, can_read, can_write }
```

#### Create Directory
```
POST /api/filesystem/create-directory
Body: { parent_path, name }
```

---

## WebSocket Protocols

### Project Updates (`/ws/projects/{project_name}`)

**Server → Client Messages:**
```json
{"type": "progress", "passing": 5, "total": 10, "percentage": 50.0}
{"type": "agent_status", "status": "running"}
{"type": "log", "line": "...", "timestamp": "..."}
```

### Spec Creation (`/api/spec/ws/{project_name}`)

**Client → Server:**
```json
{"type": "start"}
{"type": "message", "content": "...", "attachments": [...]}
{"type": "answer", "answers": {...}, "tool_id": "..."}
```

**Server → Client:**
```json
{"type": "text", "content": "..."}
{"type": "question", "questions": [...], "tool_id": "..."}
{"type": "spec_complete", "path": "..."}
{"type": "complete", "path": "..."}
```

### Assistant Chat (`/api/assistant/ws/{project_name}`)

**Client → Server:**
```json
{"type": "start", "conversation_id": null}
{"type": "message", "content": "..."}
```

**Server → Client:**
```json
{"type": "conversation_created", "conversation_id": 42}
{"type": "text", "content": "..."}
{"type": "tool_call", "tool": "Read", "input": {...}}
{"type": "response_done"}
```

---

## Pydantic Schemas

### Project Schemas
```python
class ProjectStats(BaseModel):
    passing: int
    in_progress: int
    total: int
    percentage: float

class ProjectSummary(BaseModel):
    name: str
    path: str
    has_spec: bool
    stats: ProjectStats

class ProjectCreate(BaseModel):
    name: str
    path: str
    spec_method: Literal["claude", "manual"]
```

### Feature Schemas
```python
class FeatureCreate(BaseModel):
    category: str
    name: str
    description: str
    steps: list[str]
    priority: int | None = None

class FeatureResponse(BaseModel):
    id: int
    priority: int
    category: str
    name: str
    description: str
    steps: list[str]
    passes: bool
    in_progress: bool
```

### Agent Schemas
```python
class AgentStatus(BaseModel):
    status: Literal["stopped", "running", "paused", "crashed"]
    pid: int | None
    started_at: datetime | None
    yolo_mode: bool
```

---

## Security

### Localhost-Only Middleware
```python
@app.middleware("http")
async def require_localhost(request, call_next):
    if request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Localhost access only")
```

### Blocked Filesystem Paths
- Windows: `C:\Windows`, `C:\Program Files`
- macOS: `/System`, `/Library`, `/usr`, `/bin`
- Linux: `/etc`, `/var`, `/usr`, `/root`, `/tmp`
- Universal: `~/.ssh`, `~/.aws`, `~/.gnupg`

### Project Name Validation
```python
Pattern: ^[a-zA-Z0-9_-]{1,50}$
```

---

## Process Manager

### AgentProcessManager Class

```python
class AgentProcessManager:
    status: "stopped" | "running" | "paused" | "crashed"
    process: subprocess.Popen | None

    async def start(yolo_mode: bool) -> tuple[bool, str]
    async def stop() -> tuple[bool, str]
    async def pause() -> tuple[bool, str]
    async def resume() -> tuple[bool, str]
```

**Subprocess Command:**
```bash
python autonomous_agent_demo.py --project-dir {path} [--yolo]
```

**Lock File:** `{project_dir}/.agent.lock`

---

## Adding New Endpoints

### Step 1: Define Schema (schemas.py)
```python
class ImportRequest(BaseModel):
    name: str
    path: str
```

### Step 2: Create Router Endpoint
```python
@router.post("/import", response_model=ProjectSummary)
async def import_project(request: ImportRequest):
    # Implementation
    pass
```

### Step 3: Register Router (main.py)
```python
app.include_router(import_router)
```
