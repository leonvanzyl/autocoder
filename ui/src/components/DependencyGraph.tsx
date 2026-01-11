import { useMemo, useState } from 'react'
import { Lock, CheckCircle2, Circle, Loader2, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'
import type { DependencyGraph as DependencyGraphType, DependencyNode, DependencyEdge } from '../lib/types'

interface DependencyGraphProps {
  graph: DependencyGraphType
  onNodeClick?: (nodeId: number) => void
  highlightNodeId?: number | null
}

// Node dimensions
const NODE_WIDTH = 180
const NODE_HEIGHT = 60
const NODE_MARGIN_X = 40
const NODE_MARGIN_Y = 30

// Get status color
function getStatusColor(status: DependencyNode['status']): string {
  switch (status) {
    case 'done':
      return 'var(--color-neo-done)'
    case 'in_progress':
      return 'var(--color-neo-progress)'
    case 'blocked':
      return '#ef4444' // red-500
    case 'pending':
    default:
      return 'var(--color-neo-pending)'
  }
}

// Get status icon
function StatusIcon({ status }: { status: DependencyNode['status'] }) {
  switch (status) {
    case 'done':
      return <CheckCircle2 size={14} />
    case 'in_progress':
      return <Loader2 size={14} className="animate-spin" />
    case 'blocked':
      return <Lock size={14} />
    case 'pending':
    default:
      return <Circle size={14} />
  }
}

// Calculate node positions using a simple layered layout
function calculateLayout(nodes: DependencyNode[], edges: DependencyEdge[]) {
  // Build adjacency list
  const children = new Map<number, Set<number>>()
  const parents = new Map<number, Set<number>>()

  for (const node of nodes) {
    children.set(node.id, new Set())
    parents.set(node.id, new Set())
  }

  for (const edge of edges) {
    children.get(edge.from)?.add(edge.to)
    parents.get(edge.to)?.add(edge.from)
  }

  // Find nodes with no parents (roots)
  const roots = nodes.filter(n => (parents.get(n.id)?.size ?? 0) === 0)

  // BFS to assign layers
  const layers = new Map<number, number>()
  const queue: number[] = []

  for (const root of roots) {
    layers.set(root.id, 0)
    queue.push(root.id)
  }

  // Handle nodes that might not be reachable from roots
  for (const node of nodes) {
    if (!layers.has(node.id)) {
      layers.set(node.id, 0)
      queue.push(node.id)
    }
  }

  while (queue.length > 0) {
    const nodeId = queue.shift()!
    const currentLayer = layers.get(nodeId) ?? 0

    for (const childId of children.get(nodeId) ?? []) {
      const existingLayer = layers.get(childId) ?? -1
      if (existingLayer < currentLayer + 1) {
        layers.set(childId, currentLayer + 1)
        queue.push(childId)
      }
    }
  }

  // Group nodes by layer
  const layerGroups = new Map<number, number[]>()
  for (const [nodeId, layer] of layers) {
    if (!layerGroups.has(layer)) {
      layerGroups.set(layer, [])
    }
    layerGroups.get(layer)!.push(nodeId)
  }

  // Calculate positions
  const positions = new Map<number, { x: number; y: number }>()
  const maxLayer = Math.max(...layers.values(), 0)

  for (let layer = 0; layer <= maxLayer; layer++) {
    const nodesInLayer = layerGroups.get(layer) ?? []
    const layerWidth = nodesInLayer.length * (NODE_WIDTH + NODE_MARGIN_X) - NODE_MARGIN_X
    const startX = -layerWidth / 2

    nodesInLayer.forEach((nodeId, index) => {
      positions.set(nodeId, {
        x: startX + index * (NODE_WIDTH + NODE_MARGIN_X) + NODE_WIDTH / 2,
        y: layer * (NODE_HEIGHT + NODE_MARGIN_Y) + NODE_HEIGHT / 2,
      })
    })
  }

  // Calculate bounds
  const xs = [...positions.values()].map(p => p.x)
  const ys = [...positions.values()].map(p => p.y)

  const bounds = {
    minX: Math.min(...xs) - NODE_WIDTH / 2 - 20,
    maxX: Math.max(...xs) + NODE_WIDTH / 2 + 20,
    minY: Math.min(...ys) - NODE_HEIGHT / 2 - 20,
    maxY: Math.max(...ys) + NODE_HEIGHT / 2 + 20,
  }

  return { positions, bounds }
}

export function DependencyGraph({ graph, onNodeClick, highlightNodeId }: DependencyGraphProps) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })

  const { positions, bounds } = useMemo(
    () => calculateLayout(graph.nodes, graph.edges),
    [graph.nodes, graph.edges]
  )

  const width = bounds.maxX - bounds.minX
  const height = bounds.maxY - bounds.minY

  // Node map for quick lookup
  const nodeMap = useMemo(
    () => new Map(graph.nodes.map(n => [n.id, n])),
    [graph.nodes]
  )

  if (graph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--color-neo-text-secondary)]">
        No tasks to display
      </div>
    )
  }

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 2))
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.5))
  const handleReset = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  return (
    <div className="relative w-full h-full min-h-[400px] bg-[var(--color-neo-bg)] rounded-lg border-2 border-[var(--color-neo-border)]">
      {/* Controls */}
      <div className="absolute top-2 right-2 flex gap-1 z-10">
        <button
          onClick={handleZoomIn}
          className="neo-button p-2"
          title="Zoom in"
        >
          <ZoomIn size={16} />
        </button>
        <button
          onClick={handleZoomOut}
          className="neo-button p-2"
          title="Zoom out"
        >
          <ZoomOut size={16} />
        </button>
        <button
          onClick={handleReset}
          className="neo-button p-2"
          title="Reset view"
        >
          <Maximize2 size={16} />
        </button>
      </div>

      {/* Graph SVG */}
      <svg
        width="100%"
        height="100%"
        viewBox={`${bounds.minX - pan.x / zoom} ${bounds.minY - pan.y / zoom} ${width / zoom} ${height / zoom}`}
        className="cursor-move"
        style={{ minHeight: '400px' }}
      >
        {/* Edges */}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon
              points="0 0, 10 3.5, 0 7"
              fill="var(--color-neo-border)"
            />
          </marker>
        </defs>

        {graph.edges.map((edge, i) => {
          const fromPos = positions.get(edge.from)
          const toPos = positions.get(edge.to)

          if (!fromPos || !toPos) return null

          const fromNode = nodeMap.get(edge.from)
          const isHighlighted =
            highlightNodeId === edge.from || highlightNodeId === edge.to

          return (
            <line
              key={`edge-${i}`}
              x1={fromPos.x}
              y1={fromPos.y + NODE_HEIGHT / 2 - 5}
              x2={toPos.x}
              y2={toPos.y - NODE_HEIGHT / 2 + 5}
              stroke={isHighlighted ? getStatusColor(fromNode?.status ?? 'pending') : 'var(--color-neo-border)'}
              strokeWidth={isHighlighted ? 3 : 2}
              markerEnd="url(#arrowhead)"
            />
          )
        })}

        {/* Nodes */}
        {graph.nodes.map(node => {
          const pos = positions.get(node.id)
          if (!pos) return null

          const isHighlighted = highlightNodeId === node.id
          const statusColor = getStatusColor(node.status)

          return (
            <g
              key={`node-${node.id}`}
              transform={`translate(${pos.x - NODE_WIDTH / 2}, ${pos.y - NODE_HEIGHT / 2})`}
              onClick={() => onNodeClick?.(node.id)}
              className="cursor-pointer"
            >
              {/* Node background */}
              <rect
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={8}
                fill="var(--color-neo-card)"
                stroke={isHighlighted ? statusColor : 'var(--color-neo-border)'}
                strokeWidth={isHighlighted ? 3 : 2}
              />

              {/* Status indicator bar */}
              <rect
                width={NODE_WIDTH}
                height={6}
                rx={3}
                y={NODE_HEIGHT - 8}
                fill={statusColor}
              />

              {/* Node content */}
              <foreignObject width={NODE_WIDTH} height={NODE_HEIGHT - 10}>
                <div className="p-2 h-full flex flex-col justify-center">
                  <div className="flex items-center gap-1 mb-1">
                    <span style={{ color: statusColor }}>
                      <StatusIcon status={node.status} />
                    </span>
                    <span className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                      #{node.priority}
                    </span>
                  </div>
                  <div
                    className="text-xs font-bold line-clamp-2 leading-tight"
                    title={node.name}
                  >
                    {node.name}
                  </div>
                </div>
              </foreignObject>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 text-xs bg-[var(--color-neo-card)] p-2 rounded border border-[var(--color-neo-border)]">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--color-neo-pending)' }} />
          Pending
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--color-neo-progress)' }} />
          In Progress
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: '#ef4444' }} />
          Blocked
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: 'var(--color-neo-done)' }} />
          Done
        </span>
      </div>
    </div>
  )
}
