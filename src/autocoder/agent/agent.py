"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

from claude_agent_sdk import ClaudeSDKClient

# Fix Windows console encoding for Unicode characters (emoji, etc.)
# Without this, print() can crash when Claude outputs emoji like ✅
if sys.platform == "win32":
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

from ..core.port_config import get_web_port
from .client import create_client
from .progress import print_session_header, print_progress_summary, has_features
from .prompts import (
    get_initializer_prompt,
    get_coding_prompt,
    get_coding_prompt_yolo,
    copy_spec_to_project,
    has_project_prompts,
)
from .retry import execute_with_retry, retry_config_from_env
from ..core.database import get_database


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    print("Sending prompt to Claude Agent SDK...\n")

    def _env_int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    max_tool_calls = _env_int("AUTOCODER_GUARDRAIL_MAX_TOOL_CALLS", 400)
    max_consecutive_tool_errors = _env_int("AUTOCODER_GUARDRAIL_MAX_CONSECUTIVE_TOOL_ERRORS", 25)
    max_total_tool_errors = _env_int("AUTOCODER_GUARDRAIL_MAX_TOOL_ERRORS", 150)

    try:
        # Send the query (with retry/backoff for transient failures like 429/timeouts)
        retry_cfg = retry_config_from_env()

        async def _do_query() -> None:
            await client.query(message)

        await execute_with_retry(_do_query, config=retry_cfg)

        # Collect response text and show tool use
        response_text = ""
        tool_calls = 0
        consecutive_tool_errors = 0
        total_tool_errors = 0
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            # Handle AssistantMessage (text and tool use)
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        print(block.text, end="", flush=True)
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_calls += 1
                        if tool_calls > max_tool_calls:
                            err = (
                                f"Guardrail tripped: too many tool calls in one session "
                                f"({tool_calls} > {max_tool_calls})"
                            )
                            print(f"\n[{err}]", flush=True)
                            return "error", err
                        print(f"\n[Tool: {block.name}]", flush=True)
                        if hasattr(block, "input"):
                            input_str = str(block.input)
                            if len(input_str) > 200:
                                print(f"   Input: {input_str[:200]}...", flush=True)
                            else:
                                print(f"   Input: {input_str}", flush=True)

            # Handle UserMessage (tool results)
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)
                        content_str = str(result_content)

                        # Check if command was blocked by security hook
                        if "blocked" in content_str.lower():
                            total_tool_errors += 1
                            consecutive_tool_errors += 1
                            print(f"   [BLOCKED] {result_content}", flush=True)
                        elif is_error:
                            # Show errors (truncated)
                            total_tool_errors += 1
                            consecutive_tool_errors += 1
                            error_str = content_str[:500]
                            print(f"   [Error] {error_str}", flush=True)
                        else:
                            consecutive_tool_errors = 0
                            # Tool succeeded - just show brief confirmation
                            print("   [Done]", flush=True)

                        if total_tool_errors > max_total_tool_errors:
                            err = (
                                f"Guardrail tripped: too many tool errors "
                                f"({total_tool_errors} > {max_total_tool_errors})"
                            )
                            print(f"\n[{err}]", flush=True)
                            return "error", err
                        if consecutive_tool_errors > max_consecutive_tool_errors:
                            err = (
                                f"Guardrail tripped: too many consecutive tool errors "
                                f"({consecutive_tool_errors} > {max_consecutive_tool_errors})"
                            )
                            print(f"\n[{err}]", flush=True)
                            return "error", err

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        print(f"Error during agent session: {e}")
        return "error", str(e)


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
    yolo_mode: bool = False,
    *,
    features_project_dir: Optional[Path] = None,
    assigned_feature_id: Optional[int] = None,
    agent_id: Optional[str] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
        yolo_mode: If True, skip browser testing and use YOLO prompt
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    if agent_id:
        print(f"Agent ID: {agent_id}")
    print(f"Model: {model}")
    if yolo_mode:
        print("Mode: YOLO (testing disabled)")
    else:
        print("Mode: Standard (full testing)")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    features_state_dir = (features_project_dir or project_dir).resolve()

    # Check if this is a fresh start or continuation
    # Uses has_features() which checks if the database actually has features,
    # not just if the file exists (empty db should still trigger initializer)
    is_first_run = not has_features(features_state_dir)

    if assigned_feature_id is not None and is_first_run:
        raise RuntimeError(
            f"Assigned feature #{assigned_feature_id} but no features exist in {features_state_dir}"
        )

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()
        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is generating 200 detailed test cases.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project")
        print_progress_summary(features_state_dir)

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_first_run)

        # Create client (fresh context)
        client = create_client(
            project_dir,
            model,
            yolo_mode=yolo_mode,
            features_project_dir=features_state_dir,
        )

        # Choose prompt based on session type
        # Pass project_dir to enable project-specific prompts
        if is_first_run:
            prompt = get_initializer_prompt(project_dir)
            is_first_run = False  # Only use initializer once
        else:
            # Use YOLO prompt if in YOLO mode
            if yolo_mode:
                prompt = get_coding_prompt_yolo(project_dir)
            else:
                prompt = get_coding_prompt(project_dir)

        if assigned_feature_id is not None:
            qa_enabled = os.environ.get("AUTOCODER_QA_FIX_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
            qa_max = 0
            try:
                qa_max = int(os.environ.get("AUTOCODER_QA_MAX_SESSIONS", "3"))
            except Exception:
                qa_max = 3
            qa_max = max(0, qa_max)

            last_error_text = ""
            artifact_path = ""
            attempts = 0
            if qa_enabled:
                try:
                    db = get_database(str(features_state_dir))
                    row = db.get_feature(int(assigned_feature_id)) or {}
                    last_error_text = str(row.get("last_error") or "").strip()
                    artifact_path = str(row.get("last_artifact_path") or "").strip()
                    attempts = int(row.get("attempts") or 0)
                except Exception:
                    last_error_text = ""
                    artifact_path = ""
                    attempts = 0

            prompt = (
                "IMPORTANT: You are running as a parallel worker with an explicit assignment.\n"
                f"- Work ONLY on feature_id={assigned_feature_id}.\n"
                "- Do NOT call `feature_get_next`.\n"
                "- Call `feature_get_by_id` for the assigned feature, then proceed as usual.\n\n"
                "- When finished, call `feature_mark_passing` to submit for Gatekeeper verification (it may not immediately set passes=true).\n\n"
                + (
                    (
                        "QA FIX MODE (enabled):\n"
                        "- Your job is to fix the last Gatekeeper/verification failure for this feature.\n"
                        "- Focus on tests/lint/typecheck failures first. Do NOT expand scope.\n"
                        "- After making fixes, run the failing command(s) locally in the worktree and commit.\n"
                        "- Then submit again with `feature_mark_passing`.\n"
                        + (f"\nAttempts so far: {attempts} (QA max sessions: {qa_max})\n" if qa_max else "\n")
                        + (f"\nLast error:\n{last_error_text}\n" if last_error_text else "")
                        + (f"\nLast artifact path:\n{artifact_path}\n" if artifact_path else "")
                        + "\n---\n\n"
                    )
                    if qa_enabled and qa_max > 0 and attempts > 0 and attempts <= qa_max and (last_error_text or artifact_path)
                    else ""
                )
                + prompt
            )

        # Run session with async context manager
        async with client:
            status, response = await run_agent_session(client, prompt, project_dir)

        # Handle status
        if status == "continue":
            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(features_state_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            print("\nSession encountered an error")
            print("Will retry with a fresh session...")
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        # Small delay between sessions
        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(features_state_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print(f"\n  Then open http://localhost:{get_web_port()} (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
