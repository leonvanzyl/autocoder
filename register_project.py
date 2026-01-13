#!/usr/bin/env python3
"""
Register Project Script
========================

Simple CLI script to register a project in the autocoder registry.
Called by the /create-spec command after generating spec files.

Usage:
    python register_project.py <project_name> <project_path>

Example:
    python register_project.py my-app ~/projects/my-app
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import registry
sys.path.insert(0, str(Path(__file__).parent))

from registry import register_project, get_project_path, RegistryError


def main():
    if len(sys.argv) != 3:
        print("Usage: python register_project.py <project_name> <project_path>", file=sys.stderr)
        sys.exit(1)

    name = sys.argv[1]
    path = Path(sys.argv[2]).expanduser().resolve()

    # Check if already registered
    existing_path = get_project_path(name)
    if existing_path:
        if existing_path.resolve() == path:
            print(f"Project '{name}' is already registered at {path}")
            sys.exit(0)
        else:
            print(f"Project '{name}' is already registered at a different path: {existing_path}", file=sys.stderr)
            sys.exit(1)

    # Validate path exists
    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if not path.is_dir():
        print(f"Error: Path is not a directory: {path}", file=sys.stderr)
        sys.exit(1)

    # Register the project
    try:
        register_project(name, path)
        print(f"Registered project '{name}' at {path}")
    except RegistryError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Invalid project name: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
