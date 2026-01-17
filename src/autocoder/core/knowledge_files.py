"""
Knowledge Files Helpers
=======================

Project-scoped markdown notes that can be injected into prompts.
These live under <project>/knowledge/*.md by default.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime


def get_knowledge_dir(project_dir: Path) -> Path:
    """Return the knowledge directory for a project."""
    return project_dir / "knowledge"


def list_knowledge_files(project_dir: Path, *, extensions: tuple[str, ...] = (".md",)) -> list[Path]:
    """List knowledge files for a project (sorted by name)."""
    knowledge_dir = get_knowledge_dir(project_dir)
    if not knowledge_dir.exists():
        return []
    files: list[Path] = []
    for ext in extensions:
        files.extend(knowledge_dir.glob(f"*{ext}"))
    files = [p for p in files if p.is_file()]
    return sorted(files, key=lambda p: p.name.lower())


def read_knowledge_file(path: Path, *, max_chars: int = 6000) -> str:
    """Read a knowledge file with size guardrails."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


def build_knowledge_bundle(
    project_dir: Path,
    *,
    max_files: int = 10,
    max_total_chars: int = 20_000,
    per_file_chars: int = 6000,
    extensions: tuple[str, ...] = (".md",),
) -> str:
    """
    Combine multiple knowledge files into a single prompt-safe bundle.

    Returns an empty string when no knowledge files are available.
    """
    files = list_knowledge_files(project_dir, extensions=extensions)
    if not files:
        return ""

    if max_files > 0:
        files = files[:max_files]

    chunks: list[str] = []
    total = 0
    for file_path in files:
        content = read_knowledge_file(file_path, max_chars=per_file_chars)
        if not content:
            continue
        header = f"### knowledge/{file_path.name}"
        block = f"{header}\n{content}".strip()
        if not block:
            continue
        if total + len(block) > max_total_chars:
            remaining = max_total_chars - total
            if remaining <= 0:
                break
            block = block[:remaining].rstrip() + "\n... (truncated)"
        chunks.append(block)
        total += len(block)
        if total >= max_total_chars:
            break

    if not chunks:
        return ""

    return "\n\n".join(chunks)


def knowledge_file_meta(path: Path) -> dict:
    """Basic metadata for UI responses."""
    stat = path.stat()
    return {
        "name": path.name,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
