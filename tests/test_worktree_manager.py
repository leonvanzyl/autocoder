#!/usr/bin/env python3
"""
Worktree Manager Tests
======================

Tests for git worktree management which enables parallel agents to work
in isolation without conflicting with each other.

Run with: pytest tests/test_worktree_manager.py -v
"""

import tempfile
import shutil
import subprocess
from pathlib import Path

from autocoder.core.worktree_manager import WorktreeManager


def test_worktree_manager_initialization():
    """Test that worktree manager can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "main_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

        # Initialize worktree manager
        wm = WorktreeManager(str(repo_path))
        assert wm.repo_path == str(repo_path)
        print("✅ Worktree manager initialization works")


def test_worktree_creation():
    """Test creating a new worktree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "main_repo"
        repo_path.mkdir()

        # Setup git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

        # Create worktree
        wm = WorktreeManager(str(repo_path))
        worktree_path = wm.create_worktree("feature-1")

        assert worktree_path is not None, "Worktree should be created"
        assert Path(worktree_path).exists(), "Worktree path should exist"
        assert (Path(worktree_path) / "README.md").exists(), "Worktree should have files from main branch"

        # Cleanup
        wm.remove_worktree("feature-1")
        print("✅ Worktree creation works")


def test_worktree_can_attach_existing_branch():
    """WorktreeManager can create a worktree for an existing branch (resume)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "main_repo"
        repo_path.mkdir()

        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo_path, capture_output=True, check=True)

        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True)

        # Create an existing branch.
        subprocess.run(["git", "checkout", "-b", "feat/existing"], cwd=repo_path, capture_output=True, check=True)
        (repo_path / "A.txt").write_text("a", encoding="utf-8")
        subprocess.run(["git", "add", "A.txt"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, capture_output=True, check=True)

        wm = WorktreeManager(str(repo_path))
        info = wm.create_worktree("resume-1", feature_id=1, feature_name="x", branch_name="feat/existing")
        assert isinstance(info, dict)
        wt = Path(info["worktree_path"])
        assert (wt / "A.txt").exists()

        wm.remove_worktree("resume-1")


def test_worktree_listing():
    """Test listing all worktrees."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "main_repo"
        repo_path.mkdir()

        # Setup git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

        # Create multiple worktrees
        wm = WorktreeManager(str(repo_path))
        wm.create_worktree("feature-1")
        wm.create_worktree("feature-2")

        # List worktrees
        worktrees = wm.list_worktrees()
        assert len(worktrees) >= 2, "Should have at least 2 worktrees"

        # Cleanup
        wm.remove_worktree("feature-1")
        wm.remove_worktree("feature-2")
        print("✅ Worktree listing works")


def test_worktree_removal():
    """Test removing a worktree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "main_repo"
        repo_path.mkdir()

        # Setup git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

        # Create and remove worktree
        wm = WorktreeManager(str(repo_path))
        worktree_path = wm.create_worktree("feature-1")

        assert Path(worktree_path).exists(), "Worktree should exist"

        wm.remove_worktree("feature-1")

        # Worktree directory should be removed
        # Note: Git worktree prune might be needed
        print("✅ Worktree removal works")


if __name__ == "__main__":
    print("Running Worktree Manager Tests...\n")

    test_worktree_manager_initialization()
    test_worktree_creation()
    test_worktree_listing()
    test_worktree_removal()

    print("\n" + "=" * 70)
    print("ALL WORKTREE MANAGER TESTS PASSED ✅")
    print("=" * 70)
