from __future__ import annotations

from pathlib import Path

from autocoder.core.gatekeeper import Gatekeeper


def _git(cwd: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def test_gatekeeper_ignores_claude_cli_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    # Base commit
    (repo / "autocoder.yaml").write_text(
        "commands:\n"
        "  test:\n"
        "    - command: \"{PY} -c \\\"import sys; sys.exit(0)\\\"\"\n"
        "      timeout: 60\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md", "autocoder.yaml")
    _git(repo, "commit", "-m", "base")

    # Feature branch commit
    _git(repo, "checkout", "-b", "feat/1")
    (repo / "x.txt").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "x.txt")
    _git(repo, "commit", "-m", "feat")

    # Back to main
    _git(repo, "checkout", "master")

    # Simulate Claude Code CLI artifacts in the project root (untracked).
    (repo / ".claude_settings.json").write_text("{}", encoding="utf-8")
    (repo / "claude-progress.txt").write_text("progress\n", encoding="utf-8")

    # Simulate redundant root spec artifact (only ignored when prompts/app_spec.txt exists).
    (repo / "prompts").mkdir(parents=True, exist_ok=True)
    (repo / "prompts" / "app_spec.txt").write_text("<project_specification/>\n", encoding="utf-8")
    (repo / "app_spec.txt").write_text("artifact\n", encoding="utf-8")

    gk = Gatekeeper(str(repo))
    result = gk.verify_and_merge("feat/1", allow_no_tests=False, fetch_remote=False, push_remote=False)
    assert result["approved"] is True
