import subprocess
from pathlib import Path

from autocoder.core.gatekeeper import Gatekeeper


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def test_gatekeeper_blocks_on_failed_lint_command(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "checkout", "-b", "main"], repo)

    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.0.0'\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "autocoder.yaml").write_text(
        """
commands:
  test:
    command: "python -m pytest -q"
    timeout: 120
  lint:
    command: "python -c \\"import sys; sys.exit(1)\\""
    timeout: 10
    allow_fail: false
""".strip(),
        encoding="utf-8",
    )

    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "init"], repo)

    _run(["git", "checkout", "-b", "feat/x"], repo)
    (repo / "foo.txt").write_text("b\n", encoding="utf-8")
    _run(["git", "add", "foo.txt"], repo)
    _run(["git", "commit", "-m", "change"], repo)

    _run(["git", "checkout", "main"], repo)
    gatekeeper = Gatekeeper(str(repo))
    result = gatekeeper.verify_and_merge("feat/x", fetch_remote=False, push_remote=False, delete_feature_branch=False)
    assert result["approved"] is False
    assert "verification" in result
    fp = result.get("diff_fingerprint")
    assert isinstance(fp, str) and len(fp) == 64


def test_gatekeeper_runs_acceptance_command(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "checkout", "-b", "main"], repo)

    (repo / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.0.0'\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "autocoder.yaml").write_text(
        """
commands:
  test:
    command: "python -m pytest -q"
    timeout: 120
  acceptance:
    command: "python -c \\"import sys; sys.exit(1)\\""
    timeout: 10
    allow_fail: false
""".strip(),
        encoding="utf-8",
    )

    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "init"], repo)

    _run(["git", "checkout", "-b", "feat/x"], repo)
    (repo / "foo.txt").write_text("b\n", encoding="utf-8")
    _run(["git", "add", "foo.txt"], repo)
    _run(["git", "commit", "-m", "change"], repo)

    _run(["git", "checkout", "main"], repo)
    gatekeeper = Gatekeeper(str(repo))
    result = gatekeeper.verify_and_merge("feat/x", fetch_remote=False, push_remote=False, delete_feature_branch=False)
    assert result["approved"] is False
    assert "acceptance" in str(result.get("reason") or "").lower()
