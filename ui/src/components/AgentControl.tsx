import { useState } from 'react'
import { Play, Pause, Square, Loader2, Zap, GitBranch, Users } from 'lucide-react'
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
  parallelMode?: boolean  // From server status - whether currently running in parallel mode
  parallelCount?: number | null  // From server status - number of parallel agents
  modelPreset?: string | null  // From server status - model preset being used
}

export function AgentControl({
  projectName,
  status,
  yoloMode = false,
  parallelMode = false,
  parallelCount = null,
  modelPreset = null,
}: AgentControlProps) {
  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [parallelEnabled, setParallelEnabled] = useState(false)
  const [agentCount, setAgentCount] = useState(3)
  const [selectedPreset, setSelectedPreset] = useState<'quality' | 'balanced' | 'economy' | 'cheap' | 'experimental'>('balanced')

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const pauseAgent = usePauseAgent(projectName)
  const resumeAgent = useResumeAgent(projectName)

  const isLoading =
    startAgent.isPending ||
    stopAgent.isPending ||
    pauseAgent.isPending ||
    resumeAgent.isPending

  const handleStart = () => {
    // Disable YOLO when parallel is enabled (mutually exclusive)
    if (parallelEnabled) {
      startAgent.mutate({
        parallel_mode: true,
        parallel_count: agentCount,
        model_preset: selectedPreset,
        yolo_mode: false,
      })
    } else {
      startAgent.mutate({ yolo_mode: yoloEnabled })
    }
  }

  const handleStop = () => stopAgent.mutate()
  const handlePause = () => pauseAgent.mutate()
  const handleResume = () => resumeAgent.mutate()

  // Disable parallel toggle when YOLO is enabled
  const isParallelDisabled = yoloEnabled

  return (
    <div className="flex items-center gap-2">
      {/* Status Indicator */}
      <StatusIndicator status={status} />

      {/* Mode Indicators - shown when running */}
      {(status === 'running' || status === 'paused') && (
        <>
          {/* YOLO Mode Indicator */}
          {yoloMode && (
            <div className="flex items-center gap-1 px-2 py-1 bg-[var(--color-neo-pending)] border-3 border-[var(--color-neo-border)]">
              <Zap size={14} className="text-yellow-900" />
              <span className="font-display font-bold text-xs uppercase text-yellow-900">
                YOLO
              </span>
            </div>
          )}

          {/* Parallel Mode Indicator */}
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

      {/* Control Buttons */}
      <div className="flex gap-1">
        {status === 'stopped' || status === 'crashed' ? (
          <>
            {/* Mode Toggles - only shown when stopped */}
            {/* YOLO Toggle */}
            <button
              onClick={() => {
                setYoloEnabled(!yoloEnabled)
                if (parallelEnabled) setParallelEnabled(false)
              }}
              disabled={isLoading || parallelEnabled}
              className={`neo-btn text-sm py-2 px-3 ${
                yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'
              } ${isParallelDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={18} className={yoloEnabled ? 'text-yellow-900' : ''} />
            </button>

            {/* Parallel Mode Toggle */}
            <button
              onClick={() => {
                setParallelEnabled(!parallelEnabled)
                if (yoloEnabled) setYoloEnabled(false)
              }}
              disabled={isLoading || yoloEnabled}
              className={`neo-btn text-sm py-2 px-3 ${
                parallelEnabled ? 'neo-btn-info' : 'neo-btn-secondary'
              } ${yoloEnabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="Parallel Mode: Run multiple agents simultaneously (3x faster)"
            >
              <GitBranch size={18} className={parallelEnabled ? 'text-cyan-900' : ''} />
            </button>

            {/* Parallel Settings - shown when parallel enabled */}
            {parallelEnabled && (
              <>
                {/* Agent Count Selector */}
                <select
                  value={agentCount}
                  onChange={(e) => setAgentCount(Number(e.target.value))}
                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display"
                >
                  <option value="1">1 Agent</option>
                  <option value="2">2 Agents</option>
                  <option value="3">3 Agents</option>
                  <option value="4">4 Agents</option>
                  <option value="5">5 Agents</option>
                </select>

                {/* Model Preset Selector */}
                <select
                  value={selectedPreset}
                  onChange={(e) => setSelectedPreset(e.target.value as any)}
                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display"
                >
                  <option value="quality">Quality (Opus)</option>
                  <option value="balanced">Balanced ⭐</option>
                  <option value="economy">Economy</option>
                  <option value="cheap">Cheap</option>
                  <option value="experimental">Experimental</option>
                </select>
              </>
            )}

            {/* Start Button */}
            <button
              onClick={handleStart}
              disabled={isLoading}
              className="neo-btn neo-btn-success text-sm py-2 px-3"
              title={
                parallelEnabled
                  ? `Start ${agentCount} Parallel Agents (${selectedPreset})`
                  : yoloEnabled
                  ? "Start Agent (YOLO Mode)"
                  : "Start Agent"
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
