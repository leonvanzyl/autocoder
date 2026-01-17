from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FeatureBacklog:
    features: list[dict[str, Any]]
    raw_text: str


def build_backlog_prompt(spec_text: str, feature_count: int | None = None) -> str:
    count_clause = ""
    if feature_count and feature_count > 0:
        count_clause = f"- Aim for ~{feature_count} features (close to this count, but prioritize coverage over exact count).\n"
    return (
        "You are generating a feature backlog for AutoCoder.\n"
        "Return ONLY valid JSON (no markdown fences). Output either:\n"
        "  {\"features\": [ ... ]}\n"
        "or a raw JSON array of feature objects.\n\n"
        "Each feature object MUST include:\n"
        "- name: short title\n"
        "- description: concise but specific\n"
        "- category: functional|style|backend|frontend|testing|docs|infra (pick best fit)\n"
        "- steps: array of strings\n"
        "Optional:\n"
        "- priority: integer (higher = more important)\n\n"
        "Guidelines:\n"
        "- Focus on real user-visible behavior and system correctness.\n"
        "- Include a mix of functional + style tests.\n"
        "- Order by importance (highest first).\n"
        f"{count_clause}"
        "\nProject specification:\n"
        f"{spec_text.strip()}\n"
    )


def _extract_json_block(text: str) -> str:
    if not text:
        return ""

    fence = re.search(r"```json\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    brace = text.find("{")
    bracket = text.find("[")
    if brace == -1 and bracket == -1:
        return text.strip()

    start = min(x for x in (brace, bracket) if x != -1)
    return text[start:].strip()


def _normalize_steps(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        lines = [line.strip(" \t-") for line in value.splitlines()]
        return [line for line in lines if line]
    return []


def parse_feature_backlog(text: str) -> FeatureBacklog:
    raw = text or ""
    block = _extract_json_block(raw)
    if not block:
        return FeatureBacklog(features=[], raw_text=raw)

    data: Any
    try:
        data = json.loads(block)
    except Exception:
        # Try to salvage by trimming trailing junk
        trimmed = block.split("\n\n")[0].strip()
        try:
            data = json.loads(trimmed)
        except Exception:
            return FeatureBacklog(features=[], raw_text=raw)

    if isinstance(data, dict) and "features" in data:
        data = data.get("features", [])

    if not isinstance(data, list):
        return FeatureBacklog(features=[], raw_text=raw)

    cleaned: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        if not name or not description:
            continue
        category = str(item.get("category") or "functional").strip().lower() or "functional"
        steps = _normalize_steps(item.get("steps"))
        if not steps:
            continue
        priority = item.get("priority")
        try:
            priority = int(priority) if priority is not None else None
        except Exception:
            priority = None
        cleaned.append(
            {
                "name": name,
                "description": description,
                "category": category,
                "steps": steps,
                "priority": priority,
            }
        )

    return FeatureBacklog(features=cleaned, raw_text=raw)


def infer_feature_count(project_dir: Path) -> int | None:
    """
    Best-effort: read prompts/.spec_status.json for a suggested feature count.
    """
    status_path = Path(project_dir) / "prompts" / ".spec_status.json"
    if not status_path.exists():
        return None
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        v = int(data.get("feature_count")) if data.get("feature_count") is not None else None
        return v if v and v > 0 else None
    except Exception:
        return None
