"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
import io
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from claude_agent_sdk import ClaudeSDKClient

# Module logger for error tracking (user-facing messages use print())
logger = logging.getLogger(__name__)

# Fix Windows console encoding for Unicode characters (emoji, etc.)
# Without this, print() crashes when Claude outputs emoji like ✅
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from client import create_client
from progress import (
    clear_stuck_features,
    count_passing_tests,
    has_features,
    print_progress_summary,
    print_session_header,
    send_session_event,
)
from prompts import (
    copy_spec_to_project,
    get_coding_prompt,
    get_initializer_prompt,
    get_single_feature_prompt,
    get_testing_prompt,
)
from rate_limit_utils import (
    RATE_LIMIT_PATTERNS,
    is_rate_limit_error,
    parse_retry_after,
)

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

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
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

                        # Check if command was blocked by security hook
                        if "blocked" in str(result_content).lower():
                            print(f"   [BLOCKED] {result_content}", flush=True)
                        elif is_error:
                            # Show errors (truncated)
                            error_str = str(result_content)[:500]
                            print(f"   [Error] {error_str}", flush=True)
                        else:
                            # Tool succeeded - just show brief confirmation
                            print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        error_str = str(e)
        logger.error(f"Agent session error: {e}", exc_info=True)
        print(f"Error during agent session: {error_str}")

        # Detect rate limit errors from exception message
        if is_rate_limit_error(error_str):
            # Try to extract retry-after time from error
            retry_seconds = parse_retry_after(error_str)
            if retry_seconds is not None:
                return "rate_limit", str(retry_seconds)
            else:
                return "rate_limit", "unknown"

        return "error", error_str


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
    yolo_mode: bool = False,
    feature_id: Optional[int] = None,
    agent_type: Optional[str] = None,
    testing_feature_id: Optional[int] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
        yolo_mode: If True, skip browser testing in coding agent prompts
        feature_id: If set, work only on this specific feature (used by orchestrator for coding agents)
        agent_type: Type of agent: "initializer", "coding", "testing", or None (auto-detect)
        testing_feature_id: For testing agents, the pre-claimed feature ID to test
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Model: {model}")
    if agent_type:
        print(f"Agent type: {agent_type}")
    if yolo_mode:
        print("Mode: YOLO (testing agents disabled)")
    if feature_id:
        print(f"Feature assignment: #{feature_id}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: Do NOT clear stuck features in parallel mode!
    # The orchestrator manages feature claiming atomically.
    # Clearing here causes race conditions where features are marked in_progress
    # by the orchestrator but immediately cleared by the agent subprocess on startup.
    #
    # For single-agent mode or manual runs, clearing is still safe because
    # there's only one agent at a time and it happens before claiming any features.
    #
    # Only clear if we're NOT in a parallel orchestrator context
    # (detected by checking if this agent is a subprocess spawned by orchestrator)
    try:
        import psutil
        parent_process = psutil.Process().parent()
        parent_name = parent_process.name() if parent_process else ""

        # Only clear if parent is NOT python (i.e., we're running manually, not from orchestrator)
        if "python" not in parent_name.lower():
            clear_stuck_features(project_dir)
    except (ImportError, ModuleNotFoundError):
        # psutil not available - assume single-agent mode and clear
        clear_stuck_features(project_dir)
    except Exception:
        # If parent process check fails, err on the safe side and clear
        clear_stuck_features(project_dir)

    # Determine agent type if not explicitly set
    if agent_type is None:
        # Auto-detect based on whether we have features
        # (This path is for legacy compatibility - orchestrator should always set agent_type)
        is_first_run = not has_features(project_dir)
        if is_first_run:
            agent_type = "initializer"
        else:
            agent_type = "coding"

    is_initializer = agent_type == "initializer"

    # Send session started webhook
    send_session_event(
        "session_started",
        project_dir,
        agent_type=agent_type,
        feature_id=feature_id,
        feature_name=f"Feature #{feature_id}" if feature_id else None,
    )

    if is_initializer:
        print("Running as INITIALIZER agent")
        print()
        print("=" * 70)
        print("  NOTE: Initialization takes 10-20+ minutes!")
        print("  The agent is generating detailed test cases.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir)
    elif agent_type == "testing":
        print("Running as TESTING agent (regression testing)")
        print_progress_summary(project_dir)
    else:
        print("Running as CODING agent")
        print_progress_summary(project_dir)

    # Main loop
    iteration = 0
    rate_limit_retries = 0  # Track consecutive rate limit errors for exponential backoff
    error_retries = 0  # Track consecutive non-rate-limit errors

    while True:
        iteration += 1

        # Check if all features are already complete (before starting a new session)
        # Skip this check if running as initializer (needs to create features first)
        if not is_initializer and iteration == 1:
            passing, in_progress, total = count_passing_tests(project_dir)
            if total > 0 and passing == total:
                print("\n" + "=" * 70)
                print("  ALL FEATURES ALREADY COMPLETE!")
                print("=" * 70)
                print(f"\nAll {total} features are passing. Nothing left to do.")
                break

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        # Print session header
        print_session_header(iteration, is_initializer)

        # Create client (fresh context)
        # Pass agent_id for browser isolation in multi-agent scenarios
        import os
        if agent_type == "testing":
            agent_id = f"testing-{os.getpid()}"  # Unique ID for testing agents
        elif feature_id:
            agent_id = f"feature-{feature_id}"
        else:
            agent_id = None
        client = create_client(project_dir, model, yolo_mode=yolo_mode, agent_id=agent_id)

        # Choose prompt based on agent type
        if agent_type == "initializer":
            prompt = get_initializer_prompt(project_dir)
        elif agent_type == "testing":
            prompt = get_testing_prompt(project_dir, testing_feature_id)
        elif feature_id:
            # Single-feature mode (used by orchestrator for coding agents)
            prompt = get_single_feature_prompt(feature_id, project_dir, yolo_mode)
        else:
            # General coding prompt (legacy path)
            prompt = get_coding_prompt(project_dir)

        # Run session with async context manager
        # Wrap in try/except to handle MCP server startup failures gracefully
        try:
            async with client:
                status, response = await run_agent_session(client, prompt, project_dir)
        except Exception as e:
            logger.error(f"Client/MCP server error: {e}", exc_info=True)
            print(f"Client/MCP server error: {e}")
            # Don't crash - return error status so the loop can retry
            status, response = "error", str(e)

        # Check for project completion - EXIT when all features pass
        if "all features are passing" in response.lower() or "no more work to do" in response.lower():
            print("\n" + "=" * 70)
            print("  🎉 PROJECT COMPLETE - ALL FEATURES PASSING!")
            print("=" * 70)
            print_progress_summary(project_dir)
            break

        # Handle status
        if status == "continue":
            # Reset error retries on success; rate-limit retries reset only if no signal
            error_retries = 0
            reset_rate_limit_retries = True

            delay_seconds = AUTO_CONTINUE_DELAY_SECONDS
            target_time_str = None

            # Check for rate limit indicators in response text
            response_lower = response.lower()
            if any(pattern in response_lower for pattern in RATE_LIMIT_PATTERNS):
                print("Claude Agent SDK indicated rate limit reached.")
                reset_rate_limit_retries = False

                # Try to extract retry-after from response text first
                retry_seconds = parse_retry_after(response)
                if retry_seconds is not None:
                    delay_seconds = retry_seconds
                else:
                    # Use exponential backoff when retry-after unknown
                    delay_seconds = min(60 * (2 ** rate_limit_retries), 3600)
                    rate_limit_retries += 1

                # Try to parse reset time from response (more specific format)
                match = re.search(
                    r"(?i)\bresets(?:\s+at)?\s+(\d+)(?::(\d+))?\s*(am|pm)\s*\(([^)]+)\)",
                    response,
                )
                if match:
                    hour = int(match.group(1))
                    minute = int(match.group(2)) if match.group(2) else 0
                    period = match.group(3).lower()
                    tz_name = match.group(4).strip()

                    # Convert to 24-hour format
                    if period == "pm" and hour != 12:
                        hour += 12
                    elif period == "am" and hour == 12:
                        hour = 0

                    try:
                        tz = ZoneInfo(tz_name)
                        now = datetime.now(tz)
                        target = now.replace(
                            hour=hour, minute=minute, second=0, microsecond=0
                        )

                        # If target time has already passed today, wait until tomorrow
                        if target <= now:
                            target += timedelta(days=1)

                        delta = target - now
                        delay_seconds = min(
                            delta.total_seconds(), 24 * 60 * 60
                        )  # Clamp to 24 hours max
                        target_time_str = target.strftime("%B %d, %Y at %I:%M %p %Z")

                    except Exception as e:
                        logger.warning(f"Error parsing reset time: {e}, using default delay")
                        print(f"Error parsing reset time: {e}, using default delay")

            if target_time_str:
                print(
                    f"\nClaude Code Limit Reached. Agent will auto-continue in {delay_seconds:.0f}s ({target_time_str})...",
                    flush=True,
                )
            else:
                print(
                    f"\nAgent will auto-continue in {delay_seconds:.0f}s...", flush=True
                )

            sys.stdout.flush()  # this should allow the pause to be displayed before sleeping
            print_progress_summary(project_dir)

            # Check if all features are complete - exit gracefully if done
            passing, in_progress, total = count_passing_tests(project_dir)
            if total > 0 and passing == total:
                print("\n" + "=" * 70)
                print("  ALL FEATURES COMPLETE!")
                print("=" * 70)
                print(f"\nCongratulations! All {total} features are passing.")
                print("The autonomous agent has finished its work.")
                break

            # Single-feature mode OR testing agent: exit after one session
            if feature_id is not None or agent_type == "testing":
                if agent_type == "testing":
                    print("\nTesting agent complete. Terminating session.")
                else:
                    print(f"\nSingle-feature mode: Feature #{feature_id} session complete.")
                break

            # Reset rate limit retries only if no rate limit signal was detected
            if reset_rate_limit_retries:
                rate_limit_retries = 0

            await asyncio.sleep(delay_seconds)

        elif status == "rate_limit":
            # Smart rate limit handling with exponential backoff
            if response != "unknown":
                delay_seconds = int(response)
                print(f"\nRate limit hit. Waiting {delay_seconds} seconds before retry...")
            else:
                # Use exponential backoff when retry-after unknown
                delay_seconds = min(60 * (2 ** rate_limit_retries), 3600)  # Max 1 hour
                rate_limit_retries += 1
                print(f"\nRate limit hit. Backoff wait: {delay_seconds} seconds (attempt #{rate_limit_retries})...")

            await asyncio.sleep(delay_seconds)

        elif status == "error":
            # Non-rate-limit errors: linear backoff capped at 5 minutes
            error_retries += 1
            delay_seconds = min(30 * error_retries, 300)  # Max 5 minutes
            logger.warning("Session encountered an error, will retry")
            print("\nSession encountered an error")
            print(f"Will retry in {delay_seconds}s (attempt #{error_retries})...")
            await asyncio.sleep(delay_seconds)

        # Small delay between sessions
        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    # Send session ended webhook
    passing, in_progress, total = count_passing_tests(project_dir)
    send_session_event(
        "session_ended",
        project_dir,
        agent_type=agent_type,
        feature_id=feature_id,
        extra={
            "passing": passing,
            "total": total,
            "percentage": round((passing / total) * 100, 1) if total > 0 else 0,
        }
    )

    print("\nDone!")
