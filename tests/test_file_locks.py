from pathlib import Path

from autocoder.core.file_locks import (
    acquire_lock,
    canonicalize_path,
    get_lock_holder,
    list_locks,
    release_lock,
)


def test_canonicalize_path_normalizes():
    assert canonicalize_path("./src\\main.py") == "src/main.py"
    assert canonicalize_path("/src/main.py") == "src/main.py"


def test_lock_acquire_release(tmp_path: Path):
    lock_dir = tmp_path / "locks"
    assert acquire_lock(lock_dir, "a.txt", "agent-1", timeout_seconds=0) is True
    assert get_lock_holder(lock_dir, "a.txt") == "agent-1"

    # Second agent can't acquire while held.
    assert acquire_lock(lock_dir, "a.txt", "agent-2", timeout_seconds=0) is False
    assert get_lock_holder(lock_dir, "a.txt") == "agent-1"

    # Release by wrong agent fails.
    assert release_lock(lock_dir, "a.txt", "agent-2") is False
    assert release_lock(lock_dir, "a.txt", "agent-1") is True
    assert get_lock_holder(lock_dir, "a.txt") is None

    # List locks empty after release.
    assert list_locks(lock_dir) == []

