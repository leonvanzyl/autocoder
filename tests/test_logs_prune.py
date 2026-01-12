from pathlib import Path

from autocoder.core.logs import prune_worker_logs


def test_prune_worker_logs_keeps_newest(tmp_path):
    logs_dir = tmp_path / ".autocoder" / "logs"
    logs_dir.mkdir(parents=True)

    # Create 5 log files.
    paths: list[Path] = []
    for i in range(5):
        p = logs_dir / f"a{i}.log"
        p.write_text("x" * (10 + i), encoding="utf-8")
        paths.append(p)

    # Force deterministic mtime ordering (oldest to newest).
    for idx, p in enumerate(paths):
        # Windows resolution is fine for this.
        ts = 1000000000 + idx
        p.touch()
        p.chmod(p.stat().st_mode)
        import os

        os.utime(p, (ts, ts))

    result = prune_worker_logs(tmp_path, keep_days=9999, keep_files=2, max_total_mb=200)
    assert result.deleted_files == 3
    assert result.kept_files == 2
    remaining = sorted(logs_dir.glob("*.log"))
    assert len(remaining) == 2
    assert remaining[0].name == "a3.log"
    assert remaining[1].name == "a4.log"

