# Infrastructure & Configuration - Context Documentation

## Dependencies

### Python (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| `claude-agent-sdk` | ≥0.1.0 | Claude Agent SDK |
| `python-dotenv` | ≥1.0.0 | Environment variables |
| `sqlalchemy` | ≥2.0.0 | ORM for SQLite |
| `fastapi` | ≥0.115.0 | REST API server |
| `uvicorn[standard]` | ≥0.32.0 | ASGI server |
| `websockets` | ≥13.0 | WebSocket support |
| `python-multipart` | ≥0.0.17 | File uploads |
| `psutil` | ≥6.0.0 | Process management |
| `aiofiles` | ≥24.0.0 | Async file I/O |
| `ruff` | ≥0.8.0 | Python linter |
| `mypy` | ≥1.13.0 | Type checker |
| `pytest` | ≥8.0.0 | Testing |

### Node.js (ui/package.json)

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^18.3.1 | UI framework |
| `@tanstack/react-query` | ^5.60.0 | Data fetching |
| `tailwindcss` | ^4.0.0-beta.4 | CSS framework |
| `lucide-react` | ^0.460.0 | Icons |
| `@radix-ui/react-*` | ^1.x | Accessible components |
| `vite` | ^5.4.10 | Build tool |
| `typescript` | ~5.6.2 | Type system |

---

## Build Configuration

### Python (pyproject.toml)

```toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
ignore = ["E501", "E402", "E712"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
```

### Vite (vite.config.ts)

```typescript
plugins: [react(), tailwindcss()]
resolve.alias: { '@': './src' }
server.proxy:
  '/api' → http://127.0.0.1:8888
  '/ws' → ws://127.0.0.1:8888
```

### TypeScript (tsconfig.json)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "strict": true,
    "jsx": "react-jsx",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

---

## CI/CD Pipeline (.github/workflows/ci.yml)

**Triggers:** PR/push to main/master

### Python Job
1. Setup Python 3.11
2. `pip install -r requirements.txt`
3. `ruff check .`
4. `python test_security.py`

### UI Job
1. Setup Node 20
2. `npm ci`
3. `npm run lint`
4. `npm run build`

---

## Launcher Scripts

### CLI (start.bat / start.sh)
1. Check Claude CLI installed
2. Check credentials at `~/.claude/.credentials.json`
3. Prompt for login if missing
4. Create venv if needed
5. Install dependencies
6. Run `python start.py`

### Web UI (start_ui.bat / start_ui.sh)
1. Check Python available
2. Create venv if needed
3. Install dependencies
4. Run `python start_ui.py`

---

## Project Structure

```
autocoderCOPIA1/
├── start.bat, start.sh           # CLI launchers
├── start_ui.bat, start_ui.sh     # UI launchers
├── start.py                      # CLI menu
├── start_ui.py                   # FastAPI launcher
├── autonomous_agent_demo.py      # Agent entry point
├── agent.py                      # Agent loop
├── client.py                     # Claude SDK config
├── security.py                   # Bash security
├── prompts.py                    # Template loading
├── progress.py                   # Progress tracking
├── registry.py                   # Project registry
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .github/workflows/ci.yml
├── .claude/
│   ├── commands/create-spec.md
│   ├── skills/frontend-design/
│   └── templates/*.template.md
├── api/
│   ├── database.py
│   └── migration.py
├── mcp_server/
│   └── feature_mcp.py
├── server/
│   ├── main.py
│   ├── schemas.py
│   ├── websocket.py
│   ├── routers/
│   └── services/
├── ui/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── styles/
│   ├── dist/
│   ├── package.json
│   └── vite.config.ts
└── docs/context/
```

### Generated Project Structure
```
{project}/
├── features.db           # SQLite with features
├── .agent.lock           # Session lock
├── prompts/
│   ├── app_spec.txt
│   ├── initializer_prompt.md
│   └── coding_prompt.md
├── claude-progress.txt
├── init.sh
├── .git/
└── [source code]
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `PROGRESS_N8N_WEBHOOK_URL` | N8N webhook for notifications | None |
| `VITE_API_PORT` | Backend port for frontend | 8888 |

### Credential Storage
- `~/.claude/.credentials.json` - Claude CLI auth
- `~/.autocoder/registry.db` - Project registry

---

## License

GNU Affero General Public License v3.0 (AGPL-3.0)
Copyright (C) 2026 Leon van Zyl
