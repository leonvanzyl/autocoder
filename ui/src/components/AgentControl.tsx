import { Play, Pause, Square, Loader2, Zap, Users } from 'lucide-react'
import { useStartAgent, useStopAgent, usePauseAgent, useResumeAgent } from '../hooks/useProjects'
import type { AgentStatus } from '../lib/types'

export type RunMode = 'standard' | 'parallel'
export type ParallelPreset = 'quality' | 'balanced' | 'economy' | 'cheap' | 'experimental' | 'custom'

interface AgentControlProps {
  projectName: string
  status: AgentStatus

  // Current running mode (from server status)
  yoloMode?: boolean
  parallelMode?: boolean
  parallelCount?: number | null
  modelPreset?: string | null

  // Next-run settings (local UI state)
  yoloEnabled: boolean
  onToggleYolo: () => void
  runMode: RunMode
  parallelCountSetting: number
  parallelPresetSetting: ParallelPreset
}

export function AgentControl({
  projectName,
  status,
  yoloMode = false,
  parallelMode = false,
  parallelCount = null,
  modelPreset = null,
  yoloEnabled,
  onToggleYolo,
  runMode,
  parallelCountSetting,
  parallelPresetSetting,
}: AgentControlProps) {
  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const pauseAgent = usePauseAgent(projectName)
  const resumeAgent = useResumeAgent(projectName)

  const isLoading = startAgent.isPending || stopAgent.isPending || pauseAgent.isPending || resumeAgent.isPending

  const handleStart = () => {
    if (yoloEnabled) {
      startAgent.mutate({ yolo_mode: true, parallel_mode: false })
      return
    }

    if (runMode === 'parallel') {
      startAgent.mutate({
        parallel_mode: true,
        parallel_count: parallelCountSetting,
        model_preset: parallelPresetSetting,
        yolo_mode: false,
      })
      return
    }

    startAgent.mutate({ yolo_mode: false, parallel_mode: false })
  }

  const handleStop = () => stopAgent.mutate()
  const handlePause = () => pauseAgent.mutate()
  const handleResume = () => resumeAgent.mutate()

  const startTitle = yoloEnabled
    ? 'Start (YOLO)'
    : runMode === 'parallel'
      ? `Start (${parallelCountSetting} agents, ${parallelPresetSetting})`
      : 'Start'

  return (
    <div className="flex items-center gap-2">
      <StatusIndicator status={status} />

      {(status === 'running' || status === 'paused') && (
        <>
          {yoloMode && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
              <Zap size={14} className="text-yellow-900" />
              <span className="font-display font-bold text-xs uppercase text-yellow-900">YOLO</span>
            </div>
          )}

          {parallelMode && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-progress)] border-3 border-[var(--color-neo-border)]">
              <Users size={14} className="text-cyan-900" />
              <span className="font-display font-bold text-xs uppercase text-cyan-900">
                {parallelCount}x {modelPreset}
              </span>
            </div>
          )}
        </>
      )}

      <div className="flex gap-1">
        {status === 'stopped' || status === 'crashed' ? (
          <>
            {/* YOLO toggle stays in header for quick access */}
            <button
              onClick={onToggleYolo}
              disabled={isLoading}
              className={`neo-btn text-sm py-2 px-3 ${yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'}`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={18} className={yoloEnabled ? 'text-yellow-900' : ''} />
            </button>

            <button
              onClick={handleStart}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3"
              title={startTitle}
            >
              {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
            </button>
          </>
        ) : status === 'running' ? (
          <>
            <button
              onClick={handlePause}
              disabled={isLoading}
              className="neo-btn neo-btn-warning text-sm py-2 px-3"
              title="Pause"
            >
              {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Pause size={18} />}
            </button>
            <button onClick={handleStop} disabled={isLoading} className="neo-btn neo-btn-danger text-sm py-2 px-3" title="Stop">
              <Square size={18} />
            </button>
          </>
        ) : status === 'paused' ? (
          <>
            <button
              onClick={handleResume}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3"
              title="Resume"
            >
              {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
            </button>
            <button onClick={handleStop} disabled={isLoading} className="neo-btn neo-btn-danger text-sm py-2 px-3" title="Stop">
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
    stopped: { color: 'var(--color-neo-text-secondary)', label: 'Stopped', pulse: false },
    running: { color: 'var(--color-neo-done)', label: 'Running', pulse: true },
    paused: { color: 'var(--color-neo-pending)', label: 'Paused', pulse: false },
    crashed: { color: 'var(--color-neo-danger)', label: 'Crashed', pulse: true },
  }

  const config = statusConfig[status]

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-white border-3 border-[var(--color-neo-border)]">
      <span className={`w-3 h-3 rounded-full ${config.pulse ? 'animate-pulse' : ''}`} style={{ backgroundColor: config.color }} />
      <span className="font-display font-bold text-sm uppercase" style={{ color: config.color }}>
        {config.label}
      </span>
    </div>
  )
}
