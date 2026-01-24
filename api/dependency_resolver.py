"""
Dependency Resolver
===================

Provides dependency resolution using Kahn's algorithm for topological sorting.
Includes cycle detection, validation, and helper functions for dependency management.
"""

import heapq
from typing import TypedDict

# Security: Prevent DoS via excessive dependencies
MAX_DEPENDENCIES_PER_FEATURE = 20
MAX_DEPENDENCY_DEPTH = 50  # Prevent stack overflow in cycle detection


class DependencyResult(TypedDict):
    """Result from dependency resolution."""

    ordered_features: list[dict]
    circular_dependencies: list[list[int]]
    blocked_features: dict[int, list[int]]  # feature_id -> [blocking_ids]
    missing_dependencies: dict[int, list[int]]  # feature_id -> [missing_ids]


def resolve_dependencies(features: list[dict]) -> DependencyResult:
    """Topological sort using Kahn's algorithm with priority-aware ordering.

    Returns ordered features respecting dependencies, plus metadata about
    cycles, blocked features, and missing dependencies.

    Args:
        features: List of feature dicts with id, priority, passes, and dependencies fields

    Returns:
        DependencyResult with ordered_features, circular_dependencies,
        blocked_features, and missing_dependencies
    """
    feature_map = {f["id"]: f for f in features}
    in_degree = {f["id"]: 0 for f in features}
    adjacency: dict[int, list[int]] = {f["id"]: [] for f in features}
    blocked: dict[int, list[int]] = {}
    missing: dict[int, list[int]] = {}

    # Build graph
    for feature in features:
        deps = feature.get("dependencies") or []
        for dep_id in deps:
            if dep_id not in feature_map:
                missing.setdefault(feature["id"], []).append(dep_id)
            else:
                adjacency[dep_id].append(feature["id"])
                in_degree[feature["id"]] += 1
                # Track blocked features
                dep = feature_map[dep_id]
                if not dep.get("passes"):
                    blocked.setdefault(feature["id"], []).append(dep_id)

    # Kahn's algorithm with priority-aware selection using a heap
    # Heap entries are tuples: (priority, id, feature_dict) for stable ordering
    heap = [
        (f.get("priority", 999), f["id"], f)
        for f in features
        if in_degree[f["id"]] == 0
    ]
    heapq.heapify(heap)
    ordered: list[dict] = []

    while heap:
        _, _, current = heapq.heappop(heap)
        ordered.append(current)
        for dependent_id in adjacency[current["id"]]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                dep_feature = feature_map[dependent_id]
                heapq.heappush(
                    heap,
                    (dep_feature.get("priority", 999), dependent_id, dep_feature)
                )

    # Detect cycles (features not in ordered = part of cycle)
    cycles: list[list[int]] = []
    if len(ordered) < len(features):
        remaining = [f for f in features if f not in ordered]
        cycles = _detect_cycles(remaining, feature_map)
        ordered.extend(remaining)  # Add cyclic features at end

    return {
        "ordered_features": ordered,
        "circular_dependencies": cycles,
        "blocked_features": blocked,
        "missing_dependencies": missing,
    }


def are_dependencies_satisfied(
    feature: dict,
    all_features: list[dict],
    passing_ids: set[int] | None = None,
) -> bool:
    """Check if all dependencies have passes=True.

    Args:
        feature: Feature dict to check
        all_features: List of all feature dicts
        passing_ids: Optional pre-computed set of passing feature IDs.
            If None, will be computed from all_features. Pass this when
            calling in a loop to avoid O(n^2) complexity.

    Returns:
        True if all dependencies are satisfied (or no dependencies)
    """
    deps = feature.get("dependencies") or []
    if not deps:
        return True
    if passing_ids is None:
        passing_ids = {f["id"] for f in all_features if f.get("passes")}
    return all(dep_id in passing_ids for dep_id in deps)


def get_blocking_dependencies(
    feature: dict,
    all_features: list[dict],
    passing_ids: set[int] | None = None,
) -> list[int]:
    """Get list of incomplete dependency IDs.

    Args:
        feature: Feature dict to check
        all_features: List of all feature dicts
        passing_ids: Optional pre-computed set of passing feature IDs.
            If None, will be computed from all_features. Pass this when
            calling in a loop to avoid O(n^2) complexity.

    Returns:
        List of feature IDs that are blocking this feature
    """
    deps = feature.get("dependencies") or []
    if passing_ids is None:
        passing_ids = {f["id"] for f in all_features if f.get("passes")}
    return [dep_id for dep_id in deps if dep_id not in passing_ids]


def would_create_circular_dependency(
    features: list[dict], source_id: int, target_id: int
) -> bool:
    """Check if adding a dependency from target to source would create a cycle.

    Uses DFS with visited set for efficient cycle detection.

    Args:
        features: List of all feature dicts
        source_id: The feature that would gain the dependency
        target_id: The feature that would become a dependency

    Returns:
        True if adding the dependency would create a cycle
    """
    if source_id == target_id:
        return True  # Self-reference is a cycle

    feature_map = {f["id"]: f for f in features}
    source = feature_map.get(source_id)
    if not source:
        return False

    # Check if target already depends on source (direct or indirect)
    target = feature_map.get(target_id)
    if not target:
        return False

    # DFS from target to see if we can reach source
    visited: set[int] = set()

    def can_reach(current_id: int, depth: int = 0) -> bool:
        # Security: Prevent stack overflow with depth limit
        if depth > MAX_DEPENDENCY_DEPTH:
            return True  # Assume cycle if too deep (fail-safe)
        if current_id == source_id:
            return True
        if current_id in visited:
            return False
        visited.add(current_id)

        current = feature_map.get(current_id)
        if not current:
            return False

        deps = current.get("dependencies") or []
        for dep_id in deps:
            if can_reach(dep_id, depth + 1):
                return True
        return False

    return can_reach(target_id)


def validate_dependencies(
    feature_id: int, dependency_ids: list[int], all_feature_ids: set[int]
) -> tuple[bool, str]:
    """Validate dependency list.

    Args:
        feature_id: ID of the feature being validated
        dependency_ids: List of proposed dependency IDs
        all_feature_ids: Set of all valid feature IDs

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Security: Check limits
    if len(dependency_ids) > MAX_DEPENDENCIES_PER_FEATURE:
        return False, f"Maximum {MAX_DEPENDENCIES_PER_FEATURE} dependencies allowed"

    # Check self-reference
    if feature_id in dependency_ids:
        return False, "A feature cannot depend on itself"

    # Check all dependencies exist
    missing = [d for d in dependency_ids if d not in all_feature_ids]
    if missing:
        return False, f"Dependencies not found: {missing}"

    # Check for duplicates
    if len(dependency_ids) != len(set(dependency_ids)):
        return False, "Duplicate dependencies not allowed"

    return True, ""


def _detect_cycles(features: list[dict], feature_map: dict) -> list[list[int]]:
    """Detect cycles using DFS with recursion tracking.

    Args:
        features: List of features to check for cycles
        feature_map: Map of feature_id -> feature dict

    Returns:
        List of cycles, where each cycle is a list of feature IDs
    """
    cycles: list[list[int]] = []
    visited: set[int] = set()
    rec_stack: set[int] = set()
    path: list[int] = []

    def dfs(fid: int) -> bool:
        visited.add(fid)
        rec_stack.add(fid)
        path.append(fid)

        feature = feature_map.get(fid)
        if feature:
            for dep_id in feature.get("dependencies") or []:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    cycle_start = path.index(dep_id)
                    cycles.append(path[cycle_start:])
                    return True

        path.pop()
        rec_stack.remove(fid)
        return False

    for f in features:
        if f["id"] not in visited:
            dfs(f["id"])

    return cycles


def compute_scheduling_scores(features: list[dict]) -> dict[int, float]:
    """Compute scheduling scores for all features.

    Higher scores mean higher priority for scheduling. The algorithm considers:
    1. Unblocking potential - Features that unblock more downstream work score higher
    2. Depth in graph - Features with no dependencies (roots) are "shovel-ready"
    3. User priority - Existing priority field as tiebreaker

    Score formula: (1000 * unblock) + (100 * depth_score) + (10 * priority_factor)

    Args:
        features: List of feature dicts with id, priority, dependencies fields

    Returns:
        Dict mapping feature_id -> score (higher = schedule first)
    """
    if not features:
        return {}

    # Build adjacency lists
    children: dict[int, list[int]] = {f["id"]: [] for f in features}  # who depends on me
    parents: dict[int, list[int]] = {f["id"]: [] for f in features}   # who I depend on

    for f in features:
        for dep_id in (f.get("dependencies") or []):
            if dep_id in children:  # Only valid deps
                children[dep_id].append(f["id"])
                parents[f["id"]].append(dep_id)

    # Calculate depths via BFS from roots
    depths: dict[int, int] = {}
    roots = [f["id"] for f in features if not parents[f["id"]]]
    queue = [(root, 0) for root in roots]
    while queue:
        node_id, depth = queue.pop(0)
        if node_id not in depths or depth > depths[node_id]:
            depths[node_id] = depth
        for child_id in children[node_id]:
            queue.append((child_id, depth + 1))

    # Handle orphaned nodes (shouldn't happen but be safe)
    for f in features:
        if f["id"] not in depths:
            depths[f["id"]] = 0

    # Calculate transitive downstream counts (reverse topo order)
    downstream: dict[int, int] = {f["id"]: 0 for f in features}
    # Process in reverse depth order (leaves first)
    for fid in sorted(depths.keys(), key=lambda x: -depths[x]):
        for parent_id in parents[fid]:
            downstream[parent_id] += 1 + downstream[fid]

    # Normalize and compute scores
    max_depth = max(depths.values()) if depths else 0
    max_downstream = max(downstream.values()) if downstream else 0

    scores: dict[int, float] = {}
    for f in features:
        fid = f["id"]

        # Unblocking score: 0-1, higher = unblocks more
        unblock = downstream[fid] / max_downstream if max_downstream > 0 else 0

        # Depth score: 0-1, higher = closer to root (no deps)
        depth_score = 1 - (depths[fid] / max_depth) if max_depth > 0 else 1

        # Priority factor: 0-1, lower priority number = higher factor
        priority = f.get("priority", 999)
        priority_factor = (10 - min(priority, 10)) / 10

        scores[fid] = (1000 * unblock) + (100 * depth_score) + (10 * priority_factor)

    return scores


def get_ready_features(features: list[dict], limit: int = 10) -> list[dict]:
    """Get features that are ready to be worked on.

    A feature is ready if:
    - It is not passing
    - It is not in progress
    - All its dependencies are satisfied

    Args:
        features: List of all feature dicts
        limit: Maximum number of features to return

    Returns:
        List of ready features, sorted by priority
    """
    passing_ids = {f["id"] for f in features if f.get("passes")}

    ready = []
    for f in features:
        if f.get("passes") or f.get("in_progress"):
            continue
        deps = f.get("dependencies") or []
        if all(dep_id in passing_ids for dep_id in deps):
            ready.append(f)

    # Sort by scheduling score (higher = first), then priority, then id
    scores = compute_scheduling_scores(features)
    ready.sort(key=lambda f: (-scores.get(f["id"], 0), f.get("priority", 999), f["id"]))

    return ready[:limit]


def get_blocked_features(features: list[dict]) -> list[dict]:
    """Get features that are blocked by unmet dependencies.

    Args:
        features: List of all feature dicts

    Returns:
        List of blocked features with 'blocked_by' field added
    """
    passing_ids = {f["id"] for f in features if f.get("passes")}

    blocked = []
    for f in features:
        if f.get("passes"):
            continue
        deps = f.get("dependencies") or []
        blocking = [d for d in deps if d not in passing_ids]
        if blocking:
            blocked.append({**f, "blocked_by": blocking})

    return blocked


def build_graph_data(features: list[dict]) -> dict:
    """Build graph data structure for visualization.

    Args:
        features: List of all feature dicts

    Returns:
        Dict with 'nodes' and 'edges' for graph visualization
    """
    passing_ids = {f["id"] for f in features if f.get("passes")}

    nodes = []
    edges = []

    for f in features:
        deps = f.get("dependencies") or []
        blocking = [d for d in deps if d not in passing_ids]

        if f.get("passes"):
            status = "done"
        elif blocking:
            status = "blocked"
        elif f.get("in_progress"):
            status = "in_progress"
        else:
            status = "pending"

        nodes.append({
            "id": f["id"],
            "name": f["name"],
            "category": f["category"],
            "status": status,
            "priority": f.get("priority", 999),
            "dependencies": deps,
        })

        for dep_id in deps:
            edges.append({"source": dep_id, "target": f["id"]})

    return {"nodes": nodes, "edges": edges}
