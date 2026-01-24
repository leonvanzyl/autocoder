# AutoCoder Security Configuration Examples

This directory contains example configuration files for controlling which bash commands the autonomous coding agent can execute.

## Table of Contents

- [Quick Start](#quick-start)
- [Project-Level Configuration](#project-level-configuration)
- [Organization-Level Configuration](#organization-level-configuration)
- [Command Hierarchy](#command-hierarchy)
- [Pattern Matching](#pattern-matching)
- [Common Use Cases](#common-use-cases)
- [Security Best Practices](#security-best-practices)

---

## Quick Start

### For a Single Project (Most Common)

When you create a new project with AutoCoder, it automatically creates:

```text
my-project/
  .autocoder/
    allowed_commands.yaml    ← Automatically created from template
```

**Edit this file** to add project-specific commands (Swift tools, Rust compiler, etc.).

### For All Projects (Organization-Wide)

If you want commands available across **all projects**, manually create:

```bash
# Copy the example to your home directory
cp examples/org_config.yaml ~/.autocoder/config.yaml

# Edit it to add org-wide commands
nano ~/.autocoder/config.yaml
```

---

## Project-Level Configuration

**File:** `{project_dir}/.autocoder/allowed_commands.yaml`

**Purpose:** Define commands needed for THIS specific project.

**Example** (iOS project):

```yaml
version: 1
commands:
  - name: swift
    description: Swift compiler

  - name: xcodebuild
    description: Xcode build system

  - name: swift*
    description: All Swift tools (swiftc, swiftlint, swiftformat)

  - name: ./scripts/build.sh
    description: Project build script
```

**When to use:**
- ✅ Project uses a specific language toolchain (Swift, Rust, Go)
- ✅ Project has custom build scripts
- ✅ Temporary tools needed during development

**Limits:**
- Maximum 100 commands per project
- Cannot override org-level blocked commands
- Cannot allow hardcoded blocklist commands (sudo, dd, etc.)

**See:** `examples/project_allowed_commands.yaml` for full example with Rust, Python, iOS, etc.

---

## Organization-Level Configuration

**File:** `~/.autocoder/config.yaml`

**Purpose:** Define commands and policies for ALL projects.

**Example** (startup team):

```yaml
version: 1

# Available to all projects
allowed_commands:
  - name: jq
    description: JSON processor

  - name: python3
    description: Python interpreter

# Blocked across all projects (cannot be overridden)
blocked_commands:
  - aws
  - kubectl
  - terraform
```

**When to use:**
- ✅ Multiple projects need the same tools (jq, python3, etc.)
- ✅ Enforce organization-wide security policies
- ✅ Block dangerous commands across all projects

**See:** `examples/org_config.yaml` for full example with enterprise/startup configurations.

---

## Command Hierarchy

When the agent tries to run a command, the system checks in this order:

```text
┌─────────────────────────────────────────────────────┐
│ 1. HARDCODED BLOCKLIST (highest priority)          │
│    sudo, dd, shutdown, reboot, chown, etc.          │
│    ❌ NEVER allowed, even with user approval        │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 2. ORG BLOCKLIST (~/.autocoder/config.yaml)         │
│    Commands you block organization-wide             │
│    ❌ Projects CANNOT override these                │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 3. ORG ALLOWLIST (~/.autocoder/config.yaml)         │
│    Commands available to all projects               │
│    ✅ Automatically available                       │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 4. GLOBAL ALLOWLIST (security.py)                   │
│    Default commands: npm, git, curl, ls, cat, etc.  │
│    ✅ Always available                              │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ 5. PROJECT ALLOWLIST (.autocoder/allowed_commands)  │
│    Project-specific commands                        │
│    ✅ Available only to this project                │
└─────────────────────────────────────────────────────┘
```

**Key Rules:**
- If a command is BLOCKED at any level above, it cannot be allowed below
- If a command is ALLOWED at any level, it's available (unless blocked above)
- Blocklist always wins over allowlist

---

## Pattern Matching

You can use patterns to match multiple commands:

### Exact Match
```yaml
- name: swift
  description: Swift compiler only
```
Matches: `swift`
Does NOT match: `swiftc`, `swiftlint`

### Prefix Wildcard
```yaml
- name: swift*
  description: All Swift tools
```
Matches: `swift`, `swiftc`, `swiftlint`, `swiftformat`
Does NOT match: `npm`, `rustc`

### Local Scripts
```yaml
- name: ./scripts/build.sh
  description: Build script
```
Matches:
- `./scripts/build.sh`
- `scripts/build.sh`
- `/full/path/to/scripts/build.sh`
- Running `build.sh` from any directory (matched by filename)

---

## Common Use Cases

### iOS Development

**Project config** (`.autocoder/allowed_commands.yaml`):
```yaml
version: 1
commands:
  - name: swift*
    description: All Swift tools
  - name: xcodebuild
    description: Xcode build system
  - name: xcrun
    description: Xcode tools runner
  - name: simctl
    description: iOS Simulator control
```

### Rust CLI Project

**Project config**:
```yaml
version: 1
commands:
  - name: cargo
    description: Rust package manager
  - name: rustc
    description: Rust compiler
  - name: rustfmt
    description: Rust formatter
  - name: clippy
    description: Rust linter
  - name: ./target/debug/my-cli
    description: Debug build
  - name: ./target/release/my-cli
    description: Release build
```

### API Testing Project

**Project config**:
```yaml
version: 1
commands:
  - name: jq
    description: JSON processor
  - name: httpie
    description: HTTP client
  - name: ./scripts/test-api.sh
    description: API test runner
```

### Enterprise Organization (Restrictive)

**Org config** (`~/.autocoder/config.yaml`):
```yaml
version: 1

allowed_commands:
  - name: jq
    description: JSON processor

blocked_commands:
  - aws        # No cloud access
  - gcloud
  - az
  - kubectl    # No k8s access
  - terraform  # No infrastructure changes
  - psql       # No production DB access
  - mysql
```

### Startup Team (Permissive)

**Org config** (`~/.autocoder/config.yaml`):
```yaml
version: 1

allowed_commands:
  - name: python3
    description: Python interpreter
  - name: jq
    description: JSON processor
  - name: pytest
    description: Python tests

blocked_commands: []  # Rely on hardcoded blocklist only
```

---

## Security Best Practices

### ✅ DO

1. **Start restrictive, add as needed**
   - Begin with default commands only
   - Add project-specific tools when required
   - Review the agent's blocked command errors to understand what's needed

2. **Use org-level config for shared tools**
   - If 3+ projects need `jq`, add it to org config
   - Reduces duplication across project configs

3. **Block dangerous commands at org level**
   - Prevent accidental production deployments (`kubectl`, `terraform`)
   - Block cloud CLIs if appropriate (`aws`, `gcloud`, `az`)

4. **Use descriptive command names**
   - Good: `description: "Swift compiler for iOS builds"`
   - Bad: `description: "Compiler"`

5. **Prefer patterns for tool families**
   - `swift*` instead of listing `swift`, `swiftc`, `swiftlint` separately
   - Automatically includes future tools (e.g., new Swift utilities)

### ❌ DON'T

1. **Don't add commands "just in case"**
   - Only add when the agent actually needs them
   - Empty config is fine - defaults are usually enough

2. **Don't try to allow blocklisted commands**
   - Commands like `sudo`, `dd`, `shutdown` can NEVER be allowed
   - The system will reject these in validation

3. **Don't use org config for project-specific tools**
   - Bad: Adding `xcodebuild` to org config when only one project uses it
   - Good: Add `xcodebuild` to that project's config

4. **Don't exceed the 100 command limit per project**
   - If you need more, you're probably listing subcommands unnecessarily
   - Use wildcards instead: `flutter*` covers all flutter commands, not just the base

5. **Don't ignore validation errors**
   - If your YAML is rejected, fix the structure
   - Common issues: missing `version`, malformed lists, over 100 commands

---

## Default Allowed Commands

These commands are **always available** to all projects:

**File Operations:**
- `ls`, `cat`, `head`, `tail`, `wc`, `grep`, `cp`, `mkdir`, `mv`, `rm`, `touch`

**Shell:**
- `pwd`, `echo`, `sh`, `bash`, `sleep`

**Version Control:**
- `git`

**Process Management:**
- `ps`, `lsof`, `kill`, `pkill` (dev processes only: node, npm, vite)

**Network:**
- `curl`

**Node.js:**
- `npm`, `npx`, `pnpm`, `node`

**Docker:**
- `docker`

**Special:**
- `chmod` (only `+x` mode for making scripts executable)

---

## Hardcoded Blocklist

These commands are **NEVER allowed**, even with user approval:

**Disk Operations:**
- `dd`, `mkfs`, `fdisk`, `parted`

**System Control:**
- `shutdown`, `reboot`, `poweroff`, `halt`, `init`

**Privilege Escalation:**
- `sudo`, `su`, `doas`

**System Services:**
- `systemctl`, `service`, `launchctl`

**Network Security:**
- `iptables`, `ufw`

**Ownership Changes:**
- `chown`, `chgrp`

**Dangerous Commands** (Phase 3 will add approval):
- `aws`, `gcloud`, `az`, `kubectl`, `docker-compose`

---

## Troubleshooting

### Error: "Command 'X' is not allowed"

**Solution:** Add the command to your project config:
```yaml
# In .autocoder/allowed_commands.yaml
commands:
  - name: X
    description: What this command does
```

### Error: "Command 'X' is blocked at organization level"

**Cause:** The command is in the org blocklist or hardcoded blocklist.

**Solution:**
- If in org blocklist: Edit `~/.autocoder/config.yaml` to remove it
- If in hardcoded blocklist: Cannot be allowed (by design)

### Error: "Could not parse YAML config"

**Cause:** YAML syntax error.

**Solution:** Check for:
- Missing colons after keys
- Incorrect indentation (use 2 spaces, not tabs)
- Missing quotes around special characters

### Config not taking effect

**Solution:**
1. Restart the agent (changes are loaded on startup)
2. Verify file location:
   - Project: `{project}/.autocoder/allowed_commands.yaml`
   - Org: `~/.autocoder/config.yaml` (must be manually created)
3. Check YAML is valid (run through a YAML validator)

---

## Testing

### Running the Tests

AutoCoder has comprehensive tests for the security system:

**Unit Tests** (136 tests - fast):
```bash
source venv/bin/activate
python test_security.py
```

Tests:
- Pattern matching (exact, wildcards, scripts)
- YAML loading and validation
- Blocklist enforcement
- Project and org config hierarchy
- All existing security validations

**Integration Tests** (9 tests - uses real security hooks):
```bash
source venv/bin/activate
python test_security_integration.py
```

Tests:
- Blocked commands are rejected (sudo, shutdown, etc.)
- Default commands work (ls, git, npm, etc.)
- Non-allowed commands are blocked (wget, python, etc.)
- Project config allows commands (swift, xcodebuild, etc.)
- Pattern matching works (swift* matches swiftlint)
- Org blocklist cannot be overridden
- Org allowlist is inherited by projects
- Invalid YAML is safely ignored
- 50 command limit is enforced

### Manual Testing

To manually test the security system:

**1. Create a test project:**
```bash
python start.py
# Choose "Create new project"
# Name it "security-test"
```

**2. Edit the project config:**
```bash
# Navigate to the project directory
cd path/to/security-test

# Edit the config
nano .autocoder/allowed_commands.yaml
```

**3. Add a test command (e.g., Swift):**
```yaml
version: 1
commands:
  - name: swift
    description: Swift compiler
```

**4. Run the agent and observe:**
- Try a blocked command: `"Run sudo apt install nginx"` → Should be blocked
- Try an allowed command: `"Run ls -la"` → Should work
- Try your config command: `"Run swift --version"` → Should work
- Try a non-allowed command: `"Run wget https://example.com"` → Should be blocked

**5. Check the agent output:**

The agent will show security hook messages like:
```text
Command 'sudo' is blocked at organization level and cannot be approved.
```

Or:
```text
Command 'wget' is not allowed.
To allow this command:
  1. Add to .autocoder/allowed_commands.yaml for this project, OR
  2. Request mid-session approval (the agent can ask)
```

---

## Files Reference

- **`examples/project_allowed_commands.yaml`** - Full project config template
- **`examples/org_config.yaml`** - Full org config template
- **`security.py`** - Implementation and hardcoded blocklist
- **`test_security.py`** - Unit tests (136 tests)
- **`test_security_integration.py`** - Integration tests (9 tests)
- **`CLAUDE.md`** - Full system documentation

---

## Questions?

See the main documentation in `CLAUDE.md` for architecture details and implementation specifics.
