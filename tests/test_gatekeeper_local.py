import subprocess
from pathlib import Path

from autocoder.core.gatekeeper import Gatekeeper


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def test_gatekeeper_merges_locally(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    _run(["git", "init"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    _run(["git", "checkout", "-b", "main"], repo)

    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'x'\nversion = '0.0.0'\n", encoding="utf-8"
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (repo / "foo.txt").write_text("a\n", encoding="utf-8")

    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "init"], repo)

    _run(["git", "checkout", "-b", "feat/test-1"], repo)
    (repo / "foo.txt").write_text("b\n", encoding="utf-8")
    _run(["git", "add", "foo.txt"], repo)
    _run(["git", "commit", "-m", "change"], repo)

    _run(["git", "checkout", "main"], repo)
    main_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    gatekeeper = Gatekeeper(str(repo))
    result = gatekeeper.verify_and_merge(
        "feat/test-1",
        fetch_remote=False,
        push_remote=False,
        allow_no_tests=False,
        delete_feature_branch=False,
    )
    assert result["approved"] is True

    main_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert main_after != main_before
    assert result["merge_commit"] == main_after
    assert (repo / "foo.txt").read_text(encoding="utf-8") == "b\n"

