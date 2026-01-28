# Autocoder Fork - Enhanced Features

This is a fork of [leonvanzyl/autocoder](https://github.com/leonvanzyl/autocoder)
with additional features for improved developer experience.

## What's Different in This Fork

### New Features

- **Import Existing Projects** - Import existing codebases and continue development with Autocoder
- **Quality Gates** - Automatic code quality checks (lint, type-check) before marking features as passing
- **Enhanced Logging** - Better debugging with filterable, searchable, structured logs
- **Security Scanning** - Detect vulnerabilities in generated code (secrets, injection patterns)
- **Feature Branches** - Professional git workflow with automatic feature branch creation
- **Error Recovery** - Better handling of stuck features with auto-clear on startup
- **Template Library** - Pre-made templates for common app types (SaaS, e-commerce, dashboard)
- **CI/CD Integration** - GitHub Actions workflows generated automatically

### Configuration

All new features can be configured via `.autocoder/config.json`.
See [Configuration Guide](#configuration) for details.

## Configuration

Create a `.autocoder/config.json` file in your project directory:

```json
{
  "version": "1.0",

  "quality_gates": {
    "enabled": true,
    "strict_mode": true,
    "checks": {
      "lint": true,
      "type_check": true,
      "unit_tests": false,
      "custom_script": ".autocoder/quality-checks.sh"
    }
  },

  "git_workflow": {
    "mode": "feature_branches",
    "branch_prefix": "feature/",
    "auto_merge": false
  },

  "error_recovery": {
    "max_retries": 3,
    "skip_threshold": 5,
    "escalate_threshold": 7
  },

  "completion": {
    "auto_stop_at_100": true,
    "max_regression_cycles": 3
  },

  "ci_cd": {
    "provider": "github",
    "environments": {
      "staging": {"url": "", "auto_deploy": true},
      "production": {"url": "", "auto_deploy": false}
    }
  },

  "import": {
    "default_feature_status": "pending",
    "auto_detect_stack": true
  }
}
```

### Disabling Features

Each feature can be disabled individually:

```json
{
  "quality_gates": {
    "enabled": false
  },
  "git_workflow": {
    "mode": "none"
  }
}
```

## Staying Updated with Upstream

This fork regularly syncs with upstream. To get latest upstream changes:

```bash
git fetch upstream
git checkout main && git merge upstream/main
git checkout my-features && git merge main
```

## Reverting Changes

### Revert to Original

```bash
# Option 1: Full reset to upstream
git checkout my-features
git reset --hard upstream/main
git push origin my-features --force

# WARNING: The forced push (git push --force) can permanently overwrite remote history
# and cause data loss for collaborators. Recommended alternatives:
# - Use --force-with-lease instead of --force to prevent overwriting others' work
# - Inform your team before force-pushing
# - Consider creating a new branch instead (e.g., git checkout -b my-features-v2)
# - Backup your branch before force-pushing (git tag backup-branch && git push origin --tags)

# Option 2: Revert specific commits
git log --oneline  # find commit to revert
git revert <commit-hash>

# Option 3: Checkout specific files from upstream
git checkout upstream/master -- path/to/file.py
```

### Safety Checkpoint

Before major changes, create a tag:

```bash
git tag before-feature-name
# If something goes wrong:
git reset --hard before-feature-name
```

## Contributing Back

Features that could benefit the original project are submitted as PRs to upstream.
See [FORK_CHANGELOG.md](./FORK_CHANGELOG.md) for detailed change history.

## License

Same license as the original [leonvanzyl/autocoder](https://github.com/leonvanzyl/autocoder) project.
