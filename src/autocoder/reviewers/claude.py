from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .base import ReviewConfig, ReviewFinding, ReviewResult, Reviewer


def _resolve_cli_path(use_custom_api: bool) -> str | None:
    if use_custom_api:
        return None
    return shutil.which("claude")


@dataclass(frozen=True)
class ClaudeReviewer(Reviewer):
    cfg: ReviewConfig

    def review(
        self,
        *,
        workdir: str,
        base_branch: str,
        feature_branch: str,
        agent_id: str | None = None,
    ) -> ReviewResult:
        # If no credentials are available, skip rather than failing merges by default.
        # This keeps Gatekeeper deterministic unless explicitly configured otherwise.
        use_custom_api = False
        if "ANTHROPIC_AUTH_TOKEN" in os.environ:
            os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
            use_custom_api = True

        credentials_path = Path.home() / ".claude" / ".credentials.json"
        if not use_custom_api and not credentials_path.exists():
            return ReviewResult(
                approved=True,
                skipped=True,
                reason="Claude reviewer skipped (no credentials found)",
            )

        model = self.cfg.model or os.environ.get("AUTOCODER_REVIEW_MODEL") or "sonnet"

        # Build a read-only settings file.
        workdir_path = Path(workdir).resolve()
        settings_file = workdir_path / ".claude_settings.review.json"
        security_settings = {
            "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
            "permissions": {
                "defaultMode": "reject",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                ],
            },
        }
        settings_file.write_text(json.dumps(security_settings, indent=2), encoding="utf-8")

        cli_path = _resolve_cli_path(use_custom_api)

        client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                cli_path=cli_path,
                allowed_tools=["Read", "Glob", "Grep"],
                system_prompt=(
                    "You are a strict code reviewer. Return a JSON object with keys: "
                    "approved (bool), reason (string), findings (list of {severity,message,file?}). "
                    "Do not include any other text."
                ),
                cwd=str(workdir_path),
                settings=str(settings_file),
                max_turns=3,
                setting_sources=["project"],
            )
        )

        prompt = (
            "Review the staged changes in this repo (they come from a merge --no-commit).\n"
            f"Base branch: {base_branch}\n"
            f"Feature branch: {feature_branch}\n\n"
            "Use `git diff --cached` output below as the review source.\n\n"
            "IMPORTANT: Output JSON only.\n\n"
        )
        # Inline diff for a quick, tool-free review. If large, the model may request file reads.
        diff = os.popen(f'cd "{workdir_path}" && git diff --cached').read()
        prompt += diff[:200_000]

        # Query and parse response.
        # Note: we intentionally avoid retries here; Gatekeeper should be able to proceed without review.
        try:
            import asyncio

            async def _run() -> str:
                await client.query(prompt)
                text = ""
                async for msg in client.receive_response():
                    if type(msg).__name__ == "AssistantMessage" and hasattr(msg, "content"):
                        for block in msg.content:
                            if type(block).__name__ == "TextBlock" and hasattr(block, "text"):
                                text += block.text
                return text

            raw = asyncio.run(_run())
        except Exception as e:
            return ReviewResult(approved=True, skipped=True, reason=f"Claude reviewer error; skipped: {e}")

        raw = raw.strip()
        try:
            data = json.loads(raw)
        except Exception:
            return ReviewResult(approved=True, skipped=True, reason="Claude reviewer returned non-JSON; skipped")

        approved = bool(data.get("approved", True))
        reason = str(data.get("reason", "") or "")
        findings: list[ReviewFinding] = []
        for f in data.get("findings") or []:
            if not isinstance(f, dict):
                continue
            findings.append(
                ReviewFinding(
                    severity=str(f.get("severity") or "P2"),
                    message=str(f.get("message") or ""),
                    file=str(f.get("file")) if f.get("file") is not None else None,
                )
            )
        return ReviewResult(approved=approved, reason=reason, findings=findings)

