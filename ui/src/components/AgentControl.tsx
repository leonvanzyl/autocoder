import { useState } from 'react'
import { Play, Pause, Square, Loader2, Zap, Users } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  usePauseAgent,
  useResumeAgent,
} from '../hooks/useProjects'
import type { AgentStatus } from '../lib/types'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
  yoloMode?: boolean  // From server status - whether currently running in YOLO mode
  parallelWorkers?: number | null  // From server status - current worker count
}

export function AgentControl({ projectName, status, yoloMode = false, parallelWorkers = null }: AgentControlProps) {
  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [workerCount, setWorkerCount] = useState<number | null>(null)  // null = single agent

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const pauseAgent = usePauseAgent(projectName)
  const resumeAgent = useResumeAgent(projectName)

  const isLoading =
    startAgent.isPending ||
    stopAgent.isPending ||
    pauseAgent.isPending ||
    resumeAgent.isPending

  const handleStart = () => startAgent.mutate({ yoloMode: yoloEnabled, parallelWorkers: workerCount })
  const handleStop = () => stopAgent.mutate()
  const handlePause = () => pauseAgent.mutate()
  const handleResume = () => resumeAgent.mutate()

  return (
    <div className="flex items-center gap-2">
      {/* Status Indicator */}
      <StatusIndicator status={status} />

      {/* YOLO Mode Indicator - shown when running in YOLO mode */}
      {(status === 'running' || status === 'paused') && yoloMode && (
        <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
          <Zap size={14} className="text-yellow-900" />
          <span className="font-display font-bold text-xs uppercase text-yellow-900">
            YOLO
          </span>
        </div>
      )}

      {/* Parallel Workers Indicator - shown when running with multiple workers */}
      {(status === 'running' || status === 'paused') && parallelWorkers && parallelWorkers > 1 && (
        <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-progress)] border-3 border-[var(--color-neo-border)]">
          <Users size={14} className="text-cyan-900" />
          <span className="font-display font-bold text-xs uppercase text-cyan-900">
            {parallelWorkers}x
          </span>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex gap-1">
        {status === 'stopped' || status === 'crashed' ? (
          <>
            {/* YOLO Toggle - only shown when stopped */}
            <button
              onClick={() => setYoloEnabled(!yoloEnabled)}
              className={`neo-btn text-sm py-2 px-3 ${
                yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'
              }`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={18} className={yoloEnabled ? 'text-yellow-900' : ''} />
            </button>
            {/* Parallel Workers Selector - cycles through 1/3/5 */}
            <button
              onClick={() => {
                // Cycle: null(1) -> 3 -> 5 -> null(1)
                if (workerCount === null) setWorkerCount(3)
                else if (workerCount === 3) setWorkerCount(5)
                else setWorkerCount(null)
              }}
              className={`neo-btn text-sm py-2 px-3 ${
                workerCount !== null ? 'neo-btn-info' : 'neo-btn-secondary'
              }`}
              title={`Parallel Workers: ${workerCount ?? 1} (click to cycle 1→3→5)`}
            >
              <Users size={18} className={workerCount !== null ? 'text-cyan-900' : ''} />
              {workerCount !== null && (
                <span className="ml-1 font-bold text-xs">{workerCount}</span>
              )}
            </button>
            <button
              onClick={handleStart}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3"
              title={
                workerCount !== null
                  ? `Start ${workerCount} Parallel Agents${yoloEnabled ? ' (YOLO Mode)' : ''}`
                  : yoloEnabled ? 'Start Agent (YOLO Mode)' : 'Start Agent'
              }
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Play size={18} />
              )}
            </button>
          </>
        ) : status === 'running' ? (
          <>
            <button
              onClick={handlePause}
              disabled={isLoading}
              className="neo-btn neo-btn-warning text-sm py-2 px-3"
              title="Pause Agent"
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Pause size={18} />
              )}
            </button>
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3"
              title="Stop Agent"
            >
              <Square size={18} />
            </button>
          </>
        ) : status === 'paused' ? (
          <>
            <button
              onClick={handleResume}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3"
              title="Resume Agent"
            >
              {isLoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Play size={18} />
              )}
            </button>
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3"
              title="Stop Agent"
            >
              <Square size={18} />
            </button>
          </>
        ) : null}
      </div>
    </div>
  )
}

function StatusIndicator({ status }: { status: AgentStatus }) {
  const statusConfig = {
    stopped: {
      color: 'var(--color-neo-text-secondary)',
      label: 'Stopped',
      pulse: false,
    },
    running: {
      color: 'var(--color-neo-done)',
      label: 'Running',
      pulse: true,
    },
    paused: {
      color: 'var(--color-neo-pending)',
      label: 'Paused',
      pulse: false,
    },
    crashed: {
      color: 'var(--color-neo-danger)',
      label: 'Crashed',
      pulse: true,
    },
  }

  const config = statusConfig[status]

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-white border-3 border-[var(--color-neo-border)]">
      <span
        className={`w-3 h-3 rounded-full ${config.pulse ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: config.color }}
      />
      <span
        className="font-display font-bold text-sm uppercase"
        style={{ color: config.color }}
      >
        {config.label}
      </span>
    </div>
  )
}
