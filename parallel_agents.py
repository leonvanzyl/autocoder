"""
Parallel Agent Orchestrator
===========================

Manages multiple Claude agents working in parallel on the same project.
Each agent gets its own git worktree for isolation while sharing
the same feature database.
"""

import asyncio
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Literal, Optional

import psutil

from worktree import WorktreeManager

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """Information about a running agent."""
    agent_id: str
    process: Optional[subprocess.Popen] = None
    worktree_path: Optional[Path] = None
    status: Literal["stopped", "running", "paused", "crashed"] = "stopped"
    started_at: Optional[datetime] = None
    output_task: Optional[asyncio.Task] = None


class ParallelAgentOrchestrator:
    """
    Orchestrates multiple parallel agents for a project.

    Each agent:
    - Gets its own git worktree for code isolation
    - Shares the same features.db for task coordination
    - Has an independent Claude session
    """

    def __init__(
        self,
        project_dir: Path,
        root_dir: Path,
        max_agents: int = 10,
    ):
        """
        Initialize the orchestrator.

        Args:
            project_dir: The main project directory
            root_dir: Root directory of autocoder (for scripts)
            max_agents: Maximum number of parallel agents
        """
        self.project_dir = project_dir.resolve()
        self.root_dir = root_dir
        self.max_agents = max_agents
        self.worktree_manager = WorktreeManager(project_dir)

        # Track running agents
        self.agents: dict[str, AgentInfo] = {}

        # Callbacks for output streaming
        self._output_callbacks: list[Callable[[str, str], Awaitable[None]]] = []
        self._status_callbacks: list[Callable[[str, str], Awaitable[None]]] = []

    def add_output_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Add callback for agent output (agent_id, line)."""
        self._output_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Add callback for status changes (agent_id, status)."""
        self._status_callbacks.append(callback)

    async def _notify_output(self, agent_id: str, line: str) -> None:
        """Notify callbacks of agent output."""
        for callback in self._output_callbacks:
            try:
                await callback(agent_id, line)
            except Exception as e:
                logger.warning(f"Output callback error: {e}")

    async def _notify_status(self, agent_id: str, status: str) -> None:
        """Notify callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                await callback(agent_id, status)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    def generate_agent_id(self, index: int) -> str:
        """Generate a unique agent ID."""
        return f"agent-{index + 1}"

    async def start_agents(
        self,
        num_agents: int,
        yolo_mode: bool = False,
        model: str = "claude-sonnet-4-5-20250929",
        max_iterations: Optional[int] = None,
    ) -> dict[str, bool]:
        """
        Start multiple agents in parallel.

        Args:
            num_agents: Number of agents to start (capped at max_agents)
            yolo_mode: Enable YOLO mode (no browser testing)
            model: Claude model to use
            max_iterations: Maximum iterations per agent (default: unlimited)

        Returns:
            Dict mapping agent_id to success status
        """
        num_agents = min(num_agents, self.max_agents)
        results = {}

        # Ensure git repo is initialized
        if not self.worktree_manager.ensure_git_repo():
            logger.error("Failed to initialize git repository")
            return {self.generate_agent_id(i): False for i in range(num_agents)}

        # Start agents concurrently for faster initialization
        agent_ids = [self.generate_agent_id(i) for i in range(num_agents)]
        tasks = [self.start_agent(agent_id, yolo_mode, model, max_iterations) for agent_id in agent_ids]

        # Gather results, allowing individual failures
        start_results = await asyncio.gather(*tasks, return_exceptions=True)

        for agent_id, result in zip(agent_ids, start_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to start {agent_id}: {result}")
                results[agent_id] = False
            else:
                results[agent_id] = result

        return results

    async def start_agent(
        self,
        agent_id: str,
        yolo_mode: bool = False,
        model: str = "claude-sonnet-4-5-20250929",
        max_iterations: Optional[int] = None,
    ) -> bool:
        """
        Start a single agent.

        Args:
            agent_id: Unique agent identifier
            yolo_mode: Enable YOLO mode
            model: Claude model to use
            max_iterations: Maximum iterations (default: unlimited)

        Returns:
            True if started successfully
        """
        if agent_id in self.agents and self.agents[agent_id].status == "running":
            logger.warning(f"Agent {agent_id} is already running")
            return False

        # Create worktree for this agent
        worktree_path = self.worktree_manager.create_worktree(agent_id)
        if worktree_path is None:
            logger.error(f"Failed to create worktree for agent {agent_id}")
            return False

        # Build command - use the parallel agent script
        cmd = [
            sys.executable,
            str(self.root_dir / "parallel_agent_runner.py"),
            "--project-dir", str(self.project_dir),
            "--worktree-dir", str(worktree_path),
            "--agent-id", agent_id,
            "--model", model,
        ]

        if yolo_mode:
            cmd.append("--yolo")

        if max_iterations is not None:
            cmd.extend(["--max-iterations", str(max_iterations)])

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(worktree_path),
            )

            agent_info = AgentInfo(
                agent_id=agent_id,
                process=process,
                worktree_path=worktree_path,
                status="running",
                started_at=datetime.now(),
            )
            self.agents[agent_id] = agent_info

            # Start output streaming
            agent_info.output_task = asyncio.create_task(
                self._stream_output(agent_id)
            )

            await self._notify_status(agent_id, "running")
            logger.info(f"Started agent {agent_id} (PID {process.pid})")
            return True

        except Exception as e:
            logger.exception(f"Failed to start agent {agent_id}")
            return False

    async def _stream_output(self, agent_id: str) -> None:
        """Stream output from an agent process."""
        agent = self.agents.get(agent_id)
        if not agent or not agent.process or not agent.process.stdout:
            return

        try:
            loop = asyncio.get_running_loop()
            while True:
                line = await loop.run_in_executor(
                    None, agent.process.stdout.readline
                )
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                await self._notify_output(agent_id, decoded)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Output streaming error for {agent_id}: {e}")
        finally:
            # Check if process ended
            if agent.process and agent.process.poll() is not None:
                exit_code = agent.process.returncode
                if exit_code != 0 and agent.status == "running":
                    agent.status = "crashed"
                elif agent.status == "running":
                    agent.status = "stopped"
                await self._notify_status(agent_id, agent.status)

    async def stop_agent(self, agent_id: str) -> bool:
        """Stop a single agent."""
        agent = self.agents.get(agent_id)
        if not agent or not agent.process:
            return False

        try:
            # Cancel output streaming
            if agent.output_task:
                agent.output_task.cancel()
                try:
                    await agent.output_task
                except asyncio.CancelledError:
                    pass

            # Terminate process
            agent.process.terminate()

            loop = asyncio.get_running_loop()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, agent.process.wait),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                agent.process.kill()
                await loop.run_in_executor(None, agent.process.wait)

            agent.status = "stopped"
            agent.process = None
            await self._notify_status(agent_id, "stopped")

            logger.info(f"Stopped agent {agent_id}")
            return True

        except Exception as e:
            logger.exception(f"Failed to stop agent {agent_id}")
            return False

    async def stop_all_agents(self) -> None:
        """Stop all running agents."""
        tasks = []
        for agent_id in list(self.agents.keys()):
            if self.agents[agent_id].status == "running":
                tasks.append(self.stop_agent(agent_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def pause_agent(self, agent_id: str) -> bool:
        """
        Pause an agent using psutil suspend (SIGSTOP on Unix).

        WARNING: This uses SIGSTOP/SIGCONT which has known limitations:
        - The entire process and asyncio event loop are frozen
        - On resume, pending signals, timeouts, and callbacks fire in a burst
        - Outstanding async operations (API requests, I/O) may timeout or fail
        - Child watcher and signal handling may have unpredictable behavior

        For production use, consider stop/start semantics instead if the agent
        has long-running async operations that could be interrupted.
        """
        agent = self.agents.get(agent_id)
        if not agent or not agent.process or agent.status != "running":
            return False

        try:
            proc = psutil.Process(agent.process.pid)
            proc.suspend()
            agent.status = "paused"
            await self._notify_status(agent_id, "paused")
            return True
        except Exception as e:
            logger.exception(f"Failed to pause agent {agent_id}")
            return False

    async def resume_agent(self, agent_id: str) -> bool:
        """
        Resume a paused agent using psutil resume (SIGCONT on Unix).

        WARNING: See pause_agent docstring for important caveats about
        SIGSTOP/SIGCONT and asyncio. After resume, the agent may experience:
        - Burst of delayed timer/callback executions
        - Potential connection timeouts or stale state
        - Signal delivery ordering issues
        """
        agent = self.agents.get(agent_id)
        if not agent or not agent.process or agent.status != "paused":
            return False

        try:
            proc = psutil.Process(agent.process.pid)
            proc.resume()
            agent.status = "running"
            await self._notify_status(agent_id, "running")
            return True
        except Exception as e:
            logger.exception(f"Failed to resume agent {agent_id}")
            return False

    def get_agent_status(self, agent_id: str) -> dict:
        """Get status of a single agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"agent_id": agent_id, "status": "unknown"}

        return {
            "agent_id": agent_id,
            "status": agent.status,
            "pid": agent.process.pid if agent.process else None,
            "started_at": agent.started_at.isoformat() if agent.started_at else None,
            "worktree_path": str(agent.worktree_path) if agent.worktree_path else None,
        }

    def get_all_statuses(self) -> list[dict]:
        """Get status of all agents."""
        return [self.get_agent_status(aid) for aid in self.agents]

    async def healthcheck(self) -> dict[str, bool]:
        """Check health of all agents."""
        results = {}
        for agent_id, agent in self.agents.items():
            if not agent.process:
                results[agent_id] = agent.status == "stopped"
                continue

            poll = agent.process.poll()
            if poll is not None:
                if agent.status in ("running", "paused"):
                    agent.status = "crashed"
                    await self._notify_status(agent_id, "crashed")
                results[agent_id] = False
            else:
                results[agent_id] = True

        return results

    async def merge_all_worktrees(self) -> dict[str, bool]:
        """Merge changes from all agent worktrees back to main."""
        results = {}
        for agent_id in self.agents:
            success = self.worktree_manager.merge_worktree_changes(agent_id)
            results[agent_id] = success
        return results

    async def cleanup(self) -> None:
        """Stop all agents and clean up worktrees."""
        await self.stop_all_agents()
        self.worktree_manager.cleanup_all_worktrees()


# Global orchestrator registry
_orchestrators: dict[str, ParallelAgentOrchestrator] = {}


def get_orchestrator(
    project_name: str,
    project_dir: Path,
    root_dir: Path,
    max_agents: int = 3,
) -> ParallelAgentOrchestrator:
    """Get or create an orchestrator for a project."""
    if project_name not in _orchestrators:
        _orchestrators[project_name] = ParallelAgentOrchestrator(
            project_dir, root_dir, max_agents
        )
    return _orchestrators[project_name]
