import os

from autocoder.server.server_lock import ServerLock


def test_server_lock_blocks_when_pid_alive(tmp_path, monkeypatch):
    lock = ServerLock(9999, namespace="test-lock")
    # Force lock file to exist with current PID.
    lock.lock_file.write_text(str(os.getpid()), encoding="utf-8")
    assert lock.status().is_running is True
    assert lock.acquire(force=False, timeout_s=0) is False


def test_server_lock_clears_stale_pid(monkeypatch):
    lock = ServerLock(9998, namespace="test-lock")
    lock.lock_file.write_text("999999", encoding="utf-8")  # very likely nonexistent
    assert lock.status().is_running is False
    assert lock.acquire(force=True, timeout_s=1) is True
    lock.release()

