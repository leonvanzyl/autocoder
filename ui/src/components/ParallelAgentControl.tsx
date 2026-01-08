import { useState } from 'react'
import {
  Play,
  Pause,
  Square,
  Loader2,
  Zap,
  Users,
  Bot,
  Trash2,
  Minus,
  Plus,
} from 'lucide-react'
import {
  useParallelAgentsStatus,
  useStartParallelAgents,
  useStopParallelAgents,
  usePauseParallelAgents,
  useResumeParallelAgents,
  useCleanupParallelAgents,
} from '../hooks/useProjects'
import type { ParallelAgentInfo } from '../lib/types'

interface ParallelAgentControlProps {
  projectName: string
  onModeChange?: (isParallel: boolean) => void
}

// Agent colors matching FeatureCard.tsx
const AGENT_COLORS = [
  '#00b4d8', // cyan - agent-1
  '#70e000', // green - agent-2
  '#8338ec', // purple - agent-3
  '#ff5400', // orange - agent-4
  '#ff006e', // pink - agent-5
  '#3a86ff', // blue - agent-6
  '#ffd60a', // yellow - agent-7
  '#06d6a0', // teal - agent-8
  '#ef476f', // red - agent-9
  '#118ab2', // dark cyan - agent-10
]

function getAgentColor(agentId: string): string {
  const match = agentId.match(/\d+/)
  if (match) {
    const num = parseInt(match[0], 10) - 1
    return AGENT_COLORS[num % AGENT_COLORS.length]
  }
  return AGENT_COLORS[0]
}

export function ParallelAgentControl({
  projectName,
  onModeChange,
}: ParallelAgentControlProps) {
  const [numAgents, setNumAgents] = useState(2)
  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [isParallelMode, setIsParallelMode] = useState(false)

  const { data: status, isLoading: statusLoading } = useParallelAgentsStatus(
    isParallelMode ? projectName : null
  )

  const startAgents = useStartParallelAgents(projectName)
  const stopAgents = useStopParallelAgents(projectName)
  const pauseAgents = usePauseParallelAgents(projectName)
  const resumeAgents = useResumeParallelAgents(projectName)
  const cleanupAgents = useCleanupParallelAgents(projectName)

  const isLoading =
    startAgents.isPending ||
    stopAgents.isPending ||
    pauseAgents.isPending ||
    resumeAgents.isPending ||
    cleanupAgents.isPending

  const runningCount = status?.agents.filter(a => a.status === 'running').length ?? 0
  const pausedCount = status?.agents.filter(a => a.status === 'paused').length ?? 0
  const hasAgents = (status?.agents.length ?? 0) > 0
  const hasRunningAgents = runningCount > 0
  const hasPausedAgents = pausedCount > 0
  const allPaused = hasAgents && pausedCount === status?.agents.length
  const allStopped = hasAgents && runningCount === 0 && pausedCount === 0

  // Show start controls when no agents exist OR all agents are stopped
  const showStartControls = !hasAgents || allStopped

  const handleToggleMode = () => {
    const newMode = !isParallelMode
    setIsParallelMode(newMode)
    onModeChange?.(newMode)
  }

  const handleStart = () => {
    startAgents.mutate({ numAgents, yoloMode: yoloEnabled })
  }

  const handleStop = () => {
    stopAgents.mutate()
  }

  const handlePause = () => {
    pauseAgents.mutate()
  }

  const handleResume = () => {
    resumeAgents.mutate()
  }

  const handleCleanup = () => {
    cleanupAgents.mutate()
  }

  // Collapsed state - just show button
  if (!isParallelMode) {
    return (
      <button
        onClick={handleToggleMode}
        className="neo-btn neo-btn-secondary text-sm py-2 px-3 flex items-center gap-2"
        title="Switch to Parallel Agents Mode"
      >
        <Users size={16} />
        <span className="hidden sm:inline">Parallel</span>
      </button>
    )
  }

  // Expanded state
  return (
    <div className="flex flex-col gap-3 p-4 bg-white border-3 border-[var(--color-neo-border)] shadow-neo">
      {/* Header with Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users size={18} className="text-[var(--color-neo-primary)]" />
          <span className="font-display font-bold text-sm uppercase">
            Parallel Agents
          </span>

          {/* Status Indicator */}
          {hasAgents && (
            <StatusIndicator
              runningCount={runningCount}
              pausedCount={pausedCount}
              totalCount={status?.agents.length ?? 0}
            />
          )}

          {/* YOLO Badge when running */}
          {hasAgents && yoloEnabled && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-pending)] border-2 border-yellow-600 rounded">
              <Zap size={12} className="text-yellow-900" />
              <span className="text-xs font-bold text-yellow-900">YOLO</span>
            </div>
          )}
        </div>

        <button
          onClick={handleToggleMode}
          className="text-xs text-[var(--color-neo-text-secondary)] hover:text-[var(--color-neo-text)] underline"
        >
          Single Mode
        </button>
      </div>

      {/* Agent Status Grid */}
      {status && status.agents.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {status.agents.map((agent) => (
            <AgentStatusBadge key={agent.agent_id} agent={agent} />
          ))}
        </div>
      )}

      {/* Controls */}
      {showStartControls ? (
        // No agents or all stopped - show start controls
        <div className="flex flex-col gap-2">
          {/* Agent Count Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Agents:</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setNumAgents(Math.max(1, numAgents - 1))}
                className="neo-btn neo-btn-secondary p-1"
                disabled={numAgents <= 1}
              >
                <Minus size={14} />
              </button>
              <span className="w-8 text-center font-bold text-lg">{numAgents}</span>
              <button
                onClick={() => setNumAgents(Math.min(10, numAgents + 1))}
                className="neo-btn neo-btn-secondary p-1"
                disabled={numAgents >= 10}
              >
                <Plus size={14} />
              </button>
            </div>

            {/* YOLO Toggle */}
            <button
              onClick={() => setYoloEnabled(!yoloEnabled)}
              className={`neo-btn text-sm py-1 px-2 ml-auto flex items-center gap-1 ${
                yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'
              }`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={14} className={yoloEnabled ? 'text-yellow-900' : ''} />
              <span className={`text-xs font-bold ${yoloEnabled ? 'text-yellow-900' : ''}`}>
                YOLO
              </span>
            </button>
          </div>

          {/* Start Button */}
          <button
            onClick={handleStart}
            disabled={isLoading}
            className="neo-btn neo-btn-success text-sm py-2 px-4 flex items-center justify-center gap-2"
          >
            {startAgents.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                <Play size={16} />
                Start {numAgents} Agent{numAgents !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      ) : (
        // Has agents - show control buttons
        <div className="flex flex-col gap-2">
          {/* Primary Action Buttons */}
          <div className="flex gap-2">
            {/* Pause/Resume Button */}
            {hasRunningAgents && !allPaused ? (
              <button
                onClick={handlePause}
                disabled={isLoading}
                className="neo-btn neo-btn-warning text-sm py-2 px-3 flex items-center gap-1 flex-1"
                title="Pause All Agents"
              >
                {pauseAgents.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Pause size={14} />
                )}
                <span>Pause</span>
              </button>
            ) : hasPausedAgents ? (
              <button
                onClick={handleResume}
                disabled={isLoading}
                className="neo-btn neo-btn-success text-sm py-2 px-3 flex items-center gap-1 flex-1"
                title="Resume All Agents"
              >
                {resumeAgents.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Play size={14} />
                )}
                <span>Resume</span>
              </button>
            ) : null}

            {/* Stop Button */}
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3 flex items-center gap-1 flex-1"
              title="Stop All Agents"
            >
              {stopAgents.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Square size={14} />
              )}
              <span>Stop</span>
            </button>
          </div>

          {/* Secondary Action Button */}
          <div className="flex gap-2">
            <button
              onClick={handleCleanup}
              disabled={isLoading}
              className="neo-btn neo-btn-secondary text-sm py-2 px-3 flex items-center gap-1 flex-1"
              title="Stop All & Cleanup Worktrees"
            >
              {cleanupAgents.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Trash2 size={14} />
              )}
              <span>Cleanup</span>
            </button>
          </div>
        </div>
      )}

      {/* Status Loading */}
      {statusLoading && !status && (
        <div className="flex items-center justify-center py-2">
          <Loader2 size={16} className="animate-spin text-[var(--color-neo-text-secondary)]" />
        </div>
      )}
    </div>
  )
}

function StatusIndicator({
  runningCount,
  pausedCount,
  totalCount
}: {
  runningCount: number
  pausedCount: number
  totalCount: number
}) {
  const stoppedCount = totalCount - runningCount - pausedCount

  let color: string
  let label: string
  let pulse = false

  if (runningCount > 0) {
    color = 'var(--color-neo-done)'
    label = `${runningCount} Running`
    pulse = true
  } else if (pausedCount > 0) {
    color = 'var(--color-neo-pending)'
    label = `${pausedCount} Paused`
  } else {
    color = 'var(--color-neo-text-secondary)'
    label = `${stoppedCount} Stopped`
  }

  return (
    <div className="flex items-center gap-2 px-2 py-1 bg-white border-2 border-[var(--color-neo-border)] rounded">
      <span
        className={`w-2 h-2 rounded-full ${pulse ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: color }}
      />
      <span
        className="text-xs font-bold uppercase"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  )
}

function AgentStatusBadge({ agent }: { agent: ParallelAgentInfo }) {
  const color = getAgentColor(agent.agent_id)
  const statusColors: Record<string, string> = {
    running: 'var(--color-neo-done)',
    paused: 'var(--color-neo-pending)',
    stopped: 'var(--color-neo-text-secondary)',
    crashed: 'var(--color-neo-danger)',
    unknown: 'var(--color-neo-text-secondary)',
  }

  const statusColor = statusColors[agent.status] || statusColors.unknown
  const agentNum = agent.agent_id.replace('agent-', '#')

  return (
    <div
      className="flex flex-col items-center gap-1 p-2 rounded border-2"
      style={{ borderColor: color }}
      title={`${agent.agent_id}: ${agent.status}${agent.worktree_path ? `\nWorktree: ${agent.worktree_path}` : ''}`}
    >
      <Bot size={16} style={{ color }} />
      <span className="text-xs font-bold" style={{ color }}>
        {agentNum}
      </span>
      <span
        className={`w-2 h-2 rounded-full ${agent.status === 'running' ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: statusColor }}
      />
    </div>
  )
}
