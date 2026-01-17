"""
FastAPI Backend Server
======================

Web UI server for the Autonomous Coding Agent.
Provides REST API and WebSocket endpoints for project management,
feature tracking, and agent control.
"""

import contextlib
import os
import shutil
import sys
import threading
import time
import webbrowser
import uvicorn
from pathlib import Path

from autocoder.core.port_config import get_ui_port
from autocoder.server.server_lock import ServerLock


def start_server(host: str = "127.0.0.1", port: int | None = None, reload: bool = False) -> None:
    """
    Start the AutoCoder web UI server.

    Args:
        host: Host to bind to (default: 127.0.0.1 for security)
        port: Port to bind to (default: AUTOCODER_UI_PORT or 8888)
        reload: Enable auto-reload for development (default: False)
    """
    if port is None:
        port = get_ui_port()
    use_colors_env = os.environ.get("AUTOCODER_UVICORN_COLORS", "").strip().lower()
    if use_colors_env:
        use_colors = use_colors_env in ("1", "true", "yes", "on")
    else:
        # Default: disable ANSI colors on Windows or when output is non-interactive.
        if os.name == "nt" or not sys.stderr.isatty():
            use_colors = False
        else:
            use_colors = None
    def _bool_env(name: str, default: bool = False) -> bool:
        raw = str(os.environ.get(name, "")).strip().lower()
        if not raw:
            return default
        return raw not in ("0", "false", "no", "off")

    def _print_ui_banner() -> None:
        if not _bool_env("AUTOCODER_UI_BANNER", True):
            return
        line = "=" * 36
        print("\n" + line)
        print("  AUTOCODER // WEB UI")
        print("  Modded by Gabi (Booplex)")
        print(line)

    def _print_boot_checklist() -> None:
        if not _bool_env("AUTOCODER_UI_BANNER", True):
            return
        def mark(ok: bool) -> str:
            return "✅" if ok else "⚠️"

        cli_command = (os.environ.get("AUTOCODER_CLI_COMMAND") or os.environ.get("CLI_COMMAND") or "claude").strip()
        claude_ok = shutil.which(cli_command) is not None
        node_ok = shutil.which("node") is not None
        npm_ok = shutil.which("npm") is not None
        try:
            from autocoder.server.main import UI_DIST_DIR
            ui_ok = bool(UI_DIST_DIR and UI_DIST_DIR.exists())
        except Exception:
            ui_ok = False
        if os.name == "nt":
            try:
                from autocoder.server.services import terminal_manager
                winpty_ok = bool(getattr(terminal_manager, "WINPTY_AVAILABLE", False))
            except Exception:
                winpty_ok = False
        else:
            winpty_ok = True

        print("\nBoot Checklist")
        print(f"  {mark(claude_ok)} Claude CLI ({cli_command})")
        print(f"  {mark(node_ok)} Node")
        print(f"  {mark(npm_ok)} npm")
        print(f"  {mark(ui_ok)} UI build")
        if os.name == "nt":
            print(f"  {mark(winpty_ok)} Windows terminals (pywinpty)")
        print(f"  ✅ UI: http://{host}:{port}/")
        print("  Tip: set AUTOCODER_OPEN_UI=0 to disable auto-open\n")

    disable_lock = _bool_env("AUTOCODER_DISABLE_UI_LOCK", False)

    def should_open_browser() -> bool:
        raw = str(os.environ.get("AUTOCODER_OPEN_UI", "")).strip().lower()
        if raw:
            return raw not in ("0", "false", "no", "off")
        return True

    def open_browser_later() -> None:
        if host not in ("127.0.0.1", "localhost"):
            return
        if not should_open_browser():
            return
        try:
            delay = float(os.environ.get("AUTOCODER_OPEN_UI_DELAY_S", "1.0"))
        except ValueError:
            delay = 1.0
        url = f"http://{host}:{port}/"

        def _worker() -> None:
            time.sleep(max(0.0, delay))
            with contextlib.suppress(Exception):
                webbrowser.open(url, new=2)

        threading.Thread(target=_worker, daemon=True).start()
    _print_ui_banner()
    _print_boot_checklist()

    if disable_lock:
        open_browser_later()
        uvicorn.run(
            "autocoder.server.main:app",
            host=host,
            port=port,
            reload=reload,
            use_colors=use_colors,
        )
        return

    with ServerLock(port):
        open_browser_later()
        uvicorn.run(
            "autocoder.server.main:app",
            host=host,
            port=port,
            reload=reload,
            use_colors=use_colors,
        )


__all__ = ["start_server"]
