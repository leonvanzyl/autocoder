# Fork Changelog

All notable changes to this fork are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Fork documentation (FORK_README.md, FORK_CHANGELOG.md)
- Configuration system via `.autocoder/config.json`

## [2025-01-21] Enhanced Logging System

### Added
- New module: `structured_logging.py` - Structured JSON logging with SQLite storage
- New router: `server/routers/logs.py` - REST API for log querying and export

### Log Format
```json
{
  "timestamp": "2025-01-21T10:30:00.000Z",
  "level": "info|warn|error",
  "agent_id": "coding-42",
  "feature_id": 42,
  "tool_name": "feature_mark_passing",
  "duration_ms": 150,
  "message": "Feature marked as passing"
}
```

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/logs/{project_name}` | GET | Query logs with filters |
| `/api/logs/{project_name}/timeline` | GET | Get activity timeline |
| `/api/logs/{project_name}/stats` | GET | Get per-agent statistics |
| `/api/logs/export` | POST | Export logs to file |
| `/api/logs/{project_name}/download/{filename}` | GET | Download exported file |

### Features
- Filter by level, agent, feature, tool
- Full-text search in messages
- Timeline view bucketed by configurable intervals
- Per-agent statistics (info/warn/error counts)
- Export to JSON, JSONL, CSV formats
- Auto-cleanup old logs (configurable max entries)

### Usage
```python
from structured_logging import get_logger, get_log_query

# Create logger for an agent
logger = get_logger(project_dir, agent_id="coding-1")
logger.info("Starting feature", feature_id=42)
logger.error("Test failed", feature_id=42, tool_name="playwright")

# Query logs
query = get_log_query(project_dir)
logs = query.query(level="error", agent_id="coding-1", limit=50)
timeline = query.get_timeline(since_hours=24)
stats = query.get_agent_stats()
```

---

## [2025-01-21] Import Project API (Import Projects - Phase 2)

### Added
- New router: `server/routers/import_project.py` - REST API for project import
- New module: `analyzers/feature_extractor.py` - Transform routes to features

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/import/analyze` | POST | Analyze directory, detect stack |
| `/api/import/extract-features` | POST | Generate features from analysis |
| `/api/import/create-features` | POST | Create features in database |
| `/api/import/quick-detect` | GET | Quick stack preview |

### Feature Extraction
- Routes -> "View X page" navigation features
- API endpoints -> "API: Create/List/Update/Delete X" features
- Infrastructure -> Startup, health check features
- Each feature includes category, name, description, steps

### Usage
```bash
# 1. Analyze project
curl -X POST http://localhost:8888/api/import/analyze \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/existing/project"}'

# 2. Extract features
curl -X POST http://localhost:8888/api/import/extract-features \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/existing/project"}'

# 3. Create features in registered project
curl -X POST http://localhost:8888/api/import/create-features \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my-project", "features": [...]}'
```

---

## [2025-01-21] Stack Detector (Import Projects - Phase 1)

### Added
- New module: `analyzers/` - Codebase analysis for project import
- `analyzers/base_analyzer.py` - Abstract base class with TypedDicts
- `analyzers/stack_detector.py` - Orchestrator for running all analyzers
- `analyzers/react_analyzer.py` - React, Vite, Next.js detection
- `analyzers/node_analyzer.py` - Express, NestJS, Fastify detection
- `analyzers/python_analyzer.py` - FastAPI, Django, Flask detection
- `analyzers/vue_analyzer.py` - Vue.js, Nuxt detection

### Features
- Auto-detect tech stack from package.json, requirements.txt, config files
- Extract routes from React Router, Next.js file-based, Vue Router
- Extract API endpoints from Express, FastAPI, Django, NestJS
- Extract components from components/, views/, models/ directories
- Confidence scoring for each detected stack

### Usage
```python
from analyzers import StackDetector

detector = StackDetector(project_dir)
result = detector.detect()  # Full analysis
quick = detector.detect_quick()  # Fast preview
```

### Supported Stacks
| Stack | Indicators |
|-------|-----------|
| React | "react" in package.json, src/App.tsx |
| Next.js | next.config.js, pages/ or app/ dirs |
| Vue.js | "vue" in package.json, src/App.vue |
| Nuxt | nuxt.config.js, pages/ |
| Express | "express" in package.json, routes/ |
| NestJS | "@nestjs/core" in package.json |
| FastAPI | "from fastapi import" in main.py |
| Django | manage.py in root |
| Flask | "from flask import" in app.py |

---

## [2025-01-21] Quality Gates

### Added
- New module: `quality_gates.py` - Quality checking logic (lint, type-check, custom scripts)
- New MCP tool: `feature_verify_quality` - Run quality checks on demand
- Auto-detection of linters: ESLint, Biome, ruff, flake8
- Auto-detection of type checkers: TypeScript (tsc), Python (mypy)
- Support for custom quality scripts via `.autocoder/quality-checks.sh`

### Changed
- Modified `feature_mark_passing` - Now enforces quality checks in strict mode
- In strict mode, `feature_mark_passing` BLOCKS if lint or type-check fails
- Quality results are stored in the `quality_result` DB column

### Configuration
- `quality_gates.enabled`: Enable/disable quality gates (default: true)
- `quality_gates.strict_mode`: Block feature_mark_passing on failure (default: true)
- `quality_gates.checks.lint`: Run lint check (default: true)
- `quality_gates.checks.type_check`: Run type check (default: true)
- `quality_gates.checks.custom_script`: Path to custom script (optional)

### How to Disable
```json
{"quality_gates": {"enabled": false}}
```
Or for non-blocking mode:
```json
{"quality_gates": {"strict_mode": false}}
```

### Related Issues
- Addresses #68 (Agent skips features without testing)
- Addresses #69 (Test evidence storage)

---

## [2025-01-21] Error Recovery

### Added
- New DB columns: `failure_reason`, `failure_count`, `last_failure_at`, `quality_result` in Feature model
- New MCP tool: `feature_report_failure` - Report failures with escalation recommendations
- New MCP tool: `feature_get_stuck` - Get all features that have failed at least once
- New MCP tool: `feature_clear_all_in_progress` - Clear all stuck features at once
- New MCP tool: `feature_reset_failure` - Reset failure tracking for a feature
- New helper: `clear_stuck_features()` in `progress.py` - Auto-clear on agent startup
- Auto-recovery on agent startup: Clears stuck features from interrupted sessions

### Changed
- Modified `api/database.py` - Added error recovery and quality result columns with auto-migration
- Modified `agent.py` - Calls `clear_stuck_features()` on startup
- Modified `mcp_server/feature_mcp.py` - Added error recovery MCP tools

### Configuration
- New config section: `error_recovery` with `max_retries`, `skip_threshold`, `escalate_threshold`, `auto_clear_on_startup`

### How to Disable
```json
{"error_recovery": {"auto_clear_on_startup": false}}
```

### Related Issues
- Fixes features stuck after stop (common issue when agents are interrupted)

---

## Entry Template

When adding a new feature, use this template:

```markdown
## [YYYY-MM-DD] Feature Name

### Added
- New file: `path/to/file.py` - Description
- New component: `ComponentName` - Description

### Changed
- Modified `file.py` - What changed and why

### Configuration
- New config option: `config.key` - What it does

### How to Disable
\`\`\`json
{"feature_name": {"enabled": false}}
\`\`\`

### Related Issues
- Closes #XX (upstream issue)
```

---

## Planned Features

The following features are planned for implementation:

### Phase 1: Foundation (Quick Wins)
- [x] Enhanced Logging - Structured logs with filtering ✅
- [x] Quality Gates - Lint/type-check before marking passing ✅
- [ ] Security Scanning - Detect vulnerabilities

### Phase 2: Import Projects
- [x] Stack Detector - Detect React, Next.js, Express, FastAPI, Django, Vue.js ✅
- [x] Feature Extractor - Reverse-engineer features from routes/endpoints ✅
- [x] Import Wizard API - REST endpoints for import flow ✅
- [ ] Import Wizard UI - Chat-based project import (UI component)

### Phase 3: Workflow Improvements
- [ ] Feature Branches - Git workflow with feature branches
- [x] Error Recovery - Handle stuck features, auto-clear on startup ✅
- [ ] Review Agent - Automatic code review
- [ ] CI/CD Integration - GitHub Actions generation

### Phase 4: Polish & Ecosystem
- [ ] Template Library - SaaS, e-commerce, dashboard templates
- [ ] Auto Documentation - README, API docs generation
- [ ] Design Tokens - Consistent styling
- [ ] Visual Regression - Screenshot comparison testing
