# Autonomous Coding Agent

A long-running autonomous coding agent powered by the Claude Agent SDK. This tool can build complete applications over multiple sessions using a two-agent pattern (initializer + coding agent). Includes a React-based UI for monitoring progress in real-time.

## 🚀 NEW Features

**Parallel Agent Execution** - Run multiple agents simultaneously for 3x faster development! ✨
**Smart Model Selection** - Automatic Opus/Haiku routing for optimal cost/speed balance 💡
**Knowledge Base Learning** - System learns from every feature and gets smarter over time 🧠

---

## Video Walkthrough

[![Watch the video](https://img.youtube.com/vi/YW09hhnVqNM/maxresdefault.jpg)](https://youtu.be/YW09hhnVqNM)

> **[Watch the setup and usage guide →](https://youtu.be/YW09hhnVqNM)**

---

## Prerequisites

### Claude Code CLI (Required)

This project requires the Claude Code CLI to be installed. Install it using one of these methods:

**macOS / Linux:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

### Authentication

You need one of the following:

- **Claude Pro/Max Subscription** - Use `claude login` to authenticate (recommended for parallel agents)
- **Anthropic API Key** - Pay-per-use from https://console.anthropic.com/

---

## Quick Start

### Option 1: Web UI (Recommended)

**Windows:**
```cmd
start_ui.bat
```

**macOS / Linux:**
```bash
./start_ui.sh
```

This launches the React-based web UI at `http://localhost:5173` with:
- Project selection and creation
- Kanban board view of features
- Real-time agent output streaming
- Start/pause/stop controls
- **NEW:** Parallel agent controls
- **NEW:** Model settings configuration
- **NEW:** Knowledge base visualization

### Option 2: CLI Mode

**Windows:**
```cmd
start.bat
```

**macOS / Linux:**
```bash
./start.sh
```

The start script will:
1. Check if Claude CLI is installed
2. Check if you're authenticated (prompt to run `claude login` if not)
3. Create a Python virtual environment
4. Install dependencies
5. Launch the main menu

### Option 3: Parallel Agents (NEW!) ⚡

**Run 3 agents in parallel for 3x faster development:**

```bash
# CLI mode
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 3 \
  --preset balanced

# Or via UI: Click "⚡ Parallel" button → Start 3 Agents
```

**Model Presets:**
- `quality` - Opus only (maximum quality, highest cost)
- `balanced` ⭐ - Opus + Haiku (recommended for Pro, best value)
- `economy` - Opus + Sonnet + Haiku (cost optimization)
- `cheap` - Sonnet + Haiku (budget-friendly)
- `experimental` - All models with AI selection

---

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (First Session):** Reads your app specification, creates features in a SQLite database (`features.db`), sets up the project structure, and initializes git.

2. **Coding Agent (Subsequent Sessions):** Picks up where the previous session left off, implements features one by one, and marks them as passing in the database.

### NEW: Parallel Agent Mode 🚀

**Traditional (Sequential):**
```
Feature 1 → Feature 2 → Feature 3 → Feature 4
Total: 40 minutes
```

**Parallel (3 Agents):**
```
Agent 1: Feature 1 (10 min) ┐
Agent 2: Feature 2 (10 min) ├> Total: 10 minutes (3x faster!)
Agent 3: Feature 3 (10 min) ┘
```

**How it works:**
1. Manager atomically claims 3 features from database
2. Spawns 3 parallel agents with different models:
   - Agent 1: Opus for backend (complex)
   - Agent 2: Haiku for tests (simple)
   - Agent 3: Opus for frontend (complex)
3. All run simultaneously using real Claude agent sessions
4. Knowledge base learns from each completion
5. Database updates automatically

**Benefits:**
- 3x faster development (10 min vs 30 min for 3 features)
- Smart cost optimization (Haiku for simple tasks)
- Knowledge base gets smarter with each feature
- No conflicts (atomic database locking)

### NEW: Knowledge Base Learning 🧠

The system learns from every feature implementation:

```python
# First time implementing "User Authentication"
Feature: User Authentication (backend)
Model: Opus
Approach: JWT with refresh tokens
Result: Success
→ Stored in knowledge base

# Second time implementing "Admin Authentication"
Knowledge: "User Auth used JWT successfully (95% success rate with Opus)"
Agent applies: JWT with variations for admin role
Result: Success, faster (8 min vs 10 min)

# Third time implementing "API Authentication"
Knowledge: 2 similar features, both used JWT
Agent knows: JWT is the proven approach
Result: Success, even faster (6 min)
```

**What gets stored:**
- Feature category, name, description
- Implementation approach used
- Files changed/created
- Model used and success rate
- Attempts needed
- Lessons learned

**How it helps:**
- Finds similar past features
- Recommends best approaches
- Suggests optimal model for category
- Provides reference examples in prompts
- Tracks success rates over time

### Smart Model Selection

Automatic routing based on feature complexity:

| Feature Type | Model | Why |
|--------------|-------|-----|
| Authentication | Opus | Security-critical |
| Database Schema | Opus | Complex architecture |
| Testing | Haiku | Simple, fast |
| Documentation | Haiku | Straightforward |
| Frontend | Opus | Complex UI logic |
| CRUD | Haiku | Simple patterns |

---

## Feature Management

Features are stored in SQLite via SQLAlchemy and managed through an MCP server that exposes tools to the agent:

**Core Tools:**
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)

**NEW: Parallel Execution Tools:**
- `feature_claim_batch(count, agent_id)` - Atomically claim multiple features
- `feature_release(feature_id, status, notes)` - Release feature with completion status
- `feature_get_claimed(agent_id)` - Get all currently claimed features

---

## Session Management

- Each session runs with a fresh context window
- Progress is persisted via SQLite database and git commits
- The agent auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run the start script again to resume

---

## Important Timing Expectations

> **Note: Building complete applications takes time!**

- **First session (initialization):** The agent generates feature test cases. This takes several minutes and may appear to hang - this is normal.

- **Subsequent sessions:** Each coding iteration can take **5-15 minutes** depending on complexity.

- **Full app:** Building all features typically requires **many hours** of total runtime across multiple sessions.

- **NEW with Parallel Agents:** 3 agents = **3x faster**! 10 features that took 100 minutes now take ~35 minutes.

**Tip:** The feature count in the prompts determines scope. For faster demos, you can modify your app spec to target fewer features (e.g., 20-50 features for a quick demo).

---

## Project Structure

```
autonomous-coding/
├── start.bat                 # Windows CLI start script
├── start.sh                  # macOS/Linux CLI start script
├── start_ui.bat              # Windows Web UI start script
├── start_ui.sh               # macOS/Linux Web UI start script
├── start.py                  # CLI menu and project management
├── start_ui.py               # Web UI backend (FastAPI server launcher)
├── autonomous_agent_demo.py  # Agent entry point
├── agent.py                  # Agent session logic
├── agent_manager.py          # NEW: Parallel agent orchestrator
├── client.py                 # Claude SDK client configuration
├── model_settings.py         # NEW: Model selection system
├── knowledge_base.py         # NEW: Knowledge base learning
├── security.py               # Bash command allowlist and validation
├── progress.py               # Progress tracking utilities
├── prompts.py                # Prompt loading utilities
├── api/
│   └── database.py           # SQLAlchemy models (Feature table)
├── mcp_server/
│   └── feature_mcp.py        # MCP server for feature management tools
├── server/
│   ├── main.py               # FastAPI REST API server
│   ├── websocket.py          # WebSocket handler for real-time updates
│   ├── schemas.py            # Pydantic schemas
│   ├── routers/              # API route handlers
│   │   ├── model_settings.py      # NEW: Model settings API
│   │   ├── parallel_agents.py     # NEW: Parallel agents API
│   │   └── ...
│   └── services/             # Business logic services
├── ui/                       # React frontend
│   ├── src/
│   │   ├── App.tsx           # Main app component
│   │   ├── components/
│   │   │   ├── ModelSettingsPanel.tsx    # NEW: Model configuration
│   │   │   ├── ParallelAgentsControl.tsx # NEW: Parallel control
│   │   │   └── AgentStatusGrid.tsx       # NEW: Status display
│   │   ├── hooks/            # React Query and WebSocket hooks
│   │   │   ├── useModelSettings.ts        # NEW: Model hooks
│   │   │   └── useParallelAgents.ts       # NEW: Parallel hooks
│   │   └── lib/              # API client and types
│   ├── package.json
│   └── vite.config.ts
├── .claude/
│   ├── commands/
│   │   └── create-spec.md    # /create-spec slash command
│   ├── skills/               # Claude Code skills
│   └── templates/            # Prompt templates
├── research/                 # NEW: Research documentation
│   ├── subagent-parallel-execution.md
│   ├── repository-analysis-report.md
│   ├── PARALLEL-IMPLEMENTATION-GUIDE.md
│   └── COMPLETE-IMPLEMENTATION.md
├── generations/              # Generated projects go here
├── requirements.txt          # Python dependencies
└── .env                      # Optional configuration (N8N webhook)
```

---

## Generated Project Structure

After the agent runs, your project directory will contain:

```
generations/my_project/
├── features.db               # SQLite database (feature test cases)
├── knowledge.db              # NEW: Knowledge base (learned patterns)
├── prompts/
│   ├── app_spec.txt          # Your app specification
│   ├── initializer_prompt.md # First session prompt
│   └── coding_prompt.md      # Continuation session prompt
├── init.sh                   # Environment setup script
├── claude-progress.txt       # Session progress notes
└── [application files]       # Generated application code
```

---

## Running the Generated Application

After the agent completes (or pauses), you can run the generated application:

```bash
cd generations/my_project

# Run the setup script created by the agent
./init.sh

# Or manually (typical for Node.js apps):
npm install
npm run dev
```

The application will typically be available at `http://localhost:3000` or similar.

---

## Security Model

This project uses a defense-in-depth security approach (see `security.py` and `client.py`):

1. **OS-level Sandbox:** Bash commands run in an isolated environment
2. **Filesystem Restrictions:** File operations restricted to the project directory only
3. **Bash Allowlist:** Only specific commands are permitted:
   - File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
   - Node.js: `npm`, `node`
   - Version control: `git`
   - Process management: `ps`, `lsof`, `sleep`, `pkill` (dev processes only)

Commands not in the allowlist are blocked by the security hook.

---

## Web UI Development

The React UI is located in the `ui/` directory.

### Development Mode

```bash
cd ui
npm install
npm run dev      # Development server with hot reload
```

### Building for Production

```bash
cd ui
npm run build    # Builds to ui/dist/
```

**Note:** The `start_ui.bat`/`start_ui.sh` scripts serve the pre-built UI from `ui/dist/`. After making UI changes, run `npm run build` to see them when using the start scripts.

### Tech Stack

- React 18 with TypeScript
- TanStack Query for data fetching
- Tailwind CSS v4 with neobrutalism design
- Radix UI components
- WebSocket for real-time updates

### Real-time Updates

The UI receives live updates via WebSocket (`/ws/projects/{project_name}`):
- `progress` - Test pass counts
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (streamed from subprocess stdout)
- `feature_update` - Feature status changes

---

## NEW: Parallel Agent Usage

### Starting Parallel Agents

**Via CLI:**
```bash
# Show available presets
python agent_manager.py --show-presets

# Start 3 agents with balanced preset (recommended)
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 3 \
  --preset balanced

# Custom model selection
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 3 \
  --models opus,haiku

# Maximum quality (Opus only)
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 2 \
  --models opus
```

**Via UI:**
1. Select a project
2. Click **⚡ Parallel** button (or press `P`)
3. Adjust agent count slider (1-5)
4. Click "Start X Agents"
5. Watch real-time status grid

### Expected Performance

| Features | Sequential | 3 Agents | Speedup |
|----------|------------|----------|---------|
| 5 | 50 min | 18 min | 2.8x |
| 10 | 100 min | 35 min | 2.9x |
| 20 | 200 min | 70 min | 2.9x |

---

## NEW: Knowledge Base Usage

### Inspecting Learned Knowledge

```bash
# See what the system has learned
python inspect_knowledge.py

# Output:
# Knowledge Base Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Total Patterns: 15
# Success Rate: 93%
#
# Best Models by Category:
#   backend: opus (95% success)
#   frontend: opus (100% success)
#   testing: haiku (100% success)
#   documentation: haiku (90% success)
#
# Common Approaches:
#   Backend: "JWT authentication" (3 features)
#   Frontend: "React hooks with useState" (4 features)
#   Testing: "Jest with react-testing-library" (3 features)
```

### Knowledge Base Demo

```bash
# See knowledge base in action
python knowledge_base_demo.py

# Demonstrates:
# - Storing implementation patterns
# - Finding similar features
# - Generating reference prompts
# - Tracking model performance
```

---

## Configuration (Optional)

### N8N Webhook Integration

The agent can send progress notifications to an N8N webhook. Create a `.env` file:

```bash
# Optional: N8N webhook for progress notifications
PROGRESS_N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
```

When test progress increases, the agent sends:

```json
{
  "event": "test_progress",
  "passing": 45,
  "total": 200,
  "percentage": 22.5,
  "project": "my_project",
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

---

## Customization

### Changing the Application

Use the `/create-spec` command when creating a new project, or manually edit the files in your project's `prompts/` directory:
- `app_spec.txt` - Your application specification
- `initializer_prompt.md` - Controls feature generation

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

### NEW: Customizing Model Selection

Edit `~/.autocoder/model_settings.json` or use the UI:

```json
{
  "preset": "balanced",
  "available_models": ["opus", "haiku"],
  "auto_detect_simple": true,
  "category_mapping": {
    "frontend": "opus",
    "backend": "opus",
    "testing": "haiku",
    "documentation": "haiku",
    "infrastructure": "opus"
  }
}
```

---

## Troubleshooting

**"Claude CLI not found"**
Install the Claude Code CLI using the instructions in the Prerequisites section.

**"Not authenticated with Claude"**
Run `claude login` to authenticate. The start script will prompt you to do this automatically.

**"Appears to hang on first run"**
This is normal. The initializer agent is generating detailed test cases, which takes significant time. Watch for `[Tool: ...]` output to confirm the agent is working.

**"Command blocked by security hook"**
The agent tried to run a command not in the allowlist. This is the security system working as intended. If needed, add the command to `ALLOWED_COMMANDS` in `security.py`.

**NEW: "Agents conflicting on same feature"**
This shouldn't happen! The atomic feature claiming (`with_for_update()` database locking) prevents race conditions. If you see this, there's a bug.

**NEW: "Knowledge base not learning"**
Check that `knowledge.db` exists and is writable. Run `python inspect_knowledge.py` to verify.

---

## Architecture Documentation

Detailed documentation is available in the `research/` directory:

- **subagent-parallel-execution.md** - Research on parallel agent execution
- **repository-analysis-report.md** - Analysis of 4 open-source agent systems
- **PARALLEL-IMPLEMENTATION-GUIDE.md** - Implementation guide for parallel execution
- **COMPLETE-IMPLEMENTATION.md** - Status of all features

---

## License

Internal Anthropic use.
