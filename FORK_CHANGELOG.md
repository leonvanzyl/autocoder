# Fork Changelog

All notable changes to this fork are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Fork documentation (FORK_README.md, FORK_CHANGELOG.md)
- Configuration system via `.autocoder/config.json`

## [2025-01-21] Design Tokens

### Added
- New module: `design_tokens.py` - Design tokens management system
- New router: `server/routers/design_tokens.py` - REST API for token management

### Token Categories
| Category | Description |
|----------|-------------|
| `colors` | Primary, secondary, accent, semantic colors with auto-generated shades |
| `spacing` | Spacing scale (default: 4, 8, 12, 16, 24, 32, 48, 64, 96) |
| `typography` | Font families, sizes, weights, line heights |
| `borders` | Border radii and widths |
| `shadows` | Box shadow definitions |
| `animations` | Durations and easing functions |

### Generated Files
| File | Description |
|------|-------------|
| `tokens.css` | CSS custom properties with color shades |
| `_tokens.scss` | SCSS variables |
| `tailwind.tokens.js` | Tailwind CSS extend config |

### Color Shades
Automatically generates 50-950 shades from base colors:
- 50, 100, 200, 300, 400 (lighter)
- 500 (base color)
- 600, 700, 800, 900, 950 (darker)

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/design-tokens/{project}` | GET | Get current tokens |
| `/api/design-tokens/{project}` | PUT | Update tokens |
| `/api/design-tokens/{project}/generate` | POST | Generate token files |
| `/api/design-tokens/{project}/preview/{format}` | GET | Preview output (css/scss/tailwind) |
| `/api/design-tokens/{project}/validate` | POST | Validate tokens |
| `/api/design-tokens/{project}/reset` | POST | Reset to defaults |

### app_spec.txt Support
```xml
<design_tokens>
  <colors>
    <primary>#3B82F6</primary>
    <secondary>#6366F1</secondary>
    <accent>#F59E0B</accent>
  </colors>
  <spacing>
    <scale>[4, 8, 12, 16, 24, 32, 48]</scale>
  </spacing>
  <typography>
    <font_family>Inter, system-ui, sans-serif</font_family>
  </typography>
</design_tokens>
```

### Usage
```python
from design_tokens import DesignTokensManager, generate_design_tokens

# Quick generation
files = generate_design_tokens(project_dir)

# Custom management
manager = DesignTokensManager(project_dir)
tokens = manager.load()
manager.generate_css(tokens, output_path)
manager.generate_tailwind_config(tokens, output_path)

# Validate accessibility
issues = manager.validate_contrast(tokens)
```

### Configuration
```json
{
  "design_tokens": {
    "enabled": true,
    "output_dir": "src/styles",
    "generate_on_init": true
  }
}
```

### How to Disable
```json
{"design_tokens": {"enabled": false}}
```

---

## [2025-01-21] Auto Documentation

### Added
- New module: `auto_documentation.py` - Automatic documentation generation
- New router: `server/routers/documentation.py` - REST API for documentation management

### Generated Files
| File | Location | Description |
|------|----------|-------------|
| `README.md` | Project root | Project overview with features, tech stack, setup |
| `SETUP.md` | `docs/` | Detailed setup guide with prerequisites |
| `API.md` | `docs/` | API endpoint documentation |

### Documentation Content
- **Project name and description** - From app_spec.txt
- **Tech stack** - Auto-detected from package.json, requirements.txt
- **Features** - From features.db with completion status
- **Setup steps** - From init.sh, package.json scripts
- **Environment variables** - From .env.example
- **API endpoints** - Extracted from Express/FastAPI routes
- **Components** - Extracted from React/Vue components

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/docs/generate` | POST | Generate documentation |
| `/api/docs/{project}` | GET | List documentation files |
| `/api/docs/{project}/{filename}` | GET | Get documentation content |
| `/api/docs/preview` | POST | Preview README without writing |
| `/api/docs/{project}/{filename}` | DELETE | Delete documentation file |

### Usage
```python
from auto_documentation import DocumentationGenerator, generate_documentation

# Quick generation
files = generate_documentation(project_dir)

# Custom generation
generator = DocumentationGenerator(project_dir, output_dir="docs")
docs = generator.generate()
generator.write_readme(docs)
generator.write_api_docs(docs)
generator.write_setup_guide(docs)
```

### Configuration
```json
{
  "docs": {
    "enabled": true,
    "generate_on_init": false,
    "generate_on_complete": true,
    "output_dir": "docs"
  }
}
```

### How to Disable
```json
{"docs": {"enabled": false}}
```

---

## [2025-01-21] Review Agent

### Added
- New module: `review_agent.py` - Automatic code review with AST-based analysis
- New router: `server/routers/review.py` - REST API for code review operations

### Issue Categories
| Category | Description |
|----------|-------------|
| `dead_code` | Unused imports, variables, functions |
| `naming` | Naming convention violations |
| `error_handling` | Bare except, silent exception swallowing |
| `security` | eval(), exec(), shell=True, pickle |
| `complexity` | Long functions, too many parameters |
| `documentation` | TODO/FIXME comments |
| `style` | Code style issues |

### Issue Severities
- **error** - Critical issues that must be fixed
- **warning** - Issues that should be addressed
- **info** - Informational findings
- **style** - Style suggestions

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/review/run` | POST | Run code review |
| `/api/review/reports/{project}` | GET | List review reports |
| `/api/review/reports/{project}/{filename}` | GET | Get specific report |
| `/api/review/create-features` | POST | Create features from issues |
| `/api/review/reports/{project}/{filename}` | DELETE | Delete a report |

### Python Checks
- Unused imports (AST-based)
- Class naming (PascalCase)
- Function naming (snake_case)
- Bare except clauses
- Empty exception handlers
- Long functions (>50 lines)
- Too many parameters (>7)
- Security patterns (eval, exec, pickle, shell=True)

### JavaScript/TypeScript Checks
- console.log statements
- TODO/FIXME comments
- Security patterns (eval, innerHTML, dangerouslySetInnerHTML)

### Usage
```python
from review_agent import ReviewAgent, run_review

# Quick review
report = run_review(project_dir)

# Custom review
agent = ReviewAgent(
    project_dir,
    check_dead_code=True,
    check_naming=True,
    check_security=True,
)
report = agent.review(commits=["abc123"])
features = agent.get_issues_as_features()
```

### Reports
Reports are saved to `.autocoder/review-reports/review_YYYYMMDD_HHMMSS.json`

### Configuration
```json
{
  "review": {
    "enabled": true,
    "trigger_after_features": 5,
    "checks": {
      "dead_code": true,
      "naming": true,
      "error_handling": true,
      "security": true,
      "complexity": true
    }
  }
}
```

### How to Disable
```json
{"review": {"enabled": false}}
```

---

## [2025-01-21] Import Wizard UI

### Added
- New hook: `ui/src/hooks/useImportProject.ts` - State management for import workflow
- New component: `ui/src/components/ImportProjectModal.tsx` - Multi-step import wizard

### Wizard Steps
1. **Folder Selection** - Browse and select existing project folder
2. **Stack Detection** - View detected technologies and confidence scores
3. **Feature Extraction** - Extract features from routes and endpoints
4. **Feature Review** - Select which features to import (toggle individual features)
5. **Registration** - Name and register the project
6. **Completion** - Features created in database

### Features
- Category-based feature grouping with expand/collapse
- Individual feature selection with checkboxes
- Select All / Deselect All buttons
- Shows source type (route, endpoint, component)
- Shows source file location
- Displays detection confidence scores
- Progress indicators for each step

### UI Integration
- Added "Import Existing Project" option to NewProjectModal
- Users can choose between "Create New" and "Import Existing"

### Usage
1. Click "New Project" in the UI
2. Select "Import Existing Project"
3. Browse and select your project folder
4. Review detected tech stack
5. Click "Extract Features"
6. Select features to import
7. Enter project name and complete import

---

## [2025-01-21] Template Library

### Added
- New module: `templates/` - Project template library
- New router: `server/routers/templates.py` - REST API for templates

### Available Templates
| Template | Description | Features |
|----------|-------------|----------|
| `saas-starter` | Multi-tenant SaaS with auth, billing | ~45 |
| `ecommerce` | Online store with cart, checkout | ~50 |
| `admin-dashboard` | Admin panel with CRUD, charts | ~40 |
| `blog-cms` | Blog/CMS with posts, comments | ~35 |
| `api-service` | RESTful API with auth, docs | ~30 |

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/templates` | GET | List all templates |
| `/api/templates/{id}` | GET | Get template details |
| `/api/templates/preview` | POST | Preview app_spec.txt |
| `/api/templates/apply` | POST | Apply template to project |
| `/api/templates/{id}/features` | GET | Get template features |

### Template Format (YAML)
```yaml
name: "Template Name"
description: "Description"
tech_stack:
  frontend: "Next.js"
  backend: "FastAPI"
  database: "PostgreSQL"
feature_categories:
  authentication:
    - "User login"
    - "User registration"
design_tokens:
  colors:
    primary: "#3B82F6"
estimated_features: 30
tags: ["saas", "auth"]
```

### Usage
```bash
# List templates
curl http://localhost:8888/api/templates

# Get template details
curl http://localhost:8888/api/templates/saas-starter

# Preview app_spec.txt
curl -X POST http://localhost:8888/api/templates/preview \
  -H "Content-Type: application/json" \
  -d '{"template_id": "saas-starter", "app_name": "My SaaS"}'

# Apply template
curl -X POST http://localhost:8888/api/templates/apply \
  -H "Content-Type: application/json" \
  -d '{"template_id": "saas-starter", "project_name": "my-saas", "project_dir": "/path/to/project"}'
```

---

## [2025-01-21] CI/CD Integration

### Added
- New module: `integrations/ci/` - CI/CD workflow generation
- New router: `server/routers/cicd.py` - REST API for workflow management

### Generated Workflows
| Workflow | Filename | Triggers |
|----------|----------|----------|
| CI | `ci.yml` | Push to branches, PRs |
| Security | `security.yml` | Push/PR to main, weekly |
| Deploy | `deploy.yml` | Push to main, manual |

### CI Workflow Jobs
- **Lint**: ESLint, ruff
- **Type Check**: TypeScript tsc, mypy
- **Test**: npm test, pytest
- **Build**: Production build

### Security Workflow Jobs
- **NPM Audit**: Dependency vulnerability scan
- **Pip Audit**: Python dependency scan
- **CodeQL**: GitHub code scanning

### Deploy Workflow Jobs
- **Build**: Create production artifacts
- **Deploy Staging**: Auto-deploy on merge to main
- **Deploy Production**: Manual trigger only

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cicd/generate` | POST | Generate workflows |
| `/api/cicd/preview` | POST | Preview workflow YAML |
| `/api/cicd/workflows/{project}` | GET | List existing workflows |
| `/api/cicd/workflows/{project}/{filename}` | GET | Get workflow content |

### Usage
```bash
# Generate all workflows
curl -X POST http://localhost:8888/api/cicd/generate \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my-project"}'

# Preview CI workflow
curl -X POST http://localhost:8888/api/cicd/preview \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my-project", "workflow_type": "ci"}'
```

### Stack Detection
Automatically detects:
- Node.js version from `engines` in package.json
- Package manager (npm, yarn, pnpm, bun)
- TypeScript, React, Next.js, Vue
- Python version from pyproject.toml
- FastAPI, Django

---

## [2025-01-21] Feature Branches Git Workflow

### Added
- New module: `git_workflow.py` - Git workflow management for feature branches
- New router: `server/routers/git_workflow.py` - REST API for git operations

### Workflow Modes
| Mode | Description |
|------|-------------|
| `feature_branches` | Create branch per feature, merge on completion |
| `trunk` | All changes on main branch (default) |
| `none` | No git operations |

### Branch Naming
- Format: `feature/{id}-{slugified-name}`
- Example: `feature/42-user-can-login`

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/git/status/{project}` | GET | Get current git status |
| `/api/git/start-feature` | POST | Start feature (create branch) |
| `/api/git/complete-feature` | POST | Complete feature (merge) |
| `/api/git/abort-feature` | POST | Abort feature |
| `/api/git/commit` | POST | Commit changes |
| `/api/git/branches/{project}` | GET | List feature branches |

### Configuration
```json
{
  "git_workflow": {
    "mode": "feature_branches",
    "branch_prefix": "feature/",
    "main_branch": "main",
    "auto_merge": false
  }
}
```

### Usage
```python
from git_workflow import get_workflow

workflow = get_workflow(project_dir)

# Start working on a feature
result = workflow.start_feature(42, "User can login")

# Commit progress
result = workflow.commit_feature_progress(42, "Add login form")

# Complete feature (merge to main if auto_merge enabled)
result = workflow.complete_feature(42)
```

---

## [2025-01-21] Security Scanning

### Added
- New module: `security_scanner.py` - Vulnerability detection for code and dependencies
- New router: `server/routers/security.py` - REST API for security scanning

### Vulnerability Types Detected
| Type | Description |
|------|-------------|
| Dependency | Vulnerable packages via npm audit / pip-audit |
| Secret | Hardcoded API keys, passwords, tokens |
| SQL Injection | String formatting in SQL queries |
| XSS | innerHTML, document.write, dangerouslySetInnerHTML |
| Command Injection | shell=True, exec/eval with concatenation |
| Path Traversal | File operations with string concatenation |
| Insecure Crypto | MD5/SHA1, random.random() |

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/security/scan` | POST | Run security scan |
| `/api/security/reports/{project}` | GET | List scan reports |
| `/api/security/reports/{project}/{filename}` | GET | Get specific report |
| `/api/security/latest/{project}` | GET | Get latest report |

### Secret Patterns Detected
- AWS Access Keys and Secret Keys
- GitHub Tokens
- Slack Tokens
- Private Keys (RSA, EC, DSA)
- Generic API keys and tokens
- Database connection strings with credentials
- JWT tokens

### Usage
```python
from security_scanner import scan_project

result = scan_project(project_dir)
print(f"Found {result.summary['total_issues']} issues")
print(f"Critical: {result.summary['critical']}")
print(f"High: {result.summary['high']}")
```

### Reports
Reports are saved to `.autocoder/security-reports/security_scan_YYYYMMDD_HHMMSS.json`

---

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
- [x] Security Scanning - Detect vulnerabilities ✅

### Phase 2: Import Projects
- [x] Stack Detector - Detect React, Next.js, Express, FastAPI, Django, Vue.js ✅
- [x] Feature Extractor - Reverse-engineer features from routes/endpoints ✅
- [x] Import Wizard API - REST endpoints for import flow ✅
- [x] Import Wizard UI - Chat-based project import (UI component) ✅

### Phase 3: Workflow Improvements
- [x] Feature Branches - Git workflow with feature branches ✅
- [x] Error Recovery - Handle stuck features, auto-clear on startup ✅
- [x] Review Agent - Automatic code review ✅
- [x] CI/CD Integration - GitHub Actions generation ✅

### Phase 4: Polish & Ecosystem
- [x] Template Library - SaaS, e-commerce, dashboard templates ✅
- [x] Auto Documentation - README, API docs generation ✅
- [x] Design Tokens - Consistent styling ✅
- [ ] Visual Regression - Screenshot comparison testing
