import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  Position,
  MarkerType,
  ConnectionMode,
  Handle,
} from '@xyflow/react'
import dagre from 'dagre'
import { CheckCircle2, Circle, Loader2, AlertTriangle, RefreshCw } from 'lucide-react'
import type { DependencyGraph as DependencyGraphData, GraphNode, ActiveAgent, AgentMascot, AgentState } from '../lib/types'
import { AgentAvatar } from './AgentAvatar'
import '@xyflow/react/dist/style.css'

// Node dimensions
const NODE_WIDTH = 220
const NODE_HEIGHT = 80

interface DependencyGraphProps {
  graphData: DependencyGraphData
  onNodeClick?: (nodeId: number) => void
  activeAgents?: ActiveAgent[]
}

// Agent info to display on a node
interface NodeAgentInfo {
  name: AgentMascot | 'Unknown'
  state: AgentState
}

// Error boundary to catch and recover from ReactFlow rendering errors
interface ErrorBoundaryProps {
  children: ReactNode
  onReset?: () => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class GraphErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('DependencyGraph error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full w-full flex items-center justify-center bg-neo-neutral-100">
          <div className="text-center p-6">
            <AlertTriangle size={48} className="mx-auto mb-4 text-neo-warning" />
            <div className="text-neo-text font-bold mb-2">Graph rendering error</div>
            <div className="text-sm text-neo-text-secondary mb-4">
              The dependency graph encountered an issue.
            </div>
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 px-4 py-2 bg-neo-accent text-white rounded border-2 border-neo-border shadow-neo-sm hover:shadow-neo-md transition-all"
            >
              <RefreshCw size={16} />
              Reload Graph
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

// Custom node component
function FeatureNode({ data }: { data: GraphNode & { onClick?: () => void; agent?: NodeAgentInfo } }) {
  const statusColors = {
    pending: 'bg-neo-pending border-neo-border',
    in_progress: 'bg-neo-progress border-neo-border',
    done: 'bg-neo-done border-neo-border',
    blocked: 'bg-neo-danger/20 border-neo-danger',
  }

  const StatusIcon = () => {
    switch (data.status) {
      case 'done':
        return <CheckCircle2 size={16} className="text-neo-text-on-bright" />
      case 'in_progress':
        return <Loader2 size={16} className="text-neo-text-on-bright animate-spin" />
      case 'blocked':
        return <AlertTriangle size={16} className="text-neo-danger" />
      default:
        return <Circle size={16} className="text-neo-text-on-bright" />
    }
  }

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-neo-border !w-2 !h-2" />
      <div
        className={`
          px-4 py-3 rounded-lg border-2 cursor-pointer
          transition-all hover:shadow-neo-md relative
          ${statusColors[data.status]}
        `}
        onClick={data.onClick}
        style={{ minWidth: NODE_WIDTH - 20, maxWidth: NODE_WIDTH }}
      >
        {/* Agent avatar badge - positioned at top right */}
        {data.agent && (
          <div className="absolute -top-3 -right-3 z-10">
            <div className="rounded-full border-2 border-neo-border bg-white shadow-neo-sm">
              <AgentAvatar name={data.agent.name} state={data.agent.state} size="sm" />
            </div>
          </div>
        )}
        <div className="flex items-center gap-2 mb-1">
          <StatusIcon />
          <span className="text-xs font-mono text-neo-text-on-bright/70">
            #{data.priority}
          </span>
          {/* Show agent name inline if present */}
          {data.agent && (
            <span className="text-xs font-bold text-neo-text-on-bright ml-auto">
              {data.agent.name}
            </span>
          )}
        </div>
        <div className="font-bold text-sm text-neo-text-on-bright truncate" title={data.name}>
          {data.name}
        </div>
        <div className="text-xs text-neo-text-on-bright/70 truncate" title={data.category}>
          {data.category}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-neo-border !w-2 !h-2" />
    </>
  )
}

const nodeTypes = {
  feature: FeatureNode,
}

// Layout nodes using dagre
function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'LR'
): { nodes: Node[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const isHorizontal = direction === 'LR'
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 100,
    marginx: 50,
    marginy: 50,
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
    }
  })

  return { nodes: layoutedNodes, edges }
}

function DependencyGraphInner({ graphData, onNodeClick, activeAgents = [] }: DependencyGraphProps) {
  const [direction, setDirection] = useState<'TB' | 'LR'>('LR')

  // Use ref for callback to avoid triggering re-renders when callback identity changes
  const onNodeClickRef = useRef(onNodeClick)
  useEffect(() => {
    onNodeClickRef.current = onNodeClick
  }, [onNodeClick])

  // Create a stable click handler that uses the ref
  const handleNodeClick = useCallback((nodeId: number) => {
    onNodeClickRef.current?.(nodeId)
  }, [])

  // Create a map of featureId to agent info for quick lookup
  const agentByFeatureId = useMemo(() => {
    const map = new Map<number, NodeAgentInfo>()
    for (const agent of activeAgents) {
      map.set(agent.featureId, { name: agent.agentName, state: agent.state })
    }
    return map
  }, [activeAgents])

  // Convert graph data to React Flow format
  // Only recalculate when graphData or direction changes (not when onNodeClick changes)
  const initialElements = useMemo(() => {
    const nodes: Node[] = graphData.nodes.map((node) => ({
      id: String(node.id),
      type: 'feature',
      position: { x: 0, y: 0 },
      data: {
        ...node,
        onClick: () => handleNodeClick(node.id),
        agent: agentByFeatureId.get(node.id),
      },
    }))

    const edges: Edge[] = graphData.edges.map((edge, index) => ({
      id: `e${edge.source}-${edge.target}-${index}`,
      source: String(edge.source),
      target: String(edge.target),
      type: 'smoothstep',
      animated: false,
      style: { stroke: 'var(--color-neo-border)', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: 'var(--color-neo-border)',
      },
    }))

    return getLayoutedElements(nodes, edges, direction)
  }, [graphData, direction, handleNodeClick, agentByFeatureId])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialElements.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialElements.edges)

  // Update layout when initialElements changes
  // Using a ref to track previous graph data to avoid unnecessary updates
  const prevGraphDataRef = useRef<string>('')
  const prevDirectionRef = useRef<'TB' | 'LR'>(direction)

  useEffect(() => {
    // Create a simple hash of the graph data to detect actual changes
    // Include agent assignments so nodes update when agents change
    const agentInfo = Array.from(agentByFeatureId.entries()).map(([id, agent]) => ({
      featureId: id,
      agentName: agent.name,
      agentState: agent.state,
    }))
    const graphHash = JSON.stringify({
      nodes: graphData.nodes.map(n => ({ id: n.id, status: n.status })),
      edges: graphData.edges,
      agents: agentInfo,
    })

    // Only update if graph data or direction actually changed
    if (graphHash !== prevGraphDataRef.current || direction !== prevDirectionRef.current) {
      prevGraphDataRef.current = graphHash
      prevDirectionRef.current = direction

      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        initialElements.nodes,
        initialElements.edges,
        direction
      )
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    }
  }, [graphData, direction, setNodes, setEdges, initialElements, agentByFeatureId])

  const onLayout = useCallback(
    (newDirection: 'TB' | 'LR') => {
      setDirection(newDirection)
    },
    []
  )

  // Color nodes for minimap
  const nodeColor = useCallback((node: Node) => {
    const status = (node.data as unknown as GraphNode).status
    switch (status) {
      case 'done':
        return 'var(--color-neo-done)'
      case 'in_progress':
        return 'var(--color-neo-progress)'
      case 'blocked':
        return 'var(--color-neo-danger)'
      default:
        return 'var(--color-neo-pending)'
    }
  }, [])

  if (graphData.nodes.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-neo-neutral-100">
        <div className="text-center">
          <div className="text-neo-text-secondary mb-2">No features to display</div>
          <div className="text-sm text-neo-text-muted">
            Create features to see the dependency graph
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full relative bg-neo-neutral-50">
      {/* Layout toggle */}
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <button
          onClick={() => onLayout('LR')}
          className={`
            px-3 py-1.5 text-sm font-medium rounded border-2 border-neo-border transition-all
            ${direction === 'LR'
              ? 'bg-neo-accent text-white shadow-neo-sm'
              : 'bg-white text-neo-text hover:bg-neo-neutral-100'
            }
          `}
        >
          Horizontal
        </button>
        <button
          onClick={() => onLayout('TB')}
          className={`
            px-3 py-1.5 text-sm font-medium rounded border-2 border-neo-border transition-all
            ${direction === 'TB'
              ? 'bg-neo-accent text-white shadow-neo-sm'
              : 'bg-white text-neo-text hover:bg-neo-neutral-100'
            }
          `}
        >
          Vertical
        </button>
      </div>

      {/* Legend */}
      <div className="absolute top-4 right-4 z-10 bg-white border-2 border-neo-border rounded-lg p-3 shadow-neo-sm">
        <div className="text-xs font-bold mb-2">Status</div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-neo-pending border border-neo-border" />
            <span>Pending</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-neo-progress border border-neo-border" />
            <span>In Progress</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-neo-done border border-neo-border" />
            <span>Done</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded bg-neo-danger/20 border border-neo-danger" />
            <span>Blocked</span>
          </div>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color="var(--color-neo-neutral-300)" gap={20} size={1} />
        <Controls
          className="!bg-white !border-2 !border-neo-border !rounded-lg !shadow-neo-sm"
          showInteractive={false}
        />
        <MiniMap
          nodeColor={nodeColor}
          className="!bg-white !border-2 !border-neo-border !rounded-lg !shadow-neo-sm"
          maskColor="rgba(0, 0, 0, 0.1)"
        />
      </ReactFlow>
    </div>
  )
}

// Wrapper component with error boundary for stability
export function DependencyGraph({ graphData, onNodeClick, activeAgents }: DependencyGraphProps) {
  // Use a key based on graph data length to force remount on structural changes
  // This helps recover from corrupted ReactFlow state
  const [resetKey, setResetKey] = useState(0)

  const handleReset = useCallback(() => {
    setResetKey(k => k + 1)
  }, [])

  return (
    <GraphErrorBoundary key={resetKey} onReset={handleReset}>
      <DependencyGraphInner graphData={graphData} onNodeClick={onNodeClick} activeAgents={activeAgents} />
    </GraphErrorBoundary>
  )
}
