# Phase 3: Mid-Session Command Approval - Implementation Specification

**Status:** Not yet implemented (Phases 1 & 2 complete)
**Estimated Effort:** 2-3 days for experienced developer
**Priority:** Medium (nice-to-have, not blocking)

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [User Experience](#user-experience)
- [Technical Architecture](#technical-architecture)
- [Implementation Checklist](#implementation-checklist)
- [Detailed Implementation Guide](#detailed-implementation-guide)
- [Testing Strategy](#testing-strategy)
- [Security Considerations](#security-considerations)
- [Future Enhancements](#future-enhancements)

---

## Executive Summary

### What is Phase 3?

Phase 3 adds **mid-session approval** for bash commands that aren't in the allowlist. Instead of immediately blocking unknown commands, the agent can request user approval in real-time.

### Current State (Phases 1 & 2)

The agent can only run commands that are:
1. In the hardcoded allowlist (npm, git, ls, etc.)
2. In project config (`.autocoder/allowed_commands.yaml`)
3. In org config (`~/.autocoder/config.yaml`)

If the agent tries an unknown command → **immediately blocked**.

### Phase 3 Vision

If the agent tries an unknown command → **request approval**:
- **CLI mode**: Rich TUI overlay shows approval dialog
- **UI mode**: React banner/toast prompts user
- **User decides**: Session-only, Permanent (save to YAML), or Deny
- **Timeout**: Auto-deny after 5 minutes (configurable)

### Benefits

1. **Flexibility**: Don't need to pre-configure every possible command
2. **Discovery**: See what commands the agent actually needs
3. **Safety**: Still requires explicit approval (not automatic)
4. **Persistence**: Can save approved commands to config for future sessions

### Non-Goals

- **NOT** auto-approval (always requires user confirmation)
- **NOT** bypassing hardcoded blocklist (sudo, dd, etc. are NEVER allowed)
- **NOT** bypassing org-level blocklist (those remain final)

---

## User Experience

### CLI Mode Flow

```
Agent is working...
Agent tries: xcodebuild -project MyApp.xcodeproj

┌─────────────────────────────────────────────────────────────┐
│ ⚠️  COMMAND APPROVAL REQUIRED                                │
├─────────────────────────────────────────────────────────────┤
│ The agent is requesting permission to run:                  │
│                                                              │
│   xcodebuild -project MyApp.xcodeproj                       │
│                                                              │
│ This command is not in your allowed commands list.          │
│                                                              │
│ Options:                                                     │
│   [S] Allow for this Session only                          │
│   [P] Allow Permanently (save to config)                   │
│   [D] Deny (default in 5 minutes)                          │
│                                                              │
│ Your choice (S/P/D):                                        │
└─────────────────────────────────────────────────────────────┘
```

**For dangerous commands** (aws, kubectl, sudo*):

```
╔═══════════════════════════════════════════════════════════════╗
║ ⚠️  DANGER: PRIVILEGED COMMAND REQUESTED                       ║
╠═══════════════════════════════════════════════════════════════╣
║ The agent is requesting: aws s3 ls                            ║
║                                                                ║
║ aws is a CLOUD CLI that can:                                  ║
║   • Access production infrastructure                          ║
║   • Modify or delete cloud resources                          ║
║   • Incur significant costs                                   ║
║                                                                ║
║ This action could have SERIOUS consequences.                  ║
║                                                                ║
║ Type CONFIRM to allow, or press Enter to deny:                ║
╚═══════════════════════════════════════════════════════════════╝
```

*Note: sudo would still be in hardcoded blocklist, but this shows the UX pattern

### UI Mode Flow

**React UI Banner** (top of screen):

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️  Agent requesting permission: xcodebuild                  │
│                                                              │
│ [Session Only] [Save to Config] [Deny]                      │
│                                                              │
│ Auto-denies in: 4:32                                        │
└─────────────────────────────────────────────────────────────┘
```

**Multiple requests queued:**

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️  3 approval requests pending                              │
│                                                              │
│ 1. xcodebuild -project MyApp.xcodeproj                      │
│    [Session] [Save] [Deny]                                  │
│                                                              │
│ 2. swift package resolve                                    │
│    [Session] [Save] [Deny]                                  │
│                                                              │
│ 3. xcrun simctl list devices                                │
│    [Session] [Save] [Deny]                                  │
└─────────────────────────────────────────────────────────────┘
```

### Response Behavior

| User Action | Agent Behavior | Config Updated |
|-------------|----------------|----------------|
| Session Only | Command allowed this session | No |
| Permanent | Command allowed forever | Yes - appended to YAML |
| Deny | Command blocked, agent sees error | No |
| Timeout (5 min) | Command blocked, agent sees timeout | No |

---

## Technical Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Agent tries command: xcodebuild                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. bash_security_hook() checks allowlist                    │
│    → Not found, not in blocklist                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Hook returns: {"decision": "pending",                    │
│                   "request_id": "req_123",                  │
│                   "command": "xcodebuild"}                  │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐
│ CLI Mode            │  │ UI Mode             │
│                     │  │                     │
│ approval_tui.py     │  │ WebSocket message   │
│ shows Rich dialog   │  │ → React banner      │
└──────────┬──────────┘  └──────────┬──────────┘
           │                        │
           └────────┬───────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. User responds: "session" / "permanent" / "deny"          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. approval_manager.respond(request_id, decision)           │
│    → If permanent: persist_command()                        │
│    → If session: add to in-memory set                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Hook gets response, returns to agent:                    │
│    → "allow" or "block"                                     │
└─────────────────────────────────────────────────────────────┘
```

### State Management

**ApprovalManager** (new class in `security.py`):

```python
class ApprovalManager:
    """
    Manages pending approval requests and responses.
    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._pending: Dict[str, PendingRequest] = {}
        self._session_allowed: Set[str] = set()
        self._lock = threading.Lock()

    def request_approval(
        self,
        command: str,
        is_dangerous: bool = False
    ) -> str:
        """
        Create a new approval request.
        Returns request_id.
        """
        ...

    def wait_for_response(
        self,
        request_id: str,
        timeout_seconds: int = 300
    ) -> ApprovalDecision:
        """
        Block until user responds or timeout.
        Returns: "allow_session", "allow_permanent", "deny", "timeout"
        """
        ...

    def respond(
        self,
        request_id: str,
        decision: ApprovalDecision
    ):
        """
        Called by UI/CLI to respond to a request.
        """
        ...
```

### File Locking for Persistence

When user chooses "Permanent", append to YAML with exclusive file lock:

```python
import fcntl  # Unix
import msvcrt  # Windows

def persist_command(project_dir: Path, command: str, description: str = None):
    """
    Atomically append command to project YAML.
    Uses platform-specific file locking.
    """
    config_path = project_dir / ".autocoder" / "allowed_commands.yaml"

    # Ensure file exists
    if not config_path.exists():
        config_path.write_text("version: 1\ncommands: []\n")

    with open(config_path, "r+") as f:
        # Acquire exclusive lock
        if sys.platform == "win32":
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        try:
            # Load current config
            config = yaml.safe_load(f) or {"version": 1, "commands": []}

            # Add new command
            new_entry = {"name": command}
            if description:
                new_entry["description"] = description

            config.setdefault("commands", []).append(new_entry)

            # Validate doesn't exceed 50 commands
            if len(config["commands"]) > 50:
                raise ValueError("Cannot add command: 50 command limit reached")

            # Write back
            f.seek(0)
            f.truncate()
            yaml.dump(config, f, default_flow_style=False)

        finally:
            # Release lock
            if sys.platform == "win32":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

---

## Implementation Checklist

### Core Security Module

- [ ] Create `ApprovalManager` class in `security.py`
  - [ ] Thread-safe pending request storage
  - [ ] Session-only allowed commands set
  - [ ] Timeout handling with threading.Timer
  - [ ] Request/response API

- [ ] Modify `bash_security_hook()` to support pending state
  - [ ] Check if command needs approval
  - [ ] Create approval request
  - [ ] Wait for response (with timeout)
  - [ ] Return appropriate decision

- [ ] Implement `persist_command()` with file locking
  - [ ] Platform-specific locking (fcntl/msvcrt)
  - [ ] Atomic YAML append
  - [ ] 50 command limit validation
  - [ ] Auto-generate description if not provided

- [ ] Add `is_dangerous_command()` helper
  - [ ] Check against DANGEROUS_COMMANDS set
  - [ ] Return emphatic warning text

- [ ] Update DANGEROUS_COMMANDS set
  - [ ] Move from hardcoded blocklist to dangerous list
  - [ ] Commands: aws, gcloud, az, kubectl, docker-compose
  - [ ] Keep sudo, dd, etc. in BLOCKED_COMMANDS (never allowed)

### CLI Approval Interface

- [ ] Create `approval_tui.py` module
  - [ ] Use Rich library for TUI
  - [ ] Overlay design (doesn't clear screen)
  - [ ] Keyboard input handling (S/P/D keys)
  - [ ] Timeout display (countdown timer)
  - [ ] Different layouts for normal vs dangerous commands

- [ ] Integrate with agent.py
  - [ ] Detect if running in CLI mode (not UI)
  - [ ] Pass approval callback to client
  - [ ] Handle approval responses

- [ ] Add `rich` to requirements.txt
  - [ ] Version: `rich>=13.0.0`

### React UI Components

- [ ] Create `ApprovalBanner.tsx` component
  - [ ] Banner at top of screen
  - [ ] Queue multiple requests
  - [ ] Session/Permanent/Deny buttons
  - [ ] Countdown timer display
  - [ ] Dangerous command warning variant

- [ ] Update `useWebSocket.ts` hook
  - [ ] Handle `approval_request` message type
  - [ ] Send `approval_response` message
  - [ ] Queue management for multiple requests

- [ ] Update WebSocket message types in `types.ts`
  ```typescript
  type ApprovalRequest = {
    request_id: string;
    command: string;
    is_dangerous: boolean;
    timeout_seconds: number;
    warning_text?: string;
  };

  type ApprovalResponse = {
    request_id: string;
    decision: "session" | "permanent" | "deny";
  };
  ```

### Backend WebSocket Integration

- [ ] Update `server/routers/agent.py`
  - [ ] Add `approval_request` message sender
  - [ ] Add `approval_response` message handler
  - [ ] Wire to ApprovalManager

- [ ] Thread-safe WebSocket message queue
  - [ ] Handle approval requests from agent thread
  - [ ] Handle approval responses from WebSocket thread

### MCP Tool for Agent Introspection

- [ ] Add `list_allowed_commands` tool to feature MCP
  - [ ] Returns current allowed commands
  - [ ] Indicates which are from project/org/global
  - [ ] Shows if approval is available
  - [ ] Agent can proactively query before trying commands

- [ ] Tool response format:
  ```python
  {
    "commands": [
      {"name": "swift", "source": "project"},
      {"name": "npm", "source": "global"},
      {"name": "jq", "source": "org"}
    ],
    "blocked_count": 15,
    "can_request_approval": True,
    "approval_timeout_minutes": 5
  }
  ```

### Configuration

- [ ] Add approval settings to org config
  - [ ] `approval_timeout_minutes` (default: 5)
  - [ ] `approval_enabled` (default: true)
  - [ ] `dangerous_command_requires_confirmation` (default: true)

- [ ] Validate org config settings
  - [ ] Timeout must be 1-30 minutes
  - [ ] Boolean flags properly typed

### Testing

- [ ] Unit tests for ApprovalManager
  - [ ] Request creation
  - [ ] Response handling
  - [ ] Timeout behavior
  - [ ] Thread safety

- [ ] Unit tests for file locking
  - [ ] Concurrent append operations
  - [ ] Platform-specific locking
  - [ ] Error handling

- [ ] Integration tests for approval flow
  - [ ] CLI approval (mocked input)
  - [ ] WebSocket approval (mocked messages)
  - [ ] Session vs permanent vs deny
  - [ ] Timeout scenarios

- [ ] UI component tests
  - [ ] ApprovalBanner rendering
  - [ ] Queue management
  - [ ] Button interactions
  - [ ] Timer countdown

### Documentation

- [ ] Update `CLAUDE.md`
  - [ ] Document approval flow
  - [ ] Update security model section
  - [ ] Add Phase 3 to architecture

- [ ] Update `examples/README.md`
  - [ ] Add mid-session approval examples
  - [ ] Document timeout configuration
  - [ ] Troubleshooting approval issues

- [ ] Create user guide for approvals
  - [ ] When/why to use session vs permanent
  - [ ] How to handle dangerous commands
  - [ ] Keyboard shortcuts for CLI

---

## Detailed Implementation Guide

### Step 1: Core ApprovalManager (2-3 hours)

**File:** `security.py`

```python
from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Dict, Set, Optional
import uuid

class ApprovalDecision(Enum):
    ALLOW_SESSION = "session"
    ALLOW_PERMANENT = "permanent"
    DENY = "deny"
    TIMEOUT = "timeout"

@dataclass
class PendingRequest:
    request_id: str
    command: str
    is_dangerous: bool
    timestamp: float
    response_event: threading.Event
    decision: Optional[ApprovalDecision] = None

class ApprovalManager:
    """
    Singleton manager for approval requests.
    Thread-safe for concurrent access from agent and UI.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pending: Dict[str, PendingRequest] = {}
        self._session_allowed: Set[str] = set()
        self._state_lock = threading.Lock()
        self._initialized = True

    def request_approval(
        self,
        command: str,
        is_dangerous: bool = False,
        timeout_seconds: int = 300
    ) -> str:
        """
        Create a new approval request.

        Args:
            command: The command needing approval
            is_dangerous: True if command is in DANGEROUS_COMMANDS
            timeout_seconds: How long to wait before auto-deny

        Returns:
            request_id to use for waiting/responding
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"

        with self._state_lock:
            request = PendingRequest(
                request_id=request_id,
                command=command,
                is_dangerous=is_dangerous,
                timestamp=time.time(),
                response_event=threading.Event()
            )
            self._pending[request_id] = request

        # Start timeout timer
        timer = threading.Timer(
            timeout_seconds,
            self._handle_timeout,
            args=[request_id]
        )
        timer.daemon = True
        timer.start()

        # Emit notification (CLI or WebSocket)
        self._emit_approval_request(request)

        return request_id

    def wait_for_response(
        self,
        request_id: str,
        timeout_seconds: int = 300
    ) -> ApprovalDecision:
        """
        Block until user responds or timeout.

        Returns:
            ApprovalDecision (session/permanent/deny/timeout)
        """
        with self._state_lock:
            request = self._pending.get(request_id)
            if not request:
                return ApprovalDecision.DENY

        # Wait for response event
        request.response_event.wait(timeout=timeout_seconds)

        with self._state_lock:
            request = self._pending.get(request_id)
            if not request or not request.decision:
                return ApprovalDecision.TIMEOUT

            decision = request.decision

            # Handle permanent approval
            if decision == ApprovalDecision.ALLOW_PERMANENT:
                # This will be handled by caller (needs project_dir)
                pass
            elif decision == ApprovalDecision.ALLOW_SESSION:
                self._session_allowed.add(request.command)

            # Clean up
            del self._pending[request_id]

            return decision

    def respond(
        self,
        request_id: str,
        decision: ApprovalDecision
    ):
        """
        Called by UI/CLI to respond to a request.
        """
        with self._state_lock:
            request = self._pending.get(request_id)
            if not request:
                return

            request.decision = decision
            request.response_event.set()

    def is_session_allowed(self, command: str) -> bool:
        """Check if command was approved for this session."""
        with self._state_lock:
            return command in self._session_allowed

    def _handle_timeout(self, request_id: str):
        """Called by timer thread when request times out."""
        self.respond(request_id, ApprovalDecision.TIMEOUT)

    def _emit_approval_request(self, request: PendingRequest):
        """
        Emit approval request to CLI or WebSocket.
        To be implemented based on execution mode.
        """
        # This is called by approval_callback in client.py
        pass

# Global singleton instance
_approval_manager = ApprovalManager()

def get_approval_manager() -> ApprovalManager:
    """Get the global ApprovalManager singleton."""
    return _approval_manager
```

### Step 2: Modify bash_security_hook (1 hour)

**File:** `security.py`

```python
async def bash_security_hook(input_data, tool_use_id=None, context=None):
    """
    Pre-tool-use hook that validates bash commands.

    Phase 3: Supports mid-session approval for unknown commands.
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    # Extract commands
    commands = extract_commands(command)
    if not commands:
        return {
            "decision": "block",
            "reason": f"Could not parse command: {command}",
        }

    # Get project directory and effective commands
    project_dir = None
    if context and isinstance(context, dict):
        project_dir_str = context.get("project_dir")
        if project_dir_str:
            project_dir = Path(project_dir_str)

    allowed_commands, blocked_commands = get_effective_commands(project_dir)
    segments = split_command_segments(command)

    # Check each command
    for cmd in commands:
        # Check blocklist (highest priority)
        if cmd in blocked_commands:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is blocked and cannot be approved.",
            }

        # Check if allowed (allowlist or session)
        approval_mgr = get_approval_manager()
        if is_command_allowed(cmd, allowed_commands) or approval_mgr.is_session_allowed(cmd):
            # Additional validation for sensitive commands
            if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
                cmd_segment = get_command_for_validation(cmd, segments)
                # ... existing validation code ...
            continue

        # PHASE 3: Request approval
        is_dangerous = cmd in DANGEROUS_COMMANDS
        request_id = approval_mgr.request_approval(
            command=cmd,
            is_dangerous=is_dangerous,
            timeout_seconds=300  # TODO: Get from org config
        )

        decision = approval_mgr.wait_for_response(request_id)

        if decision == ApprovalDecision.DENY:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' was denied.",
            }
        elif decision == ApprovalDecision.TIMEOUT:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' was denied (approval timeout after 5 minutes).",
            }
        elif decision == ApprovalDecision.ALLOW_PERMANENT:
            # Persist to YAML
            if project_dir:
                try:
                    persist_command(
                        project_dir,
                        cmd,
                        description=f"Added via mid-session approval"
                    )
                except Exception as e:
                    # If persist fails, still allow for session
                    print(f"Warning: Could not save to config: {e}")
        # If ALLOW_SESSION, already added to session set by wait_for_response

    return {}  # Allow
```

### Step 3: CLI Approval Interface (3-4 hours)

**File:** `approval_tui.py`

```python
"""
CLI approval interface using Rich library.
Displays an overlay when approval is needed.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.live import Live
from rich.text import Text
import sys
import threading
import time

console = Console()

def show_approval_dialog(
    command: str,
    is_dangerous: bool,
    timeout_seconds: int,
    on_response: callable
):
    """
    Show approval dialog in CLI.

    Args:
        command: The command requesting approval
        is_dangerous: True if dangerous command
        timeout_seconds: Timeout in seconds
        on_response: Callback(decision: str) - "session"/"permanent"/"deny"
    """

    if is_dangerous:
        _show_dangerous_dialog(command, timeout_seconds, on_response)
    else:
        _show_normal_dialog(command, timeout_seconds, on_response)

def _show_normal_dialog(command: str, timeout_seconds: int, on_response: callable):
    """Standard approval dialog."""

    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        remaining = timeout_seconds - elapsed

        if remaining <= 0:
            on_response("deny")
            console.print("[red]⏱️  Request timed out - command denied[/red]")
            return

        # Build dialog
        content = f"""[bold yellow]⚠️  COMMAND APPROVAL REQUIRED[/bold yellow]

The agent is requesting permission to run:

  [cyan]{command}[/cyan]

This command is not in your allowed commands list.

Options:
  [green][S][/green] Allow for this [green]Session only[/green]
  [blue][P][/blue] Allow [blue]Permanently[/blue] (save to config)
  [red][D][/red] [red]Deny[/red] (default in {int(remaining)}s)

Your choice (S/P/D): """

        console.print(Panel(content, border_style="yellow", expand=False))

        # Get input with timeout
        choice = _get_input_with_timeout("", timeout=1.0)

        if choice:
            choice = choice.upper()
            if choice == "S":
                on_response("session")
                console.print("[green]✅ Allowed for this session[/green]")
                return
            elif choice == "P":
                on_response("permanent")
                console.print("[blue]✅ Saved to config permanently[/blue]")
                return
            elif choice == "D":
                on_response("deny")
                console.print("[red]❌ Command denied[/red]")
                return
            else:
                console.print("[yellow]Invalid choice. Use S, P, or D.[/yellow]")

def _show_dangerous_dialog(command: str, timeout_seconds: int, on_response: callable):
    """Emphatic dialog for dangerous commands."""

    # Determine warning text based on command
    warnings = {
        "aws": "AWS CLI can:\n  • Access production infrastructure\n  • Modify or delete cloud resources\n  • Incur significant costs",
        "gcloud": "Google Cloud CLI can:\n  • Access production GCP resources\n  • Modify or delete cloud infrastructure\n  • Incur significant costs",
        "kubectl": "Kubernetes CLI can:\n  • Access production clusters\n  • Deploy or delete workloads\n  • Disrupt running services",
    }

    cmd_name = command.split()[0]
    warning = warnings.get(cmd_name, "This command can make significant system changes.")

    content = f"""[bold red on white] ⚠️  DANGER: PRIVILEGED COMMAND REQUESTED [/bold red on white]

The agent is requesting: [red bold]{command}[/red bold]

[yellow]{warning}[/yellow]

[bold]This action could have SERIOUS consequences.[/bold]

Type [bold]CONFIRM[/bold] to allow, or press Enter to deny:"""

    console.print(Panel(content, border_style="red", expand=False))

    confirmation = Prompt.ask("", default="deny")

    if confirmation.upper() == "CONFIRM":
        # Ask session vs permanent
        choice = Prompt.ask(
            "Allow for [S]ession or [P]ermanent?",
            choices=["S", "P", "s", "p"],
            default="S"
        )
        if choice.upper() == "P":
            on_response("permanent")
            console.print("[blue]✅ Saved to config permanently[/blue]")
        else:
            on_response("session")
            console.print("[green]✅ Allowed for this session[/green]")
    else:
        on_response("deny")
        console.print("[red]❌ Command denied[/red]")

def _get_input_with_timeout(prompt: str, timeout: float) -> str:
    """
    Get input with timeout (non-blocking).
    Returns empty string if timeout.
    """
    import select

    sys.stdout.write(prompt)
    sys.stdout.flush()

    # Check if input available (Unix only, Windows needs different approach)
    if sys.platform != "win32":
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().strip()
    else:
        # Windows: use msvcrt.kbhit() and msvcrt.getch()
        import msvcrt
        start = time.time()
        chars = []
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                char = msvcrt.getch()
                if char == b'\r':  # Enter
                    return ''.join(chars)
                elif char == b'\x08':  # Backspace
                    if chars:
                        chars.pop()
                        sys.stdout.write('\b \b')
                else:
                    chars.append(char.decode('utf-8'))
                    sys.stdout.write(char.decode('utf-8'))
            time.sleep(0.01)

    return ""
```

### Step 4: React UI Components (4-5 hours)

**File:** `ui/src/components/ApprovalBanner.tsx`

```tsx
import React, { useState, useEffect } from 'react';
import { X, AlertTriangle, Clock } from 'lucide-react';

interface ApprovalRequest {
  request_id: string;
  command: string;
  is_dangerous: boolean;
  timeout_seconds: number;
  warning_text?: string;
  timestamp: number;
}

interface ApprovalBannerProps {
  requests: ApprovalRequest[];
  onRespond: (requestId: string, decision: 'session' | 'permanent' | 'deny') => void;
}

export function ApprovalBanner({ requests, onRespond }: ApprovalBannerProps) {
  const [remainingTimes, setRemainingTimes] = useState<Record<string, number>>({});

  // Update countdown timers
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const newTimes: Record<string, number> = {};

      requests.forEach(req => {
        const elapsed = (now - req.timestamp) / 1000;
        const remaining = Math.max(0, req.timeout_seconds - elapsed);
        newTimes[req.request_id] = remaining;

        // Auto-deny on timeout
        if (remaining === 0) {
          onRespond(req.request_id, 'deny');
        }
      });

      setRemainingTimes(newTimes);
    }, 100);

    return () => clearInterval(interval);
  }, [requests, onRespond]);

  if (requests.length === 0) return null;

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-100 dark:bg-amber-900 border-b-4 border-amber-500 shadow-brutal">
      <div className="max-w-7xl mx-auto px-4 py-3">
        {requests.length === 1 ? (
          <SingleRequestView
            request={requests[0]}
            remaining={remainingTimes[requests[0].request_id] || 0}
            onRespond={onRespond}
            formatTime={formatTime}
          />
        ) : (
          <MultipleRequestsView
            requests={requests}
            remainingTimes={remainingTimes}
            onRespond={onRespond}
            formatTime={formatTime}
          />
        )}
      </div>
    </div>
  );
}

function SingleRequestView({
  request,
  remaining,
  onRespond,
  formatTime,
}: {
  request: ApprovalRequest;
  remaining: number;
  onRespond: (requestId: string, decision: 'session' | 'permanent' | 'deny') => void;
  formatTime: (seconds: number) => string;
}) {
  const isDangerous = request.is_dangerous;

  return (
    <div className={`space-y-2 ${isDangerous ? 'bg-red-50 dark:bg-red-950 p-4 rounded border-2 border-red-500' : ''}`}>
      {isDangerous && (
        <div className="flex items-center gap-2 text-red-700 dark:text-red-300 font-bold">
          <AlertTriangle className="w-5 h-5" />
          DANGER: PRIVILEGED COMMAND
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold">Agent requesting permission:</span>
            <code className="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
              {request.command}
            </code>
          </div>

          {request.warning_text && (
            <p className="text-sm text-red-700 dark:text-red-300 mt-2">
              {request.warning_text}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onRespond(request.request_id, 'session')}
            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white font-bold rounded border-2 border-black shadow-brutal transition-transform hover:translate-x-[2px] hover:translate-y-[2px]"
          >
            Session Only
          </button>

          <button
            onClick={() => onRespond(request.request_id, 'permanent')}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white font-bold rounded border-2 border-black shadow-brutal transition-transform hover:translate-x-[2px] hover:translate-y-[2px]"
          >
            Save to Config
          </button>

          <button
            onClick={() => onRespond(request.request_id, 'deny')}
            className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white font-bold rounded border-2 border-black shadow-brutal transition-transform hover:translate-x-[2px] hover:translate-y-[2px]"
          >
            Deny
          </button>

          <div className="flex items-center gap-1 text-sm font-mono">
            <Clock className="w-4 h-4" />
            {formatTime(remaining)}
          </div>
        </div>
      </div>
    </div>
  );
}

function MultipleRequestsView({
  requests,
  remainingTimes,
  onRespond,
  formatTime,
}: {
  requests: ApprovalRequest[];
  remainingTimes: Record<string, number>;
  onRespond: (requestId: string, decision: 'session' | 'permanent' | 'deny') => void;
  formatTime: (seconds: number) => string;
}) {
  return (
    <div className="space-y-3">
      <div className="font-bold text-lg">
        ⚠️ {requests.length} approval requests pending
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {requests.map(req => (
          <div
            key={req.request_id}
            className="flex items-center justify-between gap-4 p-2 bg-white dark:bg-gray-800 rounded border-2 border-black"
          >
            <code className="flex-1 text-sm">
              {req.command}
            </code>

            <div className="flex items-center gap-2">
              <button
                onClick={() => onRespond(req.request_id, 'session')}
                className="px-2 py-1 text-sm bg-green-500 hover:bg-green-600 text-white font-bold rounded border border-black"
              >
                Session
              </button>

              <button
                onClick={() => onRespond(req.request_id, 'permanent')}
                className="px-2 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white font-bold rounded border border-black"
              >
                Save
              </button>

              <button
                onClick={() => onRespond(req.request_id, 'deny')}
                className="px-2 py-1 text-sm bg-red-500 hover:bg-red-600 text-white font-bold rounded border border-black"
              >
                Deny
              </button>

              <span className="text-xs font-mono">
                {formatTime(remainingTimes[req.request_id] || 0)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**File:** `ui/src/hooks/useWebSocket.ts` (add approval handling)

```typescript
// Add to message types
type ApprovalRequestMessage = {
  type: 'approval_request';
  request_id: string;
  command: string;
  is_dangerous: boolean;
  timeout_seconds: number;
  warning_text?: string;
};

// Add to useWebSocket hook
const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([]);

// In message handler
if (data.type === 'approval_request') {
  setApprovalRequests(prev => [
    ...prev,
    {
      ...data,
      timestamp: Date.now(),
    },
  ]);
}

// Approval response function
const respondToApproval = useCallback(
  (requestId: string, decision: 'session' | 'permanent' | 'deny') => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          type: 'approval_response',
          request_id: requestId,
          decision,
        })
      );
    }

    // Remove from queue
    setApprovalRequests(prev =>
      prev.filter(req => req.request_id !== requestId)
    );
  },
  []
);

return {
  // ... existing returns
  approvalRequests,
  respondToApproval,
};
```

### Step 5: Backend WebSocket (2-3 hours)

**File:** `server/routers/agent.py`

```python
# Add to WebSocket message handlers

async def handle_approval_response(websocket: WebSocket, data: dict):
    """
    Handle approval response from UI.

    Message format:
    {
        "type": "approval_response",
        "request_id": "req_abc123",
        "decision": "session" | "permanent" | "deny"
    }
    """
    request_id = data.get("request_id")
    decision = data.get("decision")

    if not request_id or not decision:
        return

    # Convert string to enum
    decision_map = {
        "session": ApprovalDecision.ALLOW_SESSION,
        "permanent": ApprovalDecision.ALLOW_PERMANENT,
        "deny": ApprovalDecision.DENY,
    }

    approval_decision = decision_map.get(decision, ApprovalDecision.DENY)

    # Respond to approval manager
    from security import get_approval_manager
    approval_mgr = get_approval_manager()
    approval_mgr.respond(request_id, approval_decision)


async def send_approval_request(
    websocket: WebSocket,
    request_id: str,
    command: str,
    is_dangerous: bool,
    timeout_seconds: int,
    warning_text: str = None
):
    """
    Send approval request to UI via WebSocket.
    """
    await websocket.send_json({
        "type": "approval_request",
        "request_id": request_id,
        "command": command,
        "is_dangerous": is_dangerous,
        "timeout_seconds": timeout_seconds,
        "warning_text": warning_text,
    })
```

---

## Testing Strategy

### Unit Tests

**File:** `test_approval.py`

```python
def test_approval_manager_request():
    """Test creating approval request."""
    mgr = ApprovalManager()
    request_id = mgr.request_approval("swift", is_dangerous=False)
    assert request_id.startswith("req_")

def test_approval_manager_respond():
    """Test responding to approval."""
    mgr = ApprovalManager()
    request_id = mgr.request_approval("swift", is_dangerous=False, timeout_seconds=1)

    # Respond in separate thread
    import threading
    def respond():
        time.sleep(0.1)
        mgr.respond(request_id, ApprovalDecision.ALLOW_SESSION)

    t = threading.Thread(target=respond)
    t.start()

    decision = mgr.wait_for_response(request_id, timeout_seconds=2)
    assert decision == ApprovalDecision.ALLOW_SESSION
    t.join()

def test_approval_timeout():
    """Test approval timeout."""
    mgr = ApprovalManager()
    request_id = mgr.request_approval("swift", is_dangerous=False, timeout_seconds=1)

    # Don't respond, let it timeout
    decision = mgr.wait_for_response(request_id, timeout_seconds=2)
    assert decision == ApprovalDecision.TIMEOUT

def test_session_allowed():
    """Test session-allowed commands."""
    mgr = ApprovalManager()
    assert not mgr.is_session_allowed("swift")

    # Approve for session
    request_id = mgr.request_approval("swift", is_dangerous=False, timeout_seconds=1)
    mgr.respond(request_id, ApprovalDecision.ALLOW_SESSION)
    mgr.wait_for_response(request_id)

    assert mgr.is_session_allowed("swift")
```

### Integration Tests

**File:** `test_security_integration.py` (add Phase 3 tests)

```python
def test_approval_flow_session():
    """Test mid-session approval with session-only."""
    # Create project with no config
    # Mock approval response: session
    # Try command → should be allowed
    # Try same command again → should still be allowed (session)
    pass

def test_approval_flow_permanent():
    """Test mid-session approval with permanent save."""
    # Create project with empty config
    # Mock approval response: permanent
    # Try command → should be allowed
    # Check YAML file → command should be added
    # Create new session → command should still be allowed
    pass

def test_approval_flow_deny():
    """Test mid-session approval denial."""
    # Create project
    # Mock approval response: deny
    # Try command → should be blocked
    pass

def test_approval_timeout():
    """Test approval timeout auto-deny."""
    # Create project
    # Don't respond to approval
    # Wait for timeout
    # Command should be blocked with timeout message
    pass

def test_concurrent_approvals():
    """Test multiple simultaneous approval requests."""
    # Create project
    # Try 3 commands at once
    # All should queue
    # Respond to each individually
    # Verify all handled correctly
    pass
```

### Manual Testing Checklist

- [ ] CLI mode: Request approval for unknown command
- [ ] CLI mode: Press S → command works this session
- [ ] CLI mode: Press P → command saved to YAML
- [ ] CLI mode: Press D → command denied
- [ ] CLI mode: Wait 5 minutes → timeout, command denied
- [ ] CLI mode: Dangerous command shows emphatic warning
- [ ] UI mode: Banner appears at top
- [ ] UI mode: Click "Session Only" → command works
- [ ] UI mode: Click "Save to Config" → YAML updated
- [ ] UI mode: Click "Deny" → command blocked
- [ ] UI mode: Multiple requests → all shown in queue
- [ ] UI mode: Countdown timer updates
- [ ] Concurrent access: Multiple agents, file locking works
- [ ] Config validation: 50 command limit enforced
- [ ] Session persistence: Session commands available until restart
- [ ] Permanent persistence: Saved commands available after restart

---

## Security Considerations

### 1. Hardcoded Blocklist is Final

**NEVER** allow approval for hardcoded blocklist commands:
- `sudo`, `su`, `doas`
- `dd`, `mkfs`, `fdisk`
- `shutdown`, `reboot`, `halt`
- etc.

These bypass approval entirely - immediate block.

### 2. Org Blocklist Cannot Be Overridden

If org config blocks a command, approval is not even requested.

### 3. Dangerous Commands Require Extra Confirmation

Commands like `aws`, `kubectl` should:
- Show emphatic warning
- Require typing "CONFIRM" (not just button click)
- Explain potential consequences

### 4. Timeout is Critical

Default 5-minute timeout prevents:
- Stale approval requests
- Forgotten dialogs
- Unattended approval accumulation

### 5. Session vs Permanent

**Session-only:**
- ✅ Safe for experimentation
- ✅ Doesn't persist across restarts
- ✅ Good for one-off commands

**Permanent:**
- ⚠️ Saved to YAML forever
- ⚠️ Available to all future sessions
- ⚠️ User should understand impact

### 6. File Locking is Essential

Multiple agents or concurrent modifications require:
- Exclusive file locks (fcntl/msvcrt)
- Atomic read-modify-write
- Proper error handling

Without locking → race conditions → corrupted YAML

### 7. Audit Trail

Consider logging all approval decisions:
```
[2026-01-22 10:30:45] User approved 'swift' (session-only)
[2026-01-22 10:32:12] User approved 'xcodebuild' (permanent)
[2026-01-22 10:35:00] Approval timeout for 'wget' (denied)
```

---

## Future Enhancements

Beyond Phase 3 scope, but possible extensions:

### 1. Approval Profiles

Pre-defined approval sets:
```yaml
profiles:
  ios-dev:
    - swift*
    - xcodebuild
    - xcrun

  rust-dev:
    - cargo
    - rustc
    - clippy
```

User can activate profile with one click.

### 2. Smart Recommendations

Agent AI suggests commands to add based on:
- Project type detection (iOS, Rust, Python)
- Frequently denied commands
- Similar projects

### 3. Approval History

Show past approvals in UI:
- What was approved
- When
- Session vs permanent
- By which agent

### 4. Bulk Approve/Deny

When agent requests multiple commands:
- "Approve all for session"
- "Save all to config"
- "Deny all"

### 5. Temporary Time-Based Approval

"Allow for next 1 hour" option:
- Not session-only (survives restarts)
- Not permanent (expires)
- Good for contractors/temporary access

### 6. Command Arguments Validation

Phase 1 has placeholder, could be fully implemented:
```yaml
- name: rm
  description: Remove files
  args_whitelist:
    - "-rf ./build/*"
    - "-rf ./dist/*"
```

### 7. Remote Approval

For team environments:
- Agent requests approval
- Notification sent to team lead
- Lead approves/denies remotely
- Agent proceeds based on decision

---

## Questions for Implementer

Before starting Phase 3, consider:

1. **CLI vs UI priority?**
   - Implement CLI first (simpler)?
   - Or UI first (more users)?

2. **Approval persistence format?**
   - Separate log file for audit trail?
   - Just YAML modifications?

3. **Dangerous commands list?**
   - Current list correct?
   - Need org-specific dangerous commands?

4. **Timeout default?**
   - 5 minutes reasonable?
   - Different for dangerous commands?

5. **UI placement?**
   - Top banner (blocks view)?
   - Modal dialog (more prominent)?
   - Sidebar notification?

6. **Multiple agents?**
   - How to attribute approvals?
   - Show which agent requested?

7. **Undo permanent approvals?**
   - UI for removing saved commands?
   - Or manual YAML editing only?

---

## Success Criteria

Phase 3 is complete when:

- ✅ Agent can request approval for unknown commands
- ✅ CLI shows Rich TUI dialog with countdown
- ✅ UI shows React banner with buttons
- ✅ Session-only approval works (in-memory)
- ✅ Permanent approval persists to YAML
- ✅ Dangerous commands show emphatic warnings
- ✅ Timeout auto-denies after configured time
- ✅ Multiple requests can queue
- ✅ File locking prevents corruption
- ✅ All tests pass (unit + integration)
- ✅ Documentation updated
- ✅ Backward compatible (Phase 1/2 still work)

---

## Estimated Timeline

| Task | Time | Dependencies |
|------|------|--------------|
| ApprovalManager core | 2-3 hours | None |
| Modify bash_security_hook | 1 hour | ApprovalManager |
| File locking + persist | 1-2 hours | None |
| CLI approval TUI | 3-4 hours | ApprovalManager |
| React components | 4-5 hours | None |
| WebSocket integration | 2-3 hours | React components |
| Unit tests | 3-4 hours | All core features |
| Integration tests | 2-3 hours | Full implementation |
| Documentation | 2-3 hours | None |
| Manual testing + polish | 4-6 hours | Full implementation |

**Total: 24-36 hours (3-4.5 days)**

---

## Getting Started

To implement Phase 3:

1. **Read this document fully**
2. **Review Phase 1 & 2 code** (`security.py`, `client.py`)
3. **Run existing tests** to understand current behavior
4. **Start with ApprovalManager** (core functionality)
5. **Add file locking** (critical for safety)
6. **Choose CLI or UI** (whichever you're more comfortable with)
7. **Write tests as you go** (don't leave for end)
8. **Manual test frequently** (approval UX needs polish)

Good luck! 🚀

---

**Document Version:** 1.0
**Last Updated:** 2026-01-22
**Author:** Phase 1 & 2 implementation team
**Status:** Ready for implementation
