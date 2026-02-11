"""
Prompt Loading Utilities
========================

Functions for loading prompt templates with project-specific support.

Fallback chain:
1. Project-specific: {project_dir}/prompts/{name}.md
2. Base template: .claude/templates/{name}.template.md
"""

import re
import shutil
from pathlib import Path

# Base templates location (generic templates)
TEMPLATES_DIR = Path(__file__).parent / ".claude" / "templates"

# Migration version — bump when adding new migration steps
CURRENT_MIGRATION_VERSION = 1


def get_project_prompts_dir(project_dir: Path) -> Path:
    """Get the prompts directory for a specific project."""
    from autoforge_paths import get_prompts_dir
    return get_prompts_dir(project_dir)


def load_prompt(name: str, project_dir: Path | None = None) -> str:
    """
    Load a prompt template with fallback chain.

    Fallback order:
    1. Project-specific: {project_dir}/prompts/{name}.md
    2. Base template: .claude/templates/{name}.template.md

    Args:
        name: The prompt name (without extension), e.g., "initializer_prompt"
        project_dir: Optional project directory for project-specific prompts

    Returns:
        The prompt content as a string

    Raises:
        FileNotFoundError: If prompt not found in any location
    """
    # 1. Try project-specific first
    if project_dir:
        project_prompts = get_project_prompts_dir(project_dir)
        project_path = project_prompts / f"{name}.md"
        if project_path.exists():
            try:
                return project_path.read_text(encoding="utf-8")
            except (OSError, PermissionError) as e:
                print(f"Warning: Could not read {project_path}: {e}")

    # 2. Try base template
    template_path = TEMPLATES_DIR / f"{name}.template.md"
    if template_path.exists():
        try:
            return template_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not read {template_path}: {e}")

    raise FileNotFoundError(
        f"Prompt '{name}' not found in:\n"
        f"  - Project: {project_dir / 'prompts' if project_dir else 'N/A'}\n"
        f"  - Templates: {TEMPLATES_DIR}"
    )


def get_initializer_prompt(project_dir: Path | None = None) -> str:
    """Load the initializer prompt (project-specific if available)."""
    return load_prompt("initializer_prompt", project_dir)


def _strip_browser_testing_sections(prompt: str) -> str:
    """Strip browser automation and Playwright testing instructions from prompt.

    Used in YOLO mode where browser testing is skipped entirely. Replaces
    browser-related sections with a brief YOLO-mode note while preserving
    all non-testing instructions (implementation, git, progress notes, etc.).

    Args:
        prompt: The full coding prompt text.

    Returns:
        The prompt with browser testing sections replaced by YOLO guidance.
    """
    original_prompt = prompt

    # Replace STEP 5 (browser automation verification) with YOLO note
    prompt = re.sub(
        r"### STEP 5: VERIFY WITH BROWSER AUTOMATION.*?(?=### STEP 5\.5:)",
        "### STEP 5: VERIFY FEATURE (YOLO MODE)\n\n"
        "**YOLO mode is active.** Skip browser automation testing. "
        "Instead, verify your feature works by ensuring:\n"
        "- Code compiles without errors (lint and type-check pass)\n"
        "- Server starts without errors after your changes\n"
        "- No obvious runtime errors in server logs\n\n",
        prompt,
        flags=re.DOTALL,
    )

    # Replace the marking rule with YOLO-appropriate wording
    prompt = prompt.replace(
        "**ONLY MARK A FEATURE AS PASSING AFTER VERIFICATION WITH BROWSER AUTOMATION.**",
        "**YOLO mode: Mark a feature as passing after lint/type-check succeeds and server starts cleanly.**",
    )

    # Replace the BROWSER AUTOMATION reference section
    prompt = re.sub(
        r"## BROWSER AUTOMATION\n\n.*?(?=---)",
        "## VERIFICATION (YOLO MODE)\n\n"
        "Browser automation is disabled in YOLO mode. "
        "Verify features by running lint, type-check, and confirming the dev server starts without errors.\n\n",
        prompt,
        flags=re.DOTALL,
    )

    # In STEP 4, replace browser automation reference with YOLO guidance
    prompt = prompt.replace(
        "2. Test manually using browser automation (see Step 5)",
        "2. Verify code compiles (lint and type-check pass)",
    )

    if prompt == original_prompt:
        print("[YOLO] Warning: No browser testing sections found to strip. "
              "Project-specific prompt may need manual YOLO adaptation.")

    return prompt


def get_coding_prompt(project_dir: Path | None = None, yolo_mode: bool = False) -> str:
    """Load the coding agent prompt (project-specific if available).

    Args:
        project_dir: Optional project directory for project-specific prompts
        yolo_mode: If True, strip browser automation / Playwright testing
            instructions and replace with YOLO-mode guidance. This reduces
            prompt tokens since YOLO mode skips all browser testing anyway.

    Returns:
        The coding prompt, optionally stripped of testing instructions.
    """
    prompt = load_prompt("coding_prompt", project_dir)

    if yolo_mode:
        prompt = _strip_browser_testing_sections(prompt)

    return prompt


def get_testing_prompt(
    project_dir: Path | None = None,
    testing_feature_id: int | None = None,
    testing_feature_ids: list[int] | None = None,
) -> str:
    """Load the testing agent prompt (project-specific if available).

    Supports both single-feature and multi-feature testing modes. When
    testing_feature_ids is provided, the template's {{TESTING_FEATURE_IDS}}
    placeholder is replaced with the comma-separated list. Falls back to
    the legacy single-feature header when only testing_feature_id is given.

    Args:
        project_dir: Optional project directory for project-specific prompts
        testing_feature_id: If provided, the pre-assigned feature ID to test (legacy single mode).
        testing_feature_ids: If provided, a list of feature IDs to test (batch mode).
            Takes precedence over testing_feature_id when both are set.

    Returns:
        The testing prompt, with feature assignment instructions populated.
    """
    base_prompt = load_prompt("testing_prompt", project_dir)

    # Batch mode: replace the {{TESTING_FEATURE_IDS}} placeholder in the template
    if testing_feature_ids is not None and len(testing_feature_ids) > 0:
        ids_str = ", ".join(str(fid) for fid in testing_feature_ids)
        return base_prompt.replace("{{TESTING_FEATURE_IDS}}", ids_str)

    # Legacy single-feature mode: prepend header and replace placeholder
    if testing_feature_id is not None:
        # Replace the placeholder with the single ID for template consistency
        base_prompt = base_prompt.replace("{{TESTING_FEATURE_IDS}}", str(testing_feature_id))
        return base_prompt

    # No feature assignment -- return template with placeholder cleared
    return base_prompt.replace("{{TESTING_FEATURE_IDS}}", "(none assigned)")


def get_single_feature_prompt(feature_id: int, project_dir: Path | None = None, yolo_mode: bool = False) -> str:
    """Prepend single-feature assignment header to base coding prompt.

    Used in parallel mode to assign a specific feature to an agent.
    The base prompt already contains the full workflow - this just
    identifies which feature to work on.

    Args:
        feature_id: The specific feature ID to work on
        project_dir: Optional project directory for project-specific prompts
        yolo_mode: If True, strip browser testing instructions from the base
            coding prompt for reduced token usage in YOLO mode.

    Returns:
        The prompt with single-feature header prepended
    """
    base_prompt = get_coding_prompt(project_dir, yolo_mode=yolo_mode)

    # Minimal header - the base prompt already contains the full workflow
    single_feature_header = f"""## ASSIGNED FEATURE: #{feature_id}

Work ONLY on this feature. Other agents are handling other features.
Use `feature_claim_and_get` with ID {feature_id} to claim it and get details.
If blocked, use `feature_skip` and document the blocker.

---

"""
    return single_feature_header + base_prompt


def get_batch_feature_prompt(
    feature_ids: list[int],
    project_dir: Path | None = None,
    yolo_mode: bool = False,
) -> str:
    """Prepend batch-feature assignment header to base coding prompt.

    Used in parallel mode to assign multiple features to an agent.
    Features should be implemented sequentially in the given order.

    Args:
        feature_ids: List of feature IDs to implement in order
        project_dir: Optional project directory for project-specific prompts
        yolo_mode: If True, strip browser testing instructions from the base prompt

    Returns:
        The prompt with batch-feature header prepended
    """
    base_prompt = get_coding_prompt(project_dir, yolo_mode=yolo_mode)
    ids_str = ", ".join(f"#{fid}" for fid in feature_ids)

    batch_header = f"""## ASSIGNED FEATURES (BATCH): {ids_str}

You have been assigned {len(feature_ids)} features to implement sequentially.
Process them IN ORDER: {ids_str}

### Workflow for each feature:
1. Call `feature_claim_and_get` with the feature ID to get its details
2. Implement the feature fully
3. Verify it works (browser testing if applicable)
4. Call `feature_mark_passing` to mark it complete
5. Git commit the changes
6. Move to the next feature

### Important:
- Complete each feature fully before starting the next
- Mark each feature passing individually as you go
- If blocked on a feature, use `feature_skip` and move to the next one
- Other agents are handling other features - focus only on yours

---

"""
    return batch_header + base_prompt


def get_app_spec(project_dir: Path) -> str:
    """
    Load the app spec from the project.

    Checks in order:
    1. Project prompts directory: {project_dir}/prompts/app_spec.txt
    2. Project root (legacy): {project_dir}/app_spec.txt

    Args:
        project_dir: The project directory

    Returns:
        The app spec content

    Raises:
        FileNotFoundError: If no app_spec.txt found
    """
    # Try project prompts directory first
    project_prompts = get_project_prompts_dir(project_dir)
    spec_path = project_prompts / "app_spec.txt"
    if spec_path.exists():
        try:
            return spec_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {spec_path}: {e}") from e

    # Fallback to legacy location in project root
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            return legacy_spec.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            raise FileNotFoundError(f"Could not read {legacy_spec}: {e}") from e

    raise FileNotFoundError(f"No app_spec.txt found for project: {project_dir}")


def scaffold_project_prompts(project_dir: Path) -> Path:
    """
    Create the project prompts directory and copy base templates.

    This sets up a new project with template files that can be customized.

    Args:
        project_dir: The absolute path to the project directory

    Returns:
        The path to the project prompts directory
    """
    project_prompts = get_project_prompts_dir(project_dir)
    project_prompts.mkdir(parents=True, exist_ok=True)

    # Create .autoforge directory with .gitignore for runtime files
    from autoforge_paths import ensure_autoforge_dir
    autoforge_dir = ensure_autoforge_dir(project_dir)

    # Define template mappings: (source_template, destination_name)
    templates = [
        ("app_spec.template.txt", "app_spec.txt"),
        ("coding_prompt.template.md", "coding_prompt.md"),
        ("initializer_prompt.template.md", "initializer_prompt.md"),
        ("testing_prompt.template.md", "testing_prompt.md"),
    ]

    copied_files = []
    for template_name, dest_name in templates:
        template_path = TEMPLATES_DIR / template_name
        dest_path = project_prompts / dest_name

        # Only copy if template exists and destination doesn't
        if template_path.exists() and not dest_path.exists():
            try:
                shutil.copy(template_path, dest_path)
                copied_files.append(dest_name)
            except (OSError, PermissionError) as e:
                print(f"  Warning: Could not copy {dest_name}: {e}")

    # Copy allowed_commands.yaml template to .autoforge/
    examples_dir = Path(__file__).parent / "examples"
    allowed_commands_template = examples_dir / "project_allowed_commands.yaml"
    allowed_commands_dest = autoforge_dir / "allowed_commands.yaml"
    if allowed_commands_template.exists() and not allowed_commands_dest.exists():
        try:
            shutil.copy(allowed_commands_template, allowed_commands_dest)
            copied_files.append(".autoforge/allowed_commands.yaml")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not copy allowed_commands.yaml: {e}")

    # Copy Playwright CLI skill for browser automation
    skills_src = Path(__file__).parent / ".claude" / "skills" / "playwright-cli"
    skills_dest = project_dir / ".claude" / "skills" / "playwright-cli"
    if skills_src.exists() and not skills_dest.exists():
        try:
            shutil.copytree(skills_src, skills_dest)
            copied_files.append(".claude/skills/playwright-cli/")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not copy playwright-cli skill: {e}")

    # Ensure .playwright-cli/ and .playwright/ are in project .gitignore
    project_gitignore = project_dir / ".gitignore"
    entries_to_add = [".playwright-cli/", ".playwright/"]
    existing_lines: list[str] = []
    if project_gitignore.exists():
        try:
            existing_lines = project_gitignore.read_text(encoding="utf-8").splitlines()
        except (OSError, PermissionError):
            pass
    missing_entries = [e for e in entries_to_add if e not in existing_lines]
    if missing_entries:
        try:
            with open(project_gitignore, "a", encoding="utf-8") as f:
                # Add newline before entries if file doesn't end with one
                if existing_lines and existing_lines[-1].strip():
                    f.write("\n")
                for entry in missing_entries:
                    f.write(f"{entry}\n")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not update .gitignore: {e}")

    # Scaffold .playwright/cli.config.json for browser settings
    playwright_config_dir = project_dir / ".playwright"
    playwright_config_file = playwright_config_dir / "cli.config.json"
    if not playwright_config_file.exists():
        try:
            playwright_config_dir.mkdir(parents=True, exist_ok=True)
            import json
            config = {
                "browser": {
                    "browserName": "chromium",
                    "launchOptions": {
                        "channel": "chrome",
                        "headless": True,
                    },
                    "contextOptions": {
                        "viewport": {"width": 1280, "height": 720},
                    },
                    "isolated": True,
                },
            }
            with open(playwright_config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                f.write("\n")
            copied_files.append(".playwright/cli.config.json")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not create playwright config: {e}")

    if copied_files:
        print(f"  Created project files: {', '.join(copied_files)}")

    # Stamp new projects at the current migration version so they never trigger migration
    _set_migration_version(project_dir, CURRENT_MIGRATION_VERSION)

    return project_prompts


def has_project_prompts(project_dir: Path) -> bool:
    """
    Check if a project has valid prompts set up.

    A project has valid prompts if:
    1. The prompts directory exists, AND
    2. app_spec.txt exists within it, AND
    3. app_spec.txt contains the <project_specification> tag

    Args:
        project_dir: The project directory to check

    Returns:
        True if valid project prompts exist, False otherwise
    """
    project_prompts = get_project_prompts_dir(project_dir)
    app_spec = project_prompts / "app_spec.txt"

    if not app_spec.exists():
        # Also check legacy location in project root
        legacy_spec = project_dir / "app_spec.txt"
        if legacy_spec.exists():
            try:
                content = legacy_spec.read_text(encoding="utf-8")
                return "<project_specification>" in content
            except (OSError, PermissionError):
                return False
        return False

    # Check for valid spec content
    try:
        content = app_spec.read_text(encoding="utf-8")
        return "<project_specification>" in content
    except (OSError, PermissionError):
        return False


def copy_spec_to_project(project_dir: Path) -> None:
    """
    Copy the app spec file into the project root directory for the agent to read.

    This maintains backwards compatibility - the agent expects app_spec.txt
    in the project root directory.

    The spec is sourced from: {project_dir}/prompts/app_spec.txt

    Args:
        project_dir: The project directory
    """
    spec_dest = project_dir / "app_spec.txt"

    # Don't overwrite if already exists
    if spec_dest.exists():
        return

    # Copy from project prompts directory
    project_prompts = get_project_prompts_dir(project_dir)
    project_spec = project_prompts / "app_spec.txt"
    if project_spec.exists():
        try:
            shutil.copy(project_spec, spec_dest)
            print("Copied app_spec.txt to project directory")
            return
        except (OSError, PermissionError) as e:
            print(f"Warning: Could not copy app_spec.txt: {e}")
            return

    print("Warning: No app_spec.txt found to copy to project directory")


# ---------------------------------------------------------------------------
# Project version migration
# ---------------------------------------------------------------------------

# Replacement content: coding_prompt.md STEP 5 section (Playwright CLI)
_CLI_STEP5_CONTENT = """\
### STEP 5: VERIFY WITH BROWSER AUTOMATION

**CRITICAL:** You MUST verify features through the actual UI.

Use `playwright-cli` for browser automation:

- Open the browser: `playwright-cli open http://localhost:PORT`
- Take a snapshot to see page elements: `playwright-cli snapshot`
- Read the snapshot YAML file to see element refs
- Click elements by ref: `playwright-cli click e5`
- Type text: `playwright-cli type "search query"`
- Fill form fields: `playwright-cli fill e3 "value"`
- Take screenshots: `playwright-cli screenshot`
- Read the screenshot file to verify visual appearance
- Check console errors: `playwright-cli console`
- Close browser when done: `playwright-cli close`

**Token-efficient workflow:** `playwright-cli screenshot` and `snapshot` save files
to `.playwright-cli/`. You will see a file link in the output. Read the file only
when you need to verify visual appearance or find element refs.

**DO:**
- Test through the UI with clicks and keyboard input
- Take screenshots and read them to verify visual appearance
- Check for console errors with `playwright-cli console`
- Verify complete user workflows end-to-end
- Always run `playwright-cli close` when finished testing

**DON'T:**
- Only test with curl commands
- Use JavaScript evaluation to bypass UI (`eval` and `run-code` are blocked)
- Skip visual verification
- Mark tests passing without thorough verification

"""

# Replacement content: coding_prompt.md BROWSER AUTOMATION reference section
_CLI_BROWSER_SECTION = """\
## BROWSER AUTOMATION

Use `playwright-cli` commands for UI verification. Key commands: `open`, `goto`,
`snapshot`, `click`, `type`, `fill`, `screenshot`, `console`, `close`.

**How it works:** `playwright-cli` uses a persistent browser daemon. `open` starts it,
subsequent commands interact via socket, `close` shuts it down. Screenshots and snapshots
save to `.playwright-cli/` -- read the files when you need to verify content.

Test like a human user with mouse and keyboard. Use `playwright-cli console` to detect
JS errors. Don't bypass UI with JavaScript evaluation.

"""

# Replacement content: testing_prompt.md STEP 2 section (Playwright CLI)
_CLI_TESTING_STEP2 = """\
### STEP 2: VERIFY THE FEATURE

**CRITICAL:** You MUST verify the feature through the actual UI using browser automation.

For the feature returned:
1. Read and understand the feature's verification steps
2. Navigate to the relevant part of the application
3. Execute each verification step using browser automation
4. Take screenshots and read them to verify visual appearance
5. Check for console errors

### Browser Automation (Playwright CLI)

**Navigation & Screenshots:**
- `playwright-cli open <url>` - Open browser and navigate
- `playwright-cli goto <url>` - Navigate to URL
- `playwright-cli screenshot` - Save screenshot to `.playwright-cli/`
- `playwright-cli snapshot` - Save page snapshot with element refs to `.playwright-cli/`

**Element Interaction:**
- `playwright-cli click <ref>` - Click elements (ref from snapshot)
- `playwright-cli type <text>` - Type text
- `playwright-cli fill <ref> <text>` - Fill form fields
- `playwright-cli select <ref> <val>` - Select dropdown
- `playwright-cli press <key>` - Keyboard input

**Debugging:**
- `playwright-cli console` - Check for JS errors
- `playwright-cli network` - Monitor API calls

**Cleanup:**
- `playwright-cli close` - Close browser when done (ALWAYS do this)

**Note:** Screenshots and snapshots save to files. Read the file to see the content.

"""

# Replacement content: testing_prompt.md AVAILABLE TOOLS browser subsection
_CLI_TESTING_TOOLS = """\
### Browser Automation (Playwright CLI)
Use `playwright-cli` commands for browser interaction. Key commands:
- `playwright-cli open <url>` - Open browser
- `playwright-cli goto <url>` - Navigate to URL
- `playwright-cli screenshot` - Take screenshot (saved to `.playwright-cli/`)
- `playwright-cli snapshot` - Get page snapshot with element refs
- `playwright-cli click <ref>` - Click element
- `playwright-cli type <text>` - Type text
- `playwright-cli fill <ref> <text>` - Fill form field
- `playwright-cli console` - Check for JS errors
- `playwright-cli close` - Close browser (always do this when done)

"""


def _get_migration_version(project_dir: Path) -> int:
    """Read the migration version from .autoforge/.migration_version."""
    from autoforge_paths import get_autoforge_dir
    version_file = get_autoforge_dir(project_dir) / ".migration_version"
    if not version_file.exists():
        return 0
    try:
        return int(version_file.read_text().strip())
    except (ValueError, OSError):
        return 0


def _set_migration_version(project_dir: Path, version: int) -> None:
    """Write the migration version to .autoforge/.migration_version."""
    from autoforge_paths import get_autoforge_dir
    version_file = get_autoforge_dir(project_dir) / ".migration_version"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(str(version))


def _migrate_coding_prompt_to_cli(content: str) -> str:
    """Replace MCP-based Playwright sections with CLI-based content in coding prompt."""
    # Replace STEP 5 section (from header to just before STEP 5.5)
    content = re.sub(
        r"### STEP 5: VERIFY WITH BROWSER AUTOMATION.*?(?=### STEP 5\.5:)",
        _CLI_STEP5_CONTENT,
        content,
        count=1,
        flags=re.DOTALL,
    )

    # Replace BROWSER AUTOMATION reference section (from header to next ---)
    content = re.sub(
        r"## BROWSER AUTOMATION\n\n.*?(?=---)",
        _CLI_BROWSER_SECTION,
        content,
        count=1,
        flags=re.DOTALL,
    )

    # Replace inline screenshot rule
    content = content.replace(
        "**ONLY MARK A FEATURE AS PASSING AFTER VERIFICATION WITH SCREENSHOTS.**",
        "**ONLY MARK A FEATURE AS PASSING AFTER VERIFICATION WITH BROWSER AUTOMATION.**",
    )

    # Replace inline screenshot references (various phrasings from old templates)
    for old_phrase in (
        "(inline only -- do NOT save to disk)",
        "(inline only, never save to disk)",
        "(inline mode only -- never save to disk)",
    ):
        content = content.replace(old_phrase, "(saved to `.playwright-cli/`)")

    return content


def _migrate_testing_prompt_to_cli(content: str) -> str:
    """Replace MCP-based Playwright sections with CLI-based content in testing prompt."""
    # Replace AVAILABLE TOOLS browser subsection FIRST (before STEP 2, to avoid
    # matching the new CLI subsection header that the STEP 2 replacement inserts).
    # In old prompts, ### Browser Automation (Playwright) only exists in AVAILABLE TOOLS.
    content = re.sub(
        r"### Browser Automation \(Playwright[^)]*\)\n.*?(?=---)",
        _CLI_TESTING_TOOLS,
        content,
        count=1,
        flags=re.DOTALL,
    )

    # Replace STEP 2 verification section (from header to just before STEP 3)
    content = re.sub(
        r"### STEP 2: VERIFY THE FEATURE.*?(?=### STEP 3:)",
        _CLI_TESTING_STEP2,
        content,
        count=1,
        flags=re.DOTALL,
    )

    # Replace inline screenshot references (various phrasings from old templates)
    for old_phrase in (
        "(inline only -- do NOT save to disk)",
        "(inline only, never save to disk)",
        "(inline mode only -- never save to disk)",
    ):
        content = content.replace(old_phrase, "(saved to `.playwright-cli/`)")

    return content


def _migrate_v0_to_v1(project_dir: Path) -> list[str]:
    """Migrate from v0 (MCP-based Playwright) to v1 (Playwright CLI).

    Four idempotent sub-steps:
    A. Copy playwright-cli skill to project
    B. Scaffold .playwright/cli.config.json
    C. Update .gitignore with .playwright-cli/ and .playwright/
    D. Update coding_prompt.md and testing_prompt.md
    """
    import json

    migrated: list[str] = []

    # A. Copy Playwright CLI skill
    skills_src = Path(__file__).parent / ".claude" / "skills" / "playwright-cli"
    skills_dest = project_dir / ".claude" / "skills" / "playwright-cli"
    if skills_src.exists() and not skills_dest.exists():
        try:
            shutil.copytree(skills_src, skills_dest)
            migrated.append("Copied playwright-cli skill")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not copy playwright-cli skill: {e}")

    # B. Scaffold .playwright/cli.config.json
    playwright_config_dir = project_dir / ".playwright"
    playwright_config_file = playwright_config_dir / "cli.config.json"
    if not playwright_config_file.exists():
        try:
            playwright_config_dir.mkdir(parents=True, exist_ok=True)
            config = {
                "browser": {
                    "browserName": "chromium",
                    "launchOptions": {
                        "channel": "chrome",
                        "headless": True,
                    },
                    "contextOptions": {
                        "viewport": {"width": 1280, "height": 720},
                    },
                    "isolated": True,
                },
            }
            with open(playwright_config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                f.write("\n")
            migrated.append("Created .playwright/cli.config.json")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not create playwright config: {e}")

    # C. Update .gitignore
    project_gitignore = project_dir / ".gitignore"
    entries_to_add = [".playwright-cli/", ".playwright/"]
    existing_lines: list[str] = []
    if project_gitignore.exists():
        try:
            existing_lines = project_gitignore.read_text(encoding="utf-8").splitlines()
        except (OSError, PermissionError):
            pass
    missing_entries = [e for e in entries_to_add if e not in existing_lines]
    if missing_entries:
        try:
            with open(project_gitignore, "a", encoding="utf-8") as f:
                if existing_lines and existing_lines[-1].strip():
                    f.write("\n")
                for entry in missing_entries:
                    f.write(f"{entry}\n")
            migrated.append(f"Added {', '.join(missing_entries)} to .gitignore")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not update .gitignore: {e}")

    # D. Update prompts
    prompts_dir = get_project_prompts_dir(project_dir)

    # D1. Update coding_prompt.md
    coding_prompt_path = prompts_dir / "coding_prompt.md"
    if coding_prompt_path.exists():
        try:
            content = coding_prompt_path.read_text(encoding="utf-8")
            if "Playwright MCP" in content or "browser_navigate" in content or "browser_take_screenshot" in content:
                updated = _migrate_coding_prompt_to_cli(content)
                if updated != content:
                    coding_prompt_path.write_text(updated, encoding="utf-8")
                    migrated.append("Updated coding_prompt.md to Playwright CLI")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not update coding_prompt.md: {e}")

    # D2. Update testing_prompt.md
    testing_prompt_path = prompts_dir / "testing_prompt.md"
    if testing_prompt_path.exists():
        try:
            content = testing_prompt_path.read_text(encoding="utf-8")
            if "browser_navigate" in content or "browser_take_screenshot" in content:
                updated = _migrate_testing_prompt_to_cli(content)
                if updated != content:
                    testing_prompt_path.write_text(updated, encoding="utf-8")
                    migrated.append("Updated testing_prompt.md to Playwright CLI")
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not update testing_prompt.md: {e}")

    return migrated


def migrate_project_to_current(project_dir: Path) -> list[str]:
    """Migrate an existing project to the current AutoForge version.

    Idempotent — safe to call on every agent start. Returns list of
    human-readable descriptions of what was migrated.
    """
    current = _get_migration_version(project_dir)
    if current >= CURRENT_MIGRATION_VERSION:
        return []

    migrated: list[str] = []

    if current < 1:
        migrated.extend(_migrate_v0_to_v1(project_dir))

    # Future: if current < 2: migrated.extend(_migrate_v1_to_v2(project_dir))

    _set_migration_version(project_dir, CURRENT_MIGRATION_VERSION)
    return migrated
