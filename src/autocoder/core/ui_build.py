from __future__ import annotations

from pathlib import Path
from typing import Iterable


def find_ui_root(start: Path) -> Path | None:
    """
    Locate the repo-root `ui/` directory (source + build) by walking parents.
    Returns None when running from an installed package without UI sources.
    """
    base = start if start.is_dir() else start.parent
    for parent in [base, *base.parents]:
        ui_dir = parent / "ui"
        if (ui_dir / "package.json").exists():
            return ui_dir
    return None


def _newest_mtime(path: Path) -> float:
    if not path.exists():
        return 0.0
    if path.is_file():
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
    latest = 0.0
    for entry in path.rglob("*"):
        if not entry.is_file():
            continue
        try:
            latest = max(latest, entry.stat().st_mtime)
        except OSError:
            continue
    return latest


def _newest_mtime_for_paths(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        latest = max(latest, _newest_mtime(path))
    return latest


def is_ui_build_stale(ui_root: Path) -> bool:
    """
    Return True when `ui/dist` is missing/empty or older than UI source inputs.
    """
    src_dir = ui_root / "src"
    if not src_dir.exists():
        return False

    dist_dir = ui_root / "dist"
    dist_latest = _newest_mtime(dist_dir)
    if dist_latest <= 0:
        return True

    candidates = [
        src_dir,
        ui_root / "index.html",
        ui_root / "package.json",
        ui_root / "vite.config.ts",
        ui_root / "vite.config.js",
        ui_root / "tailwind.config.ts",
        ui_root / "tailwind.config.js",
        ui_root / "postcss.config.js",
        ui_root / "postcss.config.cjs",
        ui_root / "tsconfig.json",
        ui_root / "tsconfig.app.json",
        ui_root / "tsconfig.node.json",
    ]
    source_latest = _newest_mtime_for_paths([p for p in candidates if p.exists()])
    if source_latest <= 0:
        return False
    return source_latest > dist_latest
