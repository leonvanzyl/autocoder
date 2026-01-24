"""
WebSocket Handlers
==================

Real-time updates for project progress, agent output, and dev server output.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from .schemas import AGENT_MASCOTS
from .services.dev_server_manager import get_devserver_manager
from .services.process_manager import get_manager

# Lazy imports
_count_passing_tests = None

logger = logging.getLogger(__name__)

# Pattern to extract feature ID from parallel orchestrator output
# Both coding and testing agents now use the same [Feature #X] format
FEATURE_ID_PATTERN = re.compile(r'\[Feature #(\d+)\]\s*(.*)')

# Pattern to detect testing agent start message (includes feature ID)
# Matches: "Started testing agent for feature #123 (PID xxx)"
TESTING_AGENT_START_PATTERN = re.compile(r'Started testing agent for feature #(\d+)')

# Pattern to detect testing agent completion
# Matches: "Feature #123 testing completed" or "Feature #123 testing failed"
TESTING_AGENT_COMPLETE_PATTERN = re.compile(r'Feature #(\d+) testing (completed|failed)')

# Patterns for detecting agent activity and thoughts
THOUGHT_PATTERNS = [
    # Claude's tool usage patterns (actual format: [Tool: name])
    (re.compile(r'\[Tool:\s*Read\]', re.I), 'thinking'),
    (re.compile(r'\[Tool:\s*(?:Write|Edit|NotebookEdit)\]', re.I), 'working'),
    (re.compile(r'\[Tool:\s*Bash\]', re.I), 'testing'),
    (re.compile(r'\[Tool:\s*(?:Glob|Grep)\]', re.I), 'thinking'),
    (re.compile(r'\[Tool:\s*(\w+)\]', re.I), 'working'),  # Fallback for other tools
    # Claude's internal thoughts
    (re.compile(r'(?:Reading|Analyzing|Checking|Looking at|Examining)\s+(.+)', re.I), 'thinking'),
    (re.compile(r'(?:Creating|Writing|Adding|Implementing|Building)\s+(.+)', re.I), 'working'),
    (re.compile(r'(?:Testing|Verifying|Running tests|Validating)\s+(.+)', re.I), 'testing'),
    (re.compile(r'(?:Error|Failed|Cannot|Unable to|Exception)\s+(.+)', re.I), 'struggling'),
    # Test results
    (re.compile(r'(?:PASS|passed|success)', re.I), 'success'),
    (re.compile(r'(?:FAIL|failed|error)', re.I), 'struggling'),
]

# Orchestrator event patterns for Mission Control observability
ORCHESTRATOR_PATTERNS = {
    'init_start': re.compile(r'Running initializer agent'),
    'init_complete': re.compile(r'INITIALIZATION COMPLETE'),
    'capacity_check': re.compile(r'\[DEBUG\] Spawning loop: (\d+) ready, (\d+) slots'),
    'at_capacity': re.compile(r'At max capacity|at max testing agents|At max total agents'),
    'feature_start': re.compile(r'Starting feature \d+/\d+: #(\d+) - (.+)'),
    'coding_spawn': re.compile(r'Started coding agent for feature #(\d+)'),
    'testing_spawn': re.compile(r'Started testing agent for feature #(\d+)'),
    'coding_complete': re.compile(r'Feature #(\d+) (completed|failed)'),
    'testing_complete': re.compile(r'Feature #(\d+) testing (completed|failed)'),
    'all_complete': re.compile(r'All features complete'),
    'blocked_features': re.compile(r'(\d+) blocked by dependencies'),
}


class AgentTracker:
    """Tracks active agents and their states for multi-agent mode.

    Both coding and testing agents are tracked using a composite key of
    (feature_id, agent_type) to allow simultaneous tracking of both agent
    types for the same feature.
    """

    def __init__(self):
        # (feature_id, agent_type) -> {name, state, last_thought, agent_index, agent_type}
        self.active_agents: dict[tuple[int, str], dict] = {}
        self._next_agent_index = 0
        self._lock = asyncio.Lock()

    async def process_line(self, line: str) -> dict | None:
        """
        Process an output line and return an agent_update message if relevant.

        Returns None if no update should be emitted.
        """
        # Check for orchestrator status messages first
        # These don't have [Feature #X] prefix

        # Coding agent start: "Started coding agent for feature #X"
        if line.startswith("Started coding agent for feature #"):
            try:
                feature_id = int(re.search(r'#(\d+)', line).group(1))
                return await self._handle_agent_start(feature_id, line, agent_type="coding")
            except (AttributeError, ValueError):
                pass

        # Testing agent start: "Started testing agent for feature #X (PID xxx)"
        testing_start_match = TESTING_AGENT_START_PATTERN.match(line)
        if testing_start_match:
            feature_id = int(testing_start_match.group(1))
            return await self._handle_agent_start(feature_id, line, agent_type="testing")

        # Testing agent complete: "Feature #X testing completed/failed"
        testing_complete_match = TESTING_AGENT_COMPLETE_PATTERN.match(line)
        if testing_complete_match:
            feature_id = int(testing_complete_match.group(1))
            is_success = testing_complete_match.group(2) == "completed"
            return await self._handle_agent_complete(feature_id, is_success, agent_type="testing")

        # Coding agent complete: "Feature #X completed/failed" (without "testing" keyword)
        if line.startswith("Feature #") and ("completed" in line or "failed" in line) and "testing" not in line:
            try:
                feature_id = int(re.search(r'#(\d+)', line).group(1))
                is_success = "completed" in line
                return await self._handle_agent_complete(feature_id, is_success, agent_type="coding")
            except (AttributeError, ValueError):
                pass

        # Check for feature-specific output lines: [Feature #X] content
        # Both coding and testing agents use this format now
        match = FEATURE_ID_PATTERN.match(line)
        if not match:
            return None

        feature_id = int(match.group(1))
        content = match.group(2)

        async with self._lock:
            # Check if either coding or testing agent exists for this feature
            # This prevents creating ghost agents when a testing agent outputs [Feature #X] lines
            coding_key = (feature_id, 'coding')
            testing_key = (feature_id, 'testing')

            if coding_key in self.active_agents:
                key = coding_key
            elif testing_key in self.active_agents:
                key = testing_key
            else:
                # Neither exists, create a new coding agent entry (implicit tracking)
                key = coding_key
                agent_index = self._next_agent_index
                self._next_agent_index += 1
                self.active_agents[key] = {
                    'name': AGENT_MASCOTS[agent_index % len(AGENT_MASCOTS)],
                    'agent_index': agent_index,
                    'agent_type': 'coding',
                    'state': 'thinking',
                    'feature_name': f'Feature #{feature_id}',
                    'last_thought': None,
                }

            agent = self.active_agents[key]

            # Detect state and thought from content
            state = 'working'
            thought = None

            for pattern, detected_state in THOUGHT_PATTERNS:
                m = pattern.search(content)
                if m:
                    state = detected_state
                    thought = m.group(1) if m.lastindex else content[:100]
                    break

            # Only emit update if state changed or we have a new thought
            if state != agent['state'] or thought != agent['last_thought']:
                agent['state'] = state
                if thought:
                    agent['last_thought'] = thought

                return {
                    'type': 'agent_update',
                    'agentIndex': agent['agent_index'],
                    'agentName': agent['name'],
                    'agentType': agent['agent_type'],
                    'featureId': feature_id,
                    'featureName': agent['feature_name'],
                    'state': state,
                    'thought': thought,
                    'timestamp': datetime.now().isoformat(),
                }

        return None

    async def get_agent_info(self, feature_id: int, agent_type: str = "coding") -> tuple[int | None, str | None]:
        """Get agent index and name for a feature ID and agent type.

        Thread-safe method that acquires the lock before reading state.

        Args:
            feature_id: The feature ID to look up.
            agent_type: The agent type ("coding" or "testing"). Defaults to "coding".

        Returns:
            Tuple of (agentIndex, agentName) or (None, None) if not tracked.
        """
        async with self._lock:
            key = (feature_id, agent_type)
            agent = self.active_agents.get(key)
            if agent:
                return agent['agent_index'], agent['name']
            return None, None

    async def reset(self):
        """Reset tracker state when orchestrator stops or crashes.

        Clears all active agents and resets the index counter to prevent
        ghost agents accumulating across start/stop cycles.

        Must be called with await since it acquires the async lock.
        """
        async with self._lock:
            self.active_agents.clear()
            self._next_agent_index = 0

    async def _handle_agent_start(self, feature_id: int, line: str, agent_type: str = "coding") -> dict | None:
        """Handle agent start message from orchestrator."""
        async with self._lock:
            key = (feature_id, agent_type)  # Composite key for separate tracking
            agent_index = self._next_agent_index
            self._next_agent_index += 1

            # Try to extract feature name from line
            feature_name = f'Feature #{feature_id}'
            name_match = re.search(r'#\d+:\s*(.+)$', line)
            if name_match:
                feature_name = name_match.group(1)

            self.active_agents[key] = {
                'name': AGENT_MASCOTS[agent_index % len(AGENT_MASCOTS)],
                'agent_index': agent_index,
                'agent_type': agent_type,
                'state': 'thinking',
                'feature_name': feature_name,
                'last_thought': 'Starting work...',
            }

            return {
                'type': 'agent_update',
                'agentIndex': agent_index,
                'agentName': AGENT_MASCOTS[agent_index % len(AGENT_MASCOTS)],
                'agentType': agent_type,
                'featureId': feature_id,
                'featureName': feature_name,
                'state': 'thinking',
                'thought': 'Starting work...',
                'timestamp': datetime.now().isoformat(),
            }

    async def _handle_agent_complete(self, feature_id: int, is_success: bool, agent_type: str = "coding") -> dict | None:
        """Handle agent completion - ALWAYS emits a message, even if agent wasn't tracked.

        Args:
            feature_id: The feature ID.
            is_success: Whether the agent completed successfully.
            agent_type: The agent type ("coding" or "testing"). Defaults to "coding".
        """
        async with self._lock:
            key = (feature_id, agent_type)  # Composite key for correct agent lookup
            state = 'success' if is_success else 'error'

            if key in self.active_agents:
                # Normal case: agent was tracked
                agent = self.active_agents[key]
                result = {
                    'type': 'agent_update',
                    'agentIndex': agent['agent_index'],
                    'agentName': agent['name'],
                    'agentType': agent.get('agent_type', agent_type),
                    'featureId': feature_id,
                    'featureName': agent['feature_name'],
                    'state': state,
                    'thought': 'Completed successfully!' if is_success else 'Failed to complete',
                    'timestamp': datetime.now().isoformat(),
                }
                del self.active_agents[key]
                return result
            else:
                # Synthetic completion for untracked agent
                # This ensures UI always receives completion messages
                return {
                    'type': 'agent_update',
                    'agentIndex': -1,  # Sentinel for untracked
                    'agentName': 'Unknown',
                    'agentType': agent_type,
                    'featureId': feature_id,
                    'featureName': f'Feature #{feature_id}',
                    'state': state,
                    'thought': 'Completed successfully!' if is_success else 'Failed to complete',
                    'timestamp': datetime.now().isoformat(),
                    'synthetic': True,
                }


class OrchestratorTracker:
    """Tracks orchestrator state for Mission Control observability.

    Parses orchestrator stdout for key events and emits orchestrator_update
    WebSocket messages showing what decisions the orchestrator is making.
    """

    def __init__(self):
        self.state = 'idle'
        self.coding_agents = 0
        self.testing_agents = 0
        self.max_concurrency = 3  # Default, will be updated from output
        self.ready_count = 0
        self.blocked_count = 0
        self.recent_events: list[dict] = []
        self._lock = asyncio.Lock()

    async def process_line(self, line: str) -> dict | None:
        """
        Process an output line and return an orchestrator_update message if relevant.

        Returns None if no update should be emitted.
        """
        async with self._lock:
            update = None

            # Check for initializer start
            if ORCHESTRATOR_PATTERNS['init_start'].search(line):
                self.state = 'initializing'
                update = self._create_update(
                    'init_start',
                    'Initializing project features...'
                )

            # Check for initializer complete
            elif ORCHESTRATOR_PATTERNS['init_complete'].search(line):
                self.state = 'scheduling'
                update = self._create_update(
                    'init_complete',
                    'Initialization complete, preparing to schedule features'
                )

            # Check for capacity status
            elif match := ORCHESTRATOR_PATTERNS['capacity_check'].search(line):
                self.ready_count = int(match.group(1))
                slots = int(match.group(2))
                self.state = 'scheduling' if self.ready_count > 0 else 'monitoring'
                update = self._create_update(
                    'capacity_check',
                    f'{self.ready_count} features ready, {slots} slots available'
                )

            # Check for at capacity
            elif ORCHESTRATOR_PATTERNS['at_capacity'].search(line):
                self.state = 'monitoring'
                update = self._create_update(
                    'at_capacity',
                    'At maximum capacity, monitoring active agents'
                )

            # Check for feature start
            elif match := ORCHESTRATOR_PATTERNS['feature_start'].search(line):
                feature_id = int(match.group(1))
                feature_name = match.group(2).strip()
                self.state = 'spawning'
                update = self._create_update(
                    'feature_start',
                    f'Preparing Feature #{feature_id}: {feature_name}',
                    feature_id=feature_id,
                    feature_name=feature_name
                )

            # Check for coding agent spawn
            elif match := ORCHESTRATOR_PATTERNS['coding_spawn'].search(line):
                feature_id = int(match.group(1))
                self.coding_agents += 1
                self.state = 'spawning'
                update = self._create_update(
                    'coding_spawn',
                    f'Spawned coding agent for Feature #{feature_id}',
                    feature_id=feature_id
                )

            # Check for testing agent spawn
            elif match := ORCHESTRATOR_PATTERNS['testing_spawn'].search(line):
                feature_id = int(match.group(1))
                self.testing_agents += 1
                self.state = 'spawning'
                update = self._create_update(
                    'testing_spawn',
                    f'Spawned testing agent for Feature #{feature_id}',
                    feature_id=feature_id
                )

            # Check for coding agent complete
            elif match := ORCHESTRATOR_PATTERNS['coding_complete'].search(line):
                # Only match if "testing" is not in the line
                if 'testing' not in line.lower():
                    feature_id = int(match.group(1))
                    self.coding_agents = max(0, self.coding_agents - 1)
                    self.state = 'monitoring'
                    update = self._create_update(
                        'coding_complete',
                        f'Coding agent finished Feature #{feature_id}',
                        feature_id=feature_id
                    )

            # Check for testing agent complete
            elif match := ORCHESTRATOR_PATTERNS['testing_complete'].search(line):
                feature_id = int(match.group(1))
                self.testing_agents = max(0, self.testing_agents - 1)
                self.state = 'monitoring'
                update = self._create_update(
                    'testing_complete',
                    f'Testing agent finished Feature #{feature_id}',
                    feature_id=feature_id
                )

            # Check for blocked features count
            elif match := ORCHESTRATOR_PATTERNS['blocked_features'].search(line):
                self.blocked_count = int(match.group(1))

            # Check for all complete
            elif ORCHESTRATOR_PATTERNS['all_complete'].search(line):
                self.state = 'complete'
                self.coding_agents = 0
                self.testing_agents = 0
                update = self._create_update(
                    'all_complete',
                    'All features complete!'
                )

            return update

    def _create_update(
        self,
        event_type: str,
        message: str,
        feature_id: int | None = None,
        feature_name: str | None = None
    ) -> dict:
        """Create an orchestrator_update WebSocket message."""
        timestamp = datetime.now().isoformat()

        # Add to recent events (keep last 5)
        event = {
            'eventType': event_type,
            'message': message,
            'timestamp': timestamp,
        }
        if feature_id is not None:
            event['featureId'] = feature_id
        if feature_name is not None:
            event['featureName'] = feature_name

        self.recent_events = [event] + self.recent_events[:4]

        update = {
            'type': 'orchestrator_update',
            'eventType': event_type,
            'state': self.state,
            'message': message,
            'timestamp': timestamp,
            'codingAgents': self.coding_agents,
            'testingAgents': self.testing_agents,
            'maxConcurrency': self.max_concurrency,
            'readyCount': self.ready_count,
            'blockedCount': self.blocked_count,
        }

        if feature_id is not None:
            update['featureId'] = feature_id
        if feature_name is not None:
            update['featureName'] = feature_name

        return update

    async def reset(self):
        """Reset tracker state when orchestrator stops or crashes."""
        async with self._lock:
            self.state = 'idle'
            self.coding_agents = 0
            self.testing_agents = 0
            self.ready_count = 0
            self.blocked_count = 0
            self.recent_events.clear()


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_count_passing_tests():
    """Lazy import of count_passing_tests."""
    global _count_passing_tests
    if _count_passing_tests is None:
        import sys
        root = Path(__file__).parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from progress import count_passing_tests
        _count_passing_tests = count_passing_tests
    return _count_passing_tests


class ConnectionManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        # project_name -> set of WebSocket connections
        self.active_connections: dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_name: str):
        """Accept a WebSocket connection for a project."""
        await websocket.accept()

        async with self._lock:
            if project_name not in self.active_connections:
                self.active_connections[project_name] = set()
            self.active_connections[project_name].add(websocket)

    async def disconnect(self, websocket: WebSocket, project_name: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if project_name in self.active_connections:
                self.active_connections[project_name].discard(websocket)
                if not self.active_connections[project_name]:
                    del self.active_connections[project_name]

    async def broadcast_to_project(self, project_name: str, message: dict):
        """Broadcast a message to all connections for a project."""
        async with self._lock:
            connections = list(self.active_connections.get(project_name, set()))

        dead_connections = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for connection in dead_connections:
                    if project_name in self.active_connections:
                        self.active_connections[project_name].discard(connection)

    def get_connection_count(self, project_name: str) -> int:
        """Get number of active connections for a project."""
        return len(self.active_connections.get(project_name, set()))


# Global connection manager
manager = ConnectionManager()

# Root directory
ROOT_DIR = Path(__file__).parent.parent


def validate_project_name(name: str) -> bool:
    """Validate project name to prevent path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,50}$', name))


async def poll_progress(websocket: WebSocket, project_name: str, project_dir: Path):
    """Poll database for progress changes and send updates."""
    count_passing_tests = _get_count_passing_tests()
    last_passing = -1
    last_in_progress = -1
    last_total = -1

    while True:
        try:
            passing, in_progress, total = count_passing_tests(project_dir)

            # Only send if changed
            if passing != last_passing or in_progress != last_in_progress or total != last_total:
                last_passing = passing
                last_in_progress = in_progress
                last_total = total
                percentage = (passing / total * 100) if total > 0 else 0

                await websocket.send_json({
                    "type": "progress",
                    "passing": passing,
                    "in_progress": in_progress,
                    "total": total,
                    "percentage": round(percentage, 1),
                })

            await asyncio.sleep(2)  # Poll every 2 seconds
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Progress polling error: {e}")
            break


async def project_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for project updates.

    Streams:
    - Progress updates (passing/total counts)
    - Agent status changes
    - Agent stdout/stderr lines
    """
    if not validate_project_name(project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    await manager.connect(websocket, project_name)

    # Get agent manager and register callbacks
    agent_manager = get_manager(project_name, project_dir, ROOT_DIR)

    # Create agent tracker for multi-agent mode
    agent_tracker = AgentTracker()

    # Create orchestrator tracker for observability
    orchestrator_tracker = OrchestratorTracker()

    async def on_output(line: str):
        """Handle agent output - broadcast to this WebSocket."""
        try:
            # Extract feature ID from line if present
            feature_id = None
            agent_index = None
            match = FEATURE_ID_PATTERN.match(line)
            if match:
                feature_id = int(match.group(1))
                agent_index, _ = await agent_tracker.get_agent_info(feature_id)

            # Send the raw log line with optional feature/agent attribution
            log_msg = {
                "type": "log",
                "line": line,
                "timestamp": datetime.now().isoformat(),
            }
            if feature_id is not None:
                log_msg["featureId"] = feature_id
            if agent_index is not None:
                log_msg["agentIndex"] = agent_index

            await websocket.send_json(log_msg)

            # Check if this line indicates agent activity (parallel mode)
            # and emit agent_update messages if so
            agent_update = await agent_tracker.process_line(line)
            if agent_update:
                await websocket.send_json(agent_update)

            # Also check for orchestrator events and emit orchestrator_update messages
            orch_update = await orchestrator_tracker.process_line(line)
            if orch_update:
                await websocket.send_json(orch_update)
        except Exception:
            pass  # Connection may be closed

    async def on_status_change(status: str):
        """Handle status change - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "agent_status",
                "status": status,
            })
            # Reset trackers when agent stops OR crashes to prevent ghost agents on restart
            if status in ("stopped", "crashed"):
                await agent_tracker.reset()
                await orchestrator_tracker.reset()
        except Exception:
            pass  # Connection may be closed

    # Register callbacks
    agent_manager.add_output_callback(on_output)
    agent_manager.add_status_callback(on_status_change)

    # Get dev server manager and register callbacks
    devserver_manager = get_devserver_manager(project_name, project_dir)

    async def on_dev_output(line: str):
        """Handle dev server output - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "dev_log",
                "line": line,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass  # Connection may be closed

    async def on_dev_status_change(status: str):
        """Handle dev server status change - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "dev_server_status",
                "status": status,
                "url": devserver_manager.detected_url,
            })
        except Exception:
            pass  # Connection may be closed

    # Register dev server callbacks
    devserver_manager.add_output_callback(on_dev_output)
    devserver_manager.add_status_callback(on_dev_status_change)

    # Start progress polling task
    poll_task = asyncio.create_task(poll_progress(websocket, project_name, project_dir))

    try:
        # Send initial agent status
        await websocket.send_json({
            "type": "agent_status",
            "status": agent_manager.status,
        })

        # Send initial dev server status
        await websocket.send_json({
            "type": "dev_server_status",
            "status": devserver_manager.status,
            "url": devserver_manager.detected_url,
        })

        # Send initial progress
        count_passing_tests = _get_count_passing_tests()
        passing, in_progress, total = count_passing_tests(project_dir)
        percentage = (passing / total * 100) if total > 0 else 0
        await websocket.send_json({
            "type": "progress",
            "passing": passing,
            "in_progress": in_progress,
            "total": total,
            "percentage": round(percentage, 1),
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any incoming messages (ping/pong, commands, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data[:100] if data else 'empty'}")
            except Exception as e:
                logger.warning(f"WebSocket error: {e}")
                break

    finally:
        # Clean up
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

        # Unregister agent callbacks
        agent_manager.remove_output_callback(on_output)
        agent_manager.remove_status_callback(on_status_change)

        # Unregister dev server callbacks
        devserver_manager.remove_output_callback(on_dev_output)
        devserver_manager.remove_status_callback(on_dev_status_change)

        # Disconnect from manager
        await manager.disconnect(websocket, project_name)
