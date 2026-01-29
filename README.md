# AutoCoder

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/leonvanzyl)

A long-running autonomous coding agent powered by the Claude Agent SDK. This tool can build complete applications over multiple sessions using a two-agent pattern (initializer + coding agent). Includes a React-based UI for monitoring progress in real-time.

## Video Tutorial

[![Watch the tutorial](https://img.youtube.com/vi/lGWFlpffWk4/hqdefault.jpg)](https://youtu.be/lGWFlpffWk4)

> **[Watch the setup and usage guide →](https://youtu.be/lGWFlpffWk4)**

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

- **Claude Pro/Max Subscription** - Use `claude login` to authenticate (recommended)
- **Anthropic API Key** - Pay-per-use from https://console.anthropic.com/

### Optional: Gemini API (assistant chat only)
- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional, default `gemini-1.5-flash`)
- `GEMINI_BASE_URL` (optional, default `https://generativelanguage.googleapis.com/v1beta/openai`)

Notes: Gemini is used for assistant chat when configured; coding agents still run on Claude/Anthropic (tools are not available in Gemini mode).

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
- **Project Assistant** - AI chat for managing features and exploring the codebase

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

### Creating or Continuing a Project

You'll see options to:
- **Create new project** - Start a fresh project with AI-assisted spec generation
- **Continue existing project** - Resume work on a previous project

For new projects, you can use the built-in `/create-spec` command to interactively create your app specification with Claude's help.

---

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (First Session):** Reads your app specification, creates features in a SQLite database (`features.db`), sets up the project structure, and initializes git.

2. **Coding Agent (Subsequent Sessions):** Picks up where the previous session left off, implements features one by one, and marks them as passing in the database.

### Feature Management

Features are stored in SQLite via SQLAlchemy and managed through an MCP server that exposes tools to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)
- `feature_create` - Create a single feature
- `feature_update` - Update a feature's fields
- `feature_delete` - Delete a feature from the backlog

### Project Assistant

The Web UI includes a **Project Assistant** - an AI-powered chat interface for each project. Click the chat button in the bottom-right corner to open it.

**Capabilities:**
- **Explore the codebase** - Ask questions about files, architecture, and implementation details
- **Manage features** - Create, edit, delete, and deprioritize features via natural language
- **Get feature details** - Ask about specific features, their status, and test steps

**Conversation Persistence:**
- Conversations are automatically saved to `assistant.db` in the registered project directory
- When you navigate away and return, your conversation resumes where you left off

### Session Management

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
├── client.py                 # Claude SDK client configuration
├── security.py               # Bash command allowlist and validation
├── progress.py               # Progress tracking utilities
├── prompts.py                # Prompt loading utilities
├── registry.py               # Project registry (maps names to paths)
├── api/
│   └── database.py           # SQLAlchemy models (Feature table)
├── mcp_server/
│   └── feature_mcp.py        # MCP server for feature management tools
├── server/
│   ├── main.py               # FastAPI REST API server
│   ├── websocket.py          # WebSocket handler for real-time updates
│   ├── schemas.py            # Pydantic schemas
│   ├── routers/              # API route handlers (projects, features, agent, assistant)
│   └── services/             # Business logic (assistant chat sessions, database)
├── ui/                       # React frontend
│   ├── src/
│   │   ├── App.tsx           # Main app component
│   │   ├── hooks/            # React Query and WebSocket hooks
│   │   └── lib/              # API client and types
│   ├── package.json
│   └── vite.config.ts
├── .claude/
│   ├── commands/
│   │   └── create-spec.md    # /create-spec slash command
│   ├── skills/               # Claude Code skills
│   └── templates/            # Prompt templates
├── generations/              # Default location for new projects (can be anywhere)
├── requirements.txt          # Python dependencies
└── .env                      # Optional configuration (N8N webhook)
```

---

## Project Registry and Structure

Projects can be stored in any directory on your filesystem. The **project registry** (`registry.py`) maps project names to their paths, stored in `~/.autocoder/registry.db` (SQLite).

When you create or register a project, the registry tracks its location. This allows projects to live anywhere - in `generations/`, your home directory, or any other path.

Each registered project directory will contain:

```text
<registered_project_path>/
├── features.db               # SQLite database (feature test cases)
├── assistant.db              # SQLite database (assistant chat history)
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

After the agent completes (or pauses), you can run the generated application. Navigate to your project's registered path (the directory you selected or created when setting up the project):

```bash
cd /path/to/your/registered/project

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

- React 19 with TypeScript
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

## Configuration (Optional)

### Web UI Authentication

For deployments where the Web UI is exposed beyond localhost, you can enable HTTP Basic Authentication. Add these to your `.env` file:

```bash
# Both variables required to enable authentication
BASIC_AUTH_USERNAME=admin
BASIC_AUTH_PASSWORD=your-secure-password

# Also enable remote access
AUTOCODER_ALLOW_REMOTE=1
```

When enabled:
- All HTTP requests require the `Authorization: Basic <credentials>` header
- WebSocket connections support auth via header or `?token=base64(user:pass)` query parameter
- The browser will prompt for username/password automatically

> ⚠️ **CRITICAL SECURITY WARNINGS**
>
> **HTTPS Required:** `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` must **only** be used over HTTPS connections. Basic Authentication transmits credentials as base64-encoded text (not encrypted), making them trivially readable by anyone intercepting plain HTTP traffic. **Never use Basic Auth over unencrypted HTTP.**
>
> **WebSocket Query Parameter is Insecure:** The `?token=base64(user:pass)` query parameter method for WebSocket authentication should be **avoided or disabled** whenever possible. Risks include:
> - **Browser history exposure** – URLs with tokens are saved in browsing history
> - **Server log leakage** – Query strings are often logged by web servers, proxies, and CDNs
> - **Referer header leakage** – The token may be sent to third-party sites via the Referer header
> - **Shoulder surfing** – Credentials visible in the address bar can be observed by others
>
> Prefer using the `Authorization` header for WebSocket connections when your client supports it.

#### Securing Your `.env` File

- **Restrict filesystem permissions** – Ensure only the application user can read the `.env` file (e.g., `chmod 600 .env` on Unix systems)
- **Never commit credentials to version control** – Add `.env` to your `.gitignore` and never commit `BASIC_AUTH_USERNAME` or `BASIC_AUTH_PASSWORD` values
- **Use a secrets manager for production** – For production deployments, prefer environment variables injected via a secrets manager (e.g., HashiCorp Vault, AWS Secrets Manager, Docker secrets) rather than a plaintext `.env` file

#### Configuration Notes

- `AUTOCODER_ALLOW_REMOTE=1` explicitly enables remote access (binding to `0.0.0.0` instead of `127.0.0.1`). Without this, the server only accepts local connections.
- **For localhost development, authentication is not required.** Basic Auth is only enforced when both username and password are set, so local development workflows remain frictionless.

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

### Using GLM Models (Alternative to Claude)

To use Zhipu AI's GLM models instead of Claude, add these variables to your `.env` file in the AutoCoder directory:

```bash
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
ANTHROPIC_AUTH_TOKEN=your-zhipu-api-key
API_TIMEOUT_MS=3000000
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-4.7
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-4.7
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.5-air
```

This routes AutoCoder's API requests through Zhipu's Claude-compatible API, allowing you to use GLM-4.7 and other models. **This only affects AutoCoder** - your global Claude Code settings remain unchanged.

Get an API key at: https://z.ai/subscribe

---

## Customization

### Changing the Application

Use the `/create-spec` command when creating a new project, or manually edit the files in your project's `prompts/` directory:
- `app_spec.txt` - Your application specification
- `initializer_prompt.md` - Controls feature generation

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

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

---

## CI/CD and Deployment

- PR Check workflow (`.github/workflows/pr-check.yml`) runs Python lint/security tests and UI lint/build on every PR to `main` or `master`.
- Push CI (`.github/workflows/ci.yml`) runs the same validations on direct pushes to `main` and `master`, then builds and pushes a Docker image to GHCR (`ghcr.io/<owner>/<repo>:latest` and `:sha`).
- Deploy to VPS (`.github/workflows/deploy.yml`) runs after Push CI succeeds, SSHes into your VPS, prunes old Docker artifacts, pulls the target branch, pulls the GHCR `:sha` image (falls back to `:latest`), restarts with `docker compose up -d`, and leaves any existing `.env` untouched. It finishes with an HTTP smoke check on `http://127.0.0.1:8888/health`.
- Repo secrets required: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_DEPLOY_PATH` (use an absolute path like `/opt/autocoder`); optional `VPS_BRANCH` (defaults to `master`) and `VPS_PORT` (defaults to `22`). The VPS needs git, Docker + Compose plugin installed, and the repo cloned at `VPS_DEPLOY_PATH` with your `.env` present.
- Local Docker run: `docker compose up -d --build` exposes the app on `http://localhost:8888`; data under `~/.autocoder` persists via the `autocoder-data` volume.

### Branch protection
To require the “PR Check” workflow before merging:
- GitHub UI: Settings → Branches → Add rule for `main` (and `master` if used) → enable **Require status checks to pass before merging** → select `PR Check` → save.
- GitHub CLI:  
  ```bash
  gh api -X PUT repos/<owner>/<repo>/branches/main/protection \
    -F required_status_checks.strict=true \
    -F required_status_checks.contexts[]="PR Check" \
    -F enforce_admins=true \
    -F required_pull_request_reviews.dismiss_stale_reviews=true \
    -F restrictions=
  ```

---

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details.
Copyright (C) 2026 Leon van Zyl (https://leonvanzyl.com)
