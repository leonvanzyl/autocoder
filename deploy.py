#!/usr/bin/env python3
"""
Autocoder Deployment Manager
============================

Manages the Autocoder application lifecycle:
- Start/stop/restart the backend API server
- Start/stop/restart the frontend UI
- Automatic port conflict detection and resolution
- Process management with PID tracking

Usage:
    python deploy.py start          # Start both backend and frontend
    python deploy.py stop           # Stop all services
    python deploy.py restart        # Restart all services
    python deploy.py status         # Show service status
    python deploy.py start backend  # Start only backend
    python deploy.py start frontend # Start only frontend
    python deploy.py logs           # Tail the logs
"""

import argparse
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Configuration
ROOT_DIR = Path(__file__).parent.resolve()
PID_FILE = ROOT_DIR / ".deploy.pid"
LOG_DIR = ROOT_DIR / "logs"
BACKEND_LOG = LOG_DIR / "backend.log"
FRONTEND_LOG = LOG_DIR / "frontend.log"

# Default ports (will find alternatives if busy)
DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 5173

# Port range to search for available ports
PORT_RANGE_START = 8000
PORT_RANGE_END = 9000


@dataclass
class ServiceInfo:
    """Information about a running service."""
    name: str
    pid: int
    port: int
    started_at: str


def is_port_available(port: int) -> bool:
    """Check if a port is available for use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            return True
    except (OSError, socket.error):
        return False


def find_available_port(start_port: int, exclude: set[int] = None) -> int:
    """Find an available port starting from start_port."""
    exclude = exclude or set()
    for port in range(start_port, PORT_RANGE_END):
        if port not in exclude and is_port_available(port):
            return port
    raise RuntimeError(f"No available ports found in range {start_port}-{PORT_RANGE_END}")


def get_process_using_port(port: int) -> Optional[str]:
    """Get the process using a specific port."""
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        # Get process name
                        name_result = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                            capture_output=True,
                            text=True,
                        )
                        if name_result.stdout:
                            lines = name_result.stdout.strip().split("\n")
                            if len(lines) > 1:
                                return f"{lines[1].split(',')[0].strip('\"')} (PID: {pid})"
                        return f"PID: {pid}"
        else:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                pid = result.stdout.strip().split("\n")[0]
                # Get process name
                name_result = subprocess.run(
                    ["ps", "-p", pid, "-o", "comm="],
                    capture_output=True,
                    text=True,
                )
                name = name_result.stdout.strip() or "unknown"
                return f"{name} (PID: {pid})"
    except Exception:
        pass
    return None


def load_pid_file() -> dict:
    """Load the PID file containing service information."""
    if PID_FILE.exists():
        try:
            return json.loads(PID_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_pid_file(data: dict) -> None:
    """Save service information to the PID file."""
    PID_FILE.write_text(json.dumps(data, indent=2))


def is_process_running(pid: int) -> bool:
    """Check if a process is running by PID."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.SubprocessError):
        return False


def kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process by PID."""
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/F" if force else "", "/PID", str(pid)],
                capture_output=True,
            )
        else:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_venv() -> Path:
    """Ensure virtual environment exists and return python path."""
    venv_dir = ROOT_DIR / "venv"

    if platform.system() == "Windows":
        python_path = venv_dir / "Scripts" / "python.exe"
        pip_path = venv_dir / "Scripts" / "pip.exe"
    else:
        python_path = venv_dir / "bin" / "python"
        pip_path = venv_dir / "bin" / "pip"

    if not python_path.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("Installing dependencies...")
        subprocess.run([str(pip_path), "install", "-r", str(ROOT_DIR / "requirements.txt")], check=True)

    return python_path


def start_backend(port: int = None) -> ServiceInfo:
    """Start the backend API server."""
    LOG_DIR.mkdir(exist_ok=True)

    # Find available port
    if port is None:
        port = find_available_port(DEFAULT_BACKEND_PORT)

    if not is_port_available(port):
        process = get_process_using_port(port)
        print(f"Port {port} is in use by: {process}")
        port = find_available_port(port + 1)
        print(f"Using alternative port: {port}")

    python_path = ensure_venv()

    # Start uvicorn
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    with open(BACKEND_LOG, "a") as log:
        log.write(f"\n{'='*60}\nStarting backend at {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n")

    if platform.system() == "Windows":
        # Windows: use subprocess with CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(
            [
                str(python_path), "-m", "uvicorn",
                "server.main:app",
                "--host", "0.0.0.0",
                "--port", str(port),
            ],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=open(BACKEND_LOG, "a"),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        # Unix: use nohup-style daemonization
        process = subprocess.Popen(
            [
                str(python_path), "-m", "uvicorn",
                "server.main:app",
                "--host", "0.0.0.0",
                "--port", str(port),
            ],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=open(BACKEND_LOG, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Wait a moment and verify it started
    time.sleep(2)
    if not is_process_running(process.pid):
        raise RuntimeError("Backend failed to start. Check logs/backend.log")

    return ServiceInfo(
        name="backend",
        pid=process.pid,
        port=port,
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def start_frontend(port: int = None, backend_port: int = DEFAULT_BACKEND_PORT) -> ServiceInfo:
    """Start the frontend development server."""
    LOG_DIR.mkdir(exist_ok=True)
    ui_dir = ROOT_DIR / "ui"

    # Check if node_modules exists
    if not (ui_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(ui_dir), check=True)

    # Find available port
    if port is None:
        port = find_available_port(DEFAULT_FRONTEND_PORT, exclude={backend_port})

    if not is_port_available(port):
        process = get_process_using_port(port)
        print(f"Port {port} is in use by: {process}")
        port = find_available_port(port + 1, exclude={backend_port})
        print(f"Using alternative port: {port}")

    env = os.environ.copy()
    env["VITE_API_URL"] = f"http://localhost:{backend_port}"

    with open(FRONTEND_LOG, "a") as log:
        log.write(f"\n{'='*60}\nStarting frontend at {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n")

    if platform.system() == "Windows":
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port), "--host"],
            cwd=str(ui_dir),
            env=env,
            stdout=open(FRONTEND_LOG, "a"),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            shell=True,
        )
    else:
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port), "--host"],
            cwd=str(ui_dir),
            env=env,
            stdout=open(FRONTEND_LOG, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # Wait a moment and verify it started
    time.sleep(3)
    if not is_process_running(process.pid):
        raise RuntimeError("Frontend failed to start. Check logs/frontend.log")

    return ServiceInfo(
        name="frontend",
        pid=process.pid,
        port=port,
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def stop_service(name: str) -> bool:
    """Stop a service by name."""
    pids = load_pid_file()

    if name not in pids:
        print(f"No {name} service found in PID file")
        return False

    info = pids[name]
    pid = info["pid"]

    if is_process_running(pid):
        print(f"Stopping {name} (PID: {pid})...")
        kill_process(pid)
        time.sleep(1)

        # Force kill if still running
        if is_process_running(pid):
            print(f"Force killing {name}...")
            kill_process(pid, force=True)
            time.sleep(1)

        if is_process_running(pid):
            print(f"Failed to stop {name}")
            return False

    del pids[name]
    save_pid_file(pids)
    print(f"Stopped {name}")
    return True


def get_status() -> dict:
    """Get the status of all services."""
    pids = load_pid_file()
    status = {}

    for name, info in pids.items():
        pid = info["pid"]
        port = info["port"]
        running = is_process_running(pid)
        port_open = not is_port_available(port)

        status[name] = {
            **info,
            "running": running,
            "port_open": port_open,
            "status": "running" if running and port_open else "stopped" if not running else "error",
        }

    return status


def print_status():
    """Print the status of all services."""
    status = get_status()

    if not status:
        print("No services registered")
        return

    print("\nAutocoder Service Status")
    print("=" * 60)

    for name, info in status.items():
        status_icon = "✓" if info["status"] == "running" else "✗"
        print(f"\n{status_icon} {name.upper()}")
        print(f"  PID:        {info['pid']}")
        print(f"  Port:       {info['port']}")
        print(f"  Status:     {info['status']}")
        print(f"  Started:    {info['started_at']}")

        if info["status"] == "running":
            if name == "backend":
                print(f"  API URL:    http://localhost:{info['port']}")
                print(f"  Docs:       http://localhost:{info['port']}/docs")
            elif name == "frontend":
                print(f"  UI URL:     http://localhost:{info['port']}")

    print()


def cmd_start(args):
    """Handle start command."""
    pids = load_pid_file()

    services = args.service if args.service else ["backend", "frontend"]

    backend_port = None

    for service in services:
        if service == "backend":
            if "backend" in pids and is_process_running(pids["backend"]["pid"]):
                print("Backend is already running")
                backend_port = pids["backend"]["port"]
                continue

            print("Starting backend...")
            try:
                info = start_backend(port=args.backend_port)
                pids["backend"] = {
                    "pid": info.pid,
                    "port": info.port,
                    "started_at": info.started_at,
                }
                backend_port = info.port
                print(f"Backend started on port {info.port} (PID: {info.pid})")
            except Exception as e:
                print(f"Failed to start backend: {e}")
                return 1

        elif service == "frontend":
            if "frontend" in pids and is_process_running(pids["frontend"]["pid"]):
                print("Frontend is already running")
                continue

            # Use backend port if available
            if backend_port is None and "backend" in pids:
                backend_port = pids["backend"]["port"]

            print("Starting frontend...")
            try:
                info = start_frontend(
                    port=args.frontend_port,
                    backend_port=backend_port or DEFAULT_BACKEND_PORT,
                )
                pids["frontend"] = {
                    "pid": info.pid,
                    "port": info.port,
                    "started_at": info.started_at,
                }
                print(f"Frontend started on port {info.port} (PID: {info.pid})")
            except Exception as e:
                print(f"Failed to start frontend: {e}")
                return 1

    save_pid_file(pids)
    print_status()
    return 0


def cmd_stop(args):
    """Handle stop command."""
    services = args.service if args.service else ["frontend", "backend"]

    for service in services:
        stop_service(service)

    print_status()
    return 0


def cmd_restart(args):
    """Handle restart command."""
    cmd_stop(args)
    time.sleep(2)
    return cmd_start(args)


def cmd_status(args):
    """Handle status command."""
    print_status()

    # Also check for port conflicts
    print("Port Availability Check")
    print("-" * 40)

    for port in [DEFAULT_BACKEND_PORT, DEFAULT_FRONTEND_PORT]:
        if is_port_available(port):
            print(f"  Port {port}: Available")
        else:
            process = get_process_using_port(port)
            print(f"  Port {port}: In use by {process}")

    return 0


def cmd_logs(args):
    """Handle logs command."""
    log_file = BACKEND_LOG if args.service == "backend" else FRONTEND_LOG if args.service == "frontend" else None

    if log_file is None:
        # Tail both logs
        print("Tailing all logs (Ctrl+C to stop)...")
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["powershell", "-Command",
                     f"Get-Content '{BACKEND_LOG}','{FRONTEND_LOG}' -Wait -Tail 50"],
                    check=True,
                )
            else:
                subprocess.run(
                    ["tail", "-f", str(BACKEND_LOG), str(FRONTEND_LOG)],
                    check=True,
                )
        except KeyboardInterrupt:
            pass
    else:
        if not log_file.exists():
            print(f"Log file not found: {log_file}")
            return 1

        print(f"Tailing {log_file} (Ctrl+C to stop)...")
        try:
            if platform.system() == "Windows":
                subprocess.run(
                    ["powershell", "-Command", f"Get-Content '{log_file}' -Wait -Tail 50"],
                    check=True,
                )
            else:
                subprocess.run(["tail", "-f", str(log_file)], check=True)
        except KeyboardInterrupt:
            pass

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Autocoder Deployment Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py start                  # Start all services
  python deploy.py start backend          # Start only backend
  python deploy.py stop                   # Stop all services
  python deploy.py restart                # Restart all services
  python deploy.py status                 # Show service status
  python deploy.py logs                   # Tail all logs
  python deploy.py logs backend           # Tail backend logs

  # Custom ports
  python deploy.py start --backend-port 8080 --frontend-port 3000
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start services")
    start_parser.add_argument(
        "service",
        nargs="*",
        choices=["backend", "frontend"],
        help="Service(s) to start (default: all)",
    )
    start_parser.add_argument(
        "--backend-port", "-b",
        type=int,
        default=None,
        help=f"Backend port (default: auto, starting from {DEFAULT_BACKEND_PORT})",
    )
    start_parser.add_argument(
        "--frontend-port", "-f",
        type=int,
        default=None,
        help=f"Frontend port (default: auto, starting from {DEFAULT_FRONTEND_PORT})",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop services")
    stop_parser.add_argument(
        "service",
        nargs="*",
        choices=["backend", "frontend"],
        help="Service(s) to stop (default: all)",
    )

    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart services")
    restart_parser.add_argument(
        "service",
        nargs="*",
        choices=["backend", "frontend"],
        help="Service(s) to restart (default: all)",
    )
    restart_parser.add_argument(
        "--backend-port", "-b",
        type=int,
        default=None,
        help=f"Backend port (default: auto)",
    )
    restart_parser.add_argument(
        "--frontend-port", "-f",
        type=int,
        default=None,
        help=f"Frontend port (default: auto)",
    )

    # Status command
    subparsers.add_parser("status", help="Show service status")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Tail service logs")
    logs_parser.add_argument(
        "service",
        nargs="?",
        choices=["backend", "frontend"],
        help="Service logs to tail (default: all)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
