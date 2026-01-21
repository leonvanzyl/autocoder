# Fork Changelog

All notable changes to this fork are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Fork documentation (FORK_README.md, FORK_CHANGELOG.md)
- Configuration system via `.autocoder/config.json`

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
- [ ] Enhanced Logging - Structured logs with filtering
- [ ] Quality Gates - Lint/type-check before marking passing
- [ ] Security Scanning - Detect vulnerabilities

### Phase 2: Import Projects
- [ ] Stack Detector - Detect React, Next.js, Express, FastAPI, Django, Vue.js
- [ ] Feature Extractor - Reverse-engineer features from routes/endpoints
- [ ] Import Wizard UI - Chat-based project import

### Phase 3: Workflow Improvements
- [ ] Feature Branches - Git workflow with feature branches
- [ ] Error Recovery - Handle stuck features, auto-clear on startup
- [ ] Review Agent - Automatic code review
- [ ] CI/CD Integration - GitHub Actions generation

### Phase 4: Polish & Ecosystem
- [ ] Template Library - SaaS, e-commerce, dashboard templates
- [ ] Auto Documentation - README, API docs generation
- [ ] Design Tokens - Consistent styling
- [ ] Visual Regression - Screenshot comparison testing
