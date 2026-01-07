#!/usr/bin/env python3
"""
Autonomous Coder UI Launcher
=============================

Automated launcher that handles all setup:
1. Creates/activates Python virtual environment
2. Installs Python dependencies
3. Checks for Node.js
4. Installs npm dependencies
5. Builds React frontend (if needed)
6. Starts FastAPI server
7. Opens browser to the UI

Usage:
    python start_ui.py [--dev]

Options:
    --dev    Run in development mode with Vite hot reload
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).parent.absolute()

# Load environment variables from .env file
# This ensures env vars like PROGRESS_N8N_WEBHOOK_URL are available to subprocesses
load_dotenv(ROOT / ".env")
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
    """Install npm dependencies if node_modules doesn't exist."""
    node_modules = UI_DIR / "node_modules"

    if node_modules.exists():
        print("  npm dependencies already installed")
        return True

    print("  Installing npm dependencies (this may take a few minutes)...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return run_command([npm_cmd, "install"], cwd=UI_DIR)


def build_frontend() -> bool:
    """Build the React frontend if dist doesn't exist."""
    dist_dir = UI_DIR / "dist"

    if dist_dir.exists():
        print("  Frontend already built")
        return True

    print("  Building React frontend...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return run_command([npm_cmd, "run", "build"], cwd=UI_DIR)


def start_dev_server(port: int) -> tuple:
    """Start both Vite and FastAPI in development mode."""
    venv_python = get_venv_python()

    print(f"\n  Starting development servers...")
    print(f"  - FastAPI backend: http://127.0.0.1:{port}")
    print(f"  - Vite frontend:   http://127.0.0.1:5173")

    # Start FastAPI
    backend = subprocess.Popen([
        str(venv_python), "-m", "uvicorn",
        "server.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--reload"
    ], cwd=str(ROOT))

    # Start Vite with API port env var for proxy configuration
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    vite_env = os.environ.copy()
    vite_env["VITE_API_PORT"] = str(port)
    frontend = subprocess.Popen([
        npm_cmd, "run", "dev"
    ], cwd=str(UI_DIR), env=vite_env)

    return backend, frontend


def start_production_server(port: int):
    """Start FastAPI server in production mode."""
    venv_python = get_venv_python()

    print(f"\n  Starting server at http://127.0.0.1:{port}")

    return subprocess.Popen([
        str(venv_python), "-m", "uvicorn",
        "server.main:app",
        "--host", "127.0.0.1",
        "--port", str(port)
    ], cwd=str(ROOT))


def main() -> None:
    """Main entry point."""
    dev_mode = "--dev" in sys.argv

    print("=" * 50)
    print("  Autonomous Coder UI Setup")
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

    port = find_available_port()

    try:
        if dev_mode:
            backend, frontend = start_dev_server(port)

            # Open browser to Vite dev server
            time.sleep(3)
            webbrowser.open("http://127.0.0.1:5173")

            print("\n" + "=" * 50)
            print("  Development mode active")
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
            server = start_production_server(port)

            # Open browser
            time.sleep(2)
            webbrowser.open(f"http://127.0.0.1:{port}")

            print("\n" + "=" * 50)
            print(f"  Server running at http://127.0.0.1:{port}")
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
