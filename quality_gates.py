"""
Quality Gates Module
====================

Provides quality checking functionality for the Autocoder system.
Runs lint, type-check, and custom scripts before allowing features
to be marked as passing.

Supports:
- ESLint/Biome for JavaScript/TypeScript
- ruff/flake8 for Python
- Custom scripts via .autocoder/quality-checks.sh
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class QualityCheckResult(TypedDict):
    """Result of a single quality check."""
    name: str
    passed: bool
    output: str
    duration_ms: int


class QualityGateResult(TypedDict):
    """Result of all quality checks combined."""
    passed: bool
    timestamp: str
    checks: dict[str, QualityCheckResult]
    summary: str


def _run_command(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, int]:
    """
    Run a command and return (exit_code, output, duration_ms).

    Args:
        cmd: Command and arguments as a list
        cwd: Working directory
        timeout: Timeout in seconds

    Returns:
        (exit_code, combined_output, duration_ms)
    """
    import time
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
        output = result.stdout + result.stderr
        return result.returncode, output.strip(), duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start) * 1000)
        return 124, f"Command timed out after {timeout}s", duration_ms
    except FileNotFoundError:
        return 127, f"Command not found: {cmd[0]}", 0
    except Exception as e:
        return 1, str(e), 0


def _detect_js_linter(project_dir: Path) -> tuple[str, list[str]] | None:
    """
    Detect the JavaScript/TypeScript linter to use.

    Returns:
        (name, command) tuple, or None if no linter detected
    """
    # Check for ESLint
    if (project_dir / "node_modules/.bin/eslint").exists():
        return ("eslint", ["node_modules/.bin/eslint", ".", "--max-warnings=0"])

    # Check for Biome
    if (project_dir / "node_modules/.bin/biome").exists():
        return ("biome", ["node_modules/.bin/biome", "lint", "."])

    # Check for package.json lint script
    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
            scripts = data.get("scripts", {})
            if "lint" in scripts:
                return ("npm_lint", ["npm", "run", "lint"])
        except (json.JSONDecodeError, OSError):
            pass

    return None


def _detect_python_linter(project_dir: Path) -> tuple[str, list[str]] | None:
    """
    Detect the Python linter to use.

    Returns:
        (name, command) tuple, or None if no linter detected
    """
    # Check for ruff
    if shutil.which("ruff"):
        return ("ruff", ["ruff", "check", "."])

    # Check for flake8
    if shutil.which("flake8"):
        return ("flake8", ["flake8", "."])

    # Check in virtual environment
    venv_ruff = project_dir / "venv/bin/ruff"
    if venv_ruff.exists():
        return ("ruff", [str(venv_ruff), "check", "."])

    venv_flake8 = project_dir / "venv/bin/flake8"
    if venv_flake8.exists():
        return ("flake8", [str(venv_flake8), "."])

    return None


def _detect_type_checker(project_dir: Path) -> tuple[str, list[str]] | None:
    """
    Detect the type checker to use.

    Returns:
        (name, command) tuple, or None if no type checker detected
    """
    # TypeScript
    if (project_dir / "tsconfig.json").exists():
        if (project_dir / "node_modules/.bin/tsc").exists():
            return ("tsc", ["node_modules/.bin/tsc", "--noEmit"])
        if shutil.which("npx"):
            # Use --no-install to fail fast if tsc is not locally installed
            # rather than prompting/auto-downloading
            return ("tsc", ["npx", "--no-install", "tsc", "--noEmit"])

    # Python (mypy)
    if (project_dir / "pyproject.toml").exists() or (project_dir / "setup.py").exists():
        if shutil.which("mypy"):
            return ("mypy", ["mypy", "."])
        venv_mypy = project_dir / "venv/bin/mypy"
        if venv_mypy.exists():
            return ("mypy", [str(venv_mypy), "."])

    return None


def run_lint_check(project_dir: Path) -> QualityCheckResult:
    """
    Run lint check on the project.

    Automatically detects the appropriate linter based on project type.

    Args:
        project_dir: Path to the project directory

    Returns:
        QualityCheckResult with lint results
    """
    # Try JS/TS linter first
    linter = _detect_js_linter(project_dir)
    if linter is None:
        # Try Python linter
        linter = _detect_python_linter(project_dir)

    if linter is None:
        return {
            "name": "lint",
            "passed": True,
            "output": "No linter detected, skipping lint check",
            "duration_ms": 0,
        }

    name, cmd = linter
    exit_code, output, duration_ms = _run_command(cmd, project_dir)

    # Truncate output if too long
    if len(output) > 5000:
        output = output[:5000] + "\n... (truncated)"

    return {
        "name": f"lint ({name})",
        "passed": exit_code == 0,
        "output": output if output else "No issues found",
        "duration_ms": duration_ms,
    }


def run_type_check(project_dir: Path) -> QualityCheckResult:
    """
    Run type check on the project.

    Automatically detects the appropriate type checker based on project type.

    Args:
        project_dir: Path to the project directory

    Returns:
        QualityCheckResult with type check results
    """
    checker = _detect_type_checker(project_dir)

    if checker is None:
        return {
            "name": "type_check",
            "passed": True,
            "output": "No type checker detected, skipping type check",
            "duration_ms": 0,
        }

    name, cmd = checker
    exit_code, output, duration_ms = _run_command(cmd, project_dir, timeout=120)

    # Truncate output if too long
    if len(output) > 5000:
        output = output[:5000] + "\n... (truncated)"

    return {
        "name": f"type_check ({name})",
        "passed": exit_code == 0,
        "output": output if output else "No type errors found",
        "duration_ms": duration_ms,
    }


def run_custom_script(
    project_dir: Path,
    script_path: str | None = None,
    explicit_config: bool = False,
) -> QualityCheckResult | None:
    """
    Run a custom quality check script.

    Args:
        project_dir: Path to the project directory
        script_path: Path to the script (relative to project), defaults to .autocoder/quality-checks.sh
        explicit_config: If True, user explicitly configured this script, so missing = error

    Returns:
        QualityCheckResult, or None if default script doesn't exist
    """
    user_configured = script_path is not None or explicit_config

    if script_path is None:
        script_path = ".autocoder/quality-checks.sh"

    script_full_path = project_dir / script_path

    if not script_full_path.exists():
        if user_configured:
            # User explicitly configured a script that doesn't exist - return error
            return {
                "name": "custom_script",
                "passed": False,
                "output": f"Configured script not found: {script_path}",
                "duration_ms": 0,
            }
        # Default script doesn't exist - that's OK, skip silently
        return None

    # Make sure it's executable
    try:
        script_full_path.chmod(0o755)
    except OSError:
        pass

    exit_code, output, duration_ms = _run_command(
        ["bash", str(script_full_path)],
        project_dir,
        timeout=300,  # 5 minutes for custom scripts
    )

    # Truncate output if too long
    if len(output) > 10000:
        output = output[:10000] + "\n... (truncated)"

    return {
        "name": "custom_script",
        "passed": exit_code == 0,
        "output": output if output else "Script completed successfully",
        "duration_ms": duration_ms,
    }


def verify_quality(
    project_dir: Path,
    run_lint: bool = True,
    run_type_check: bool = True,
    run_custom: bool = True,
    custom_script_path: str | None = None,
) -> QualityGateResult:
    """
    Run all configured quality checks.

    Args:
        project_dir: Path to the project directory
        run_lint: Whether to run lint check
        run_type_check: Whether to run type check
        run_custom: Whether to run custom script
        custom_script_path: Path to custom script (optional)

    Returns:
        QualityGateResult with all check results
    """
    checks: dict[str, QualityCheckResult] = {}
    all_passed = True

    if run_lint:
        lint_result = run_lint_check(project_dir)
        checks["lint"] = lint_result
        if not lint_result["passed"]:
            all_passed = False

    if run_type_check:
        type_result = run_type_check(project_dir)
        checks["type_check"] = type_result
        if not type_result["passed"]:
            all_passed = False

    if run_custom:
        custom_result = run_custom_script(
            project_dir,
            custom_script_path,
            explicit_config=custom_script_path is not None,
        )
        if custom_result is not None:
            checks["custom_script"] = custom_result
            if not custom_result["passed"]:
                all_passed = False

    # Build summary
    passed_count = sum(1 for c in checks.values() if c["passed"])
    total_count = len(checks)
    failed_names = [name for name, c in checks.items() if not c["passed"]]

    if all_passed:
        summary = f"All {total_count} quality checks passed"
    else:
        summary = f"{passed_count}/{total_count} checks passed. Failed: {', '.join(failed_names)}"

    return {
        "passed": all_passed,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
        "summary": summary,
    }


def load_quality_config(project_dir: Path) -> dict:
    """
    Load quality gates configuration from .autocoder/config.json.

    Args:
        project_dir: Path to the project directory

    Returns:
        Quality gates config dict with defaults applied
    """
    defaults = {
        "enabled": True,
        "strict_mode": True,
        "checks": {
            "lint": True,
            "type_check": True,
            "unit_tests": False,
            "custom_script": None,
        },
    }

    config_path = project_dir / ".autocoder" / "config.json"
    if not config_path.exists():
        return defaults

    try:
        data = json.loads(config_path.read_text())
        quality_config = data.get("quality_gates", {})

        # Merge with defaults
        result = defaults.copy()
        for key in ["enabled", "strict_mode"]:
            if key in quality_config:
                result[key] = quality_config[key]

        if "checks" in quality_config:
            result["checks"] = {**defaults["checks"], **quality_config["checks"]}

        return result
    except (json.JSONDecodeError, OSError):
        return defaults
