#!/usr/bin/env python3
"""
AutoCoder UI Launcher
=====================

Automated launcher that handles all setup:
1. Creates/activates Python virtual environment
2. Installs Python dependencies
3. Checks for Node.js
4. Installs npm dependencies
5. Builds React frontend (if needed)
6. Starts FastAPI server
7. Opens browser to the UI

Usage:
    python start_ui.py [--dev] [--host HOST] [--port PORT]

Options:
    --dev           Run in development mode with Vite hot reload
    --host HOST     Host to bind to (default: 127.0.0.1)
                    Use 0.0.0.0 for remote access (security warning will be shown)
    --port PORT     Port to bind to (default: 8888)
"""

import argparse
import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Fix Windows asyncio subprocess support BEFORE anything else runs
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

ROOT = Path(__file__).parent.absolute()
VENV_DIR = ROOT / "venv"
UI_DIR = ROOT / "ui"


def print_step(step: int, total: int, message: str) -> None:
    """Print a formatted step message."""
    print(f"\n[{step}/{total}] {message}")
    print("-" * 50)


def find_available_port(start: int = 8888, max_attempts: int = 10) -> int:
    """Find an available port starting from the given port."""
    for port in range(start, start + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found in range {start}-{start + max_attempts}")


def get_venv_python() -> Path:
    """Get the path to the virtual environment Python executable."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(cmd: list, cwd: Path | None = None, check: bool = True) -> bool:
    """Run a command and return success status."""
    try:
        subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def setup_python_venv() -> bool:
    """Create Python virtual environment if it doesn't exist."""
    if VENV_DIR.exists() and get_venv_python().exists():
        print("  Virtual environment already exists")
        return True

    print("  Creating virtual environment...")
    return run_command([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_python_deps() -> bool:
    """Install Python dependencies."""
    venv_python = get_venv_python()
    requirements = ROOT / "requirements.txt"

    if not requirements.exists():
        print("  ERROR: requirements.txt not found")
        return False

    print("  Installing Python dependencies...")
    return run_command([
        str(venv_python), "-m", "pip", "install",
        "-q", "--upgrade", "pip"
    ]) and run_command([
        str(venv_python), "-m", "pip", "install",
        "-q", "-r", str(requirements)
    ])


def check_node() -> bool:
    """Check if Node.js is installed."""
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node:
        print("  ERROR: Node.js not found")
        print("  Please install Node.js from https://nodejs.org")
        return False

    if not npm:
        print("  ERROR: npm not found")
        print("  Please install Node.js from https://nodejs.org")
        return False

    # Get version
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True
        )
        print(f"  Node.js version: {result.stdout.strip()}")
    except Exception:
        pass

    return True


def install_npm_deps() -> bool:
    """Install npm dependencies if node_modules doesn't exist or is stale."""
    node_modules = UI_DIR / "node_modules"
    package_json = UI_DIR / "package.json"
    package_lock = UI_DIR / "package-lock.json"

    # Check if npm install is needed
    needs_install = False

    if not node_modules.exists():
        needs_install = True
    elif package_json.exists():
        # If package.json or package-lock.json is newer than node_modules, reinstall
        node_modules_mtime = node_modules.stat().st_mtime
        if package_json.stat().st_mtime > node_modules_mtime:
            needs_install = True
        elif package_lock.exists() and package_lock.stat().st_mtime > node_modules_mtime:
            needs_install = True

    if not needs_install:
        print("  npm dependencies already installed")
        return True

    print("  Installing npm dependencies (this may take a few minutes)...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return run_command([npm_cmd, "install"], cwd=UI_DIR)


def build_frontend() -> bool:
    """Build the React frontend if dist doesn't exist or is stale.

    Staleness is determined by comparing modification times of:
    - Source files in ui/src/
    - Config files (package.json, vite.config.ts, etc.)
    Against the newest file in ui/dist/

    Includes a 2-second tolerance for FAT32 filesystem compatibility.
    """
    dist_dir = UI_DIR / "dist"
    src_dir = UI_DIR / "src"

    # FAT32 has 2-second timestamp precision, so we add tolerance to avoid
    # false negatives when projects are on USB drives or SD cards
    TIMESTAMP_TOLERANCE = 2

    # Config files that should trigger a rebuild when changed
    CONFIG_FILES = [
        "package.json",
        "package-lock.json",
        "vite.config.ts",
        "tailwind.config.ts",
        "tsconfig.json",
        "tsconfig.node.json",
        "postcss.config.js",
        "index.html",
    ]

    # Check if build is needed
    needs_build = False
    trigger_file = None

    if not dist_dir.exists():
        needs_build = True
        trigger_file = "dist/ directory missing"
    elif src_dir.exists():
        # Find the newest file in dist/ directory
        newest_dist_mtime = 0
        for dist_file in dist_dir.rglob("*"):
            try:
                if dist_file.is_file():
                    file_mtime = dist_file.stat().st_mtime
                    if file_mtime > newest_dist_mtime:
                        newest_dist_mtime = file_mtime
            except (FileNotFoundError, PermissionError, OSError):
                # File was deleted or became inaccessible during iteration
                continue

        if newest_dist_mtime > 0:
            # Check config files first (these always require rebuild)
            for config_name in CONFIG_FILES:
                config_path = UI_DIR / config_name
                try:
                    if config_path.exists():
                        if config_path.stat().st_mtime > newest_dist_mtime + TIMESTAMP_TOLERANCE:
                            needs_build = True
                            trigger_file = config_name
                            break
                except (FileNotFoundError, PermissionError, OSError):
                    continue

            # Check source files if no config triggered rebuild
            if not needs_build:
                for src_file in src_dir.rglob("*"):
                    try:
                        if src_file.is_file():
                            if src_file.stat().st_mtime > newest_dist_mtime + TIMESTAMP_TOLERANCE:
                                needs_build = True
                                trigger_file = str(src_file.relative_to(UI_DIR))
                                break
                    except (FileNotFoundError, PermissionError, OSError):
                        # File was deleted or became inaccessible during iteration
                        continue
        else:
            # No files found in dist, need to rebuild
            needs_build = True
            trigger_file = "dist/ directory is empty"

    if not needs_build:
        print("  Frontend already built (up to date)")
        return True

    if trigger_file:
        print(f"  Rebuild triggered by: {trigger_file}")
    print("  Building React frontend...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return run_command([npm_cmd, "run", "build"], cwd=UI_DIR)


def start_dev_server(port: int, host: str = "127.0.0.1") -> tuple:
    """Start both Vite and FastAPI in development mode."""
    venv_python = get_venv_python()

    print("\n  Starting development servers...")
    print(f"  - FastAPI backend: http://{host}:{port}")
    print("  - Vite frontend:   http://127.0.0.1:5173")

    # Set environment for remote access if needed
    env = os.environ.copy()
    if host != "127.0.0.1":
        env["AUTOCODER_ALLOW_REMOTE"] = "1"

    # Start FastAPI
    backend = subprocess.Popen([
        str(venv_python), "-m", "uvicorn",
        "server.main:app",
        "--host", host,
        "--port", str(port),
        "--reload"
    ], cwd=str(ROOT), env=env)

    # Start Vite with API port env var for proxy configuration
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    vite_env = env.copy()
    vite_env["VITE_API_PORT"] = str(port)
    frontend = subprocess.Popen([
        npm_cmd, "run", "dev"
    ], cwd=str(UI_DIR), env=vite_env)

    return backend, frontend


def start_production_server(port: int, host: str = "127.0.0.1"):
    """Start FastAPI server in production mode."""
    venv_python = get_venv_python()

    print(f"\n  Starting server at http://{host}:{port}")

    env = os.environ.copy()

    # Enable remote access in server if not localhost
    if host != "127.0.0.1":
        env["AUTOCODER_ALLOW_REMOTE"] = "1"

    # NOTE: --reload is NOT used because on Windows it breaks asyncio subprocess
    # support (uvicorn's reload worker doesn't inherit the ProactorEventLoop policy).
    # This affects Claude SDK which uses asyncio.create_subprocess_exec.
    # For development with hot reload, use: python start_ui.py --dev
    return subprocess.Popen([
        str(venv_python), "-m", "uvicorn",
        "server.main:app",
        "--host", host,
        "--port", str(port),
    ], cwd=str(ROOT), env=env)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AutoCoder UI Launcher")
    parser.add_argument("--dev", action="store_true", help="Run in development mode with Vite hot reload")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: auto-detect from 8888)")
    args = parser.parse_args()

    dev_mode = args.dev
    host = args.host

    # Security warning for remote access
    if host != "127.0.0.1":
        print("\n" + "!" * 50)
        print("  SECURITY WARNING")
        print("!" * 50)
        print(f"  Remote access enabled on host: {host}")
        print("  The AutoCoder UI will be accessible from other machines.")
        print("  Ensure you understand the security implications:")
        print("  - The agent has file system access to project directories")
        print("  - The API can start/stop agents and modify files")
        print("  - Consider using a firewall or VPN for protection")
        print("!" * 50 + "\n")

    print("=" * 50)
    print("  AutoCoder UI Setup")
    print("=" * 50)

    total_steps = 6 if not dev_mode else 5

    # Step 1: Python venv
    print_step(1, total_steps, "Setting up Python environment")
    if not setup_python_venv():
        print("ERROR: Failed to create virtual environment")
        sys.exit(1)

    # Step 2: Python dependencies
    print_step(2, total_steps, "Installing Python dependencies")
    if not install_python_deps():
        print("ERROR: Failed to install Python dependencies")
        sys.exit(1)

    # Load environment variables now that dotenv is installed
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass  # dotenv is optional for basic functionality

    # Step 3: Check Node.js
    print_step(3, total_steps, "Checking Node.js")
    if not check_node():
        sys.exit(1)

    # Step 4: npm dependencies
    print_step(4, total_steps, "Installing npm dependencies")
    if not install_npm_deps():
        print("ERROR: Failed to install npm dependencies")
        sys.exit(1)

    # Step 5: Build frontend (production only)
    if not dev_mode:
        print_step(5, total_steps, "Building frontend")
        if not build_frontend():
            print("ERROR: Failed to build frontend")
            sys.exit(1)

    # Step 6: Start server
    step = 5 if dev_mode else 6
    print_step(step, total_steps, "Starting server")

    port = args.port if args.port else find_available_port()

    try:
        if dev_mode:
            backend, frontend = start_dev_server(port, host)

            # Open browser to Vite dev server (always localhost for Vite)
            time.sleep(3)
            webbrowser.open("http://127.0.0.1:5173")

            print("\n" + "=" * 50)
            print("  Development mode active")
            if host != "127.0.0.1":
                print(f"  Backend accessible at: http://{host}:{port}")
            print("  Press Ctrl+C to stop")
            print("=" * 50)

            try:
                # Wait for either process to exit
                while backend.poll() is None and frontend.poll() is None:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\nShutting down...")
            finally:
                backend.terminate()
                frontend.terminate()
                backend.wait()
                frontend.wait()
        else:
            server = start_production_server(port, host)

            # Open browser (only if localhost)
            time.sleep(2)
            if host == "127.0.0.1":
                webbrowser.open(f"http://127.0.0.1:{port}")

            print("\n" + "=" * 50)
            print(f"  Server running at http://{host}:{port}")
            print("  Press Ctrl+C to stop")
            print("=" * 50)

            try:
                server.wait()
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                server.terminate()
                server.wait()

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
