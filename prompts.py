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


def _get_boilerplate_context(project_dir: Path | None) -> str:
    """Generate boilerplate context string for injection into prompts.

    If the project was created from a boilerplate, returns a markdown section
    describing what's pre-built so agents don't duplicate infrastructure.

    Args:
        project_dir: The project directory to check for project_config.json.

    Returns:
        A markdown string with boilerplate context, or empty string if none.
    """
    if not project_dir:
        return ""

    config_path = project_dir / ".autoforge" / "project_config.json"
    if not config_path.exists():
        return ""

    import json
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    boilerplate = config.get("boilerplate", {})
    option_id = boilerplate.get("option_id", "")

    # No boilerplate or "from scratch" - no context needed
    if not option_id or option_id == "scratch":
        return ""

    option_name = boilerplate.get("option_name", option_id)
    tech_summary = boilerplate.get("tech_summary", "")

    # Look up pre_built from the boilerplate registry
    pre_built: list[str] = []
    try:
        from server.services.boilerplate_manager import get_boilerplate_option
        opt = get_boilerplate_option(option_id)
        if opt:
            pre_built = opt.get("pre_built", [])
    except ImportError:
        pass

    pre_built_lines = "\n".join(f"- {item}" for item in pre_built)

    return f"""
## BOILERPLATE CONTEXT

This project was created from the **{option_name}** boilerplate.

**Tech Stack:** {tech_summary}

**The following features are ALREADY BUILT and should NOT be recreated:**
{pre_built_lines}

**Important guidelines for boilerplate projects:**
- DO NOT create features for auth, payments, credits, admin, or other pre-built infrastructure
- Build ON TOP of the existing code — follow the patterns already established in the codebase
- Use existing components, contexts, hooks, and API patterns from the boilerplate
- New pages go in `src/pages/`, new components in `src/components/`, new API routes in `api/`
- The boilerplate's CLAUDE.md and AI_RULES.md contain project-specific coding standards — follow them
- Focus ONLY on features that make this app unique (the app-specific business logic and UI)

"""


def get_initializer_prompt(project_dir: Path | None = None) -> str:
    """Load the initializer prompt (project-specific if available).

    If the project uses a boilerplate, injects context about pre-built features.
    """
    prompt = load_prompt("initializer_prompt", project_dir)
    boilerplate_ctx = _get_boilerplate_context(project_dir)
    if boilerplate_ctx:
        prompt = boilerplate_ctx + prompt
    return prompt


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

    # Replace the screenshots-only marking rule with YOLO-appropriate wording
    prompt = prompt.replace(
        "**ONLY MARK A FEATURE AS PASSING AFTER VERIFICATION WITH SCREENSHOTS.**",
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

    If the project uses a boilerplate, injects context about pre-built features.

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

    boilerplate_ctx = _get_boilerplate_context(project_dir)
    if boilerplate_ctx:
        prompt = boilerplate_ctx + prompt

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

    if copied_files:
        print(f"  Created project files: {', '.join(copied_files)}")

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
