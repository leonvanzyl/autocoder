import os
import time
from pathlib import Path

from autocoder.core.ui_build import is_ui_build_stale


def _touch(path: Path, ts: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (ts, ts))


def test_ui_build_stale_when_dist_missing(tmp_path):
    ui_root = tmp_path / "ui"
    _touch(ui_root / "src" / "App.tsx", time.time())
    assert is_ui_build_stale(ui_root) is True


def test_ui_build_not_stale_when_dist_newer(tmp_path):
    ui_root = tmp_path / "ui"
    now = time.time()
    _touch(ui_root / "src" / "App.tsx", now - 100)
    _touch(ui_root / "dist" / "assets" / "app.js", now)
    assert is_ui_build_stale(ui_root) is False


def test_ui_build_stale_when_source_newer(tmp_path):
    ui_root = tmp_path / "ui"
    now = time.time()
    _touch(ui_root / "dist" / "assets" / "app.js", now - 100)
    _touch(ui_root / "src" / "App.tsx", now)
    assert is_ui_build_stale(ui_root) is True
