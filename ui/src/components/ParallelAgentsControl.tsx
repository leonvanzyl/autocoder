/**
 * Parallel Agents Control
 * =======================
 *
 * UI component for starting/stopping parallel agents for a project.
 *
 * Uses the per-project agent endpoints:
 * - POST `/api/projects/{project}/agent/start` (parallel_mode=true)
 * - POST `/api/projects/{project}/agent/stop`
 */

import { useState } from 'react'
import { Zap, Play, Square, Loader2, X } from 'lucide-react'
import { useAgentStatus, useStartAgent, useStopAgent } from '../hooks/useProjects'
import { useModelSettings } from '../hooks/useModelSettings'

interface ParallelAgentsControlProps {
  projectName: string
  onClose: () => void
}

export function ParallelAgentsControl({ projectName, onClose }: ParallelAgentsControlProps) {
  const [parallelCount, setParallelCount] = useState(3)

  const { data: settings } = useModelSettings()
  const { data: agentStatus, isLoading } = useAgentStatus(projectName)
  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)

  const isRunning = agentStatus?.status === 'running' && agentStatus?.parallel_mode
  const isBusy = startAgent.isPending || stopAgent.isPending

  const handleStart = () => {
    startAgent.mutate({
      parallel_mode: true,
      parallel_count: parallelCount,
      model_preset: (settings?.preset as any) ?? 'balanced',
      yolo_mode: false,
    })
  }

  const handleStop = () => {
    stopAgent.mutate()
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div className="neo-modal w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <Zap className="text-[var(--color-neo-accent)]" size={32} />
            <h2 className="font-display text-2xl font-bold uppercase">Parallel Agents</h2>
          </div>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2" aria-label="Close">
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-[var(--color-neo-progress)]" />
            </div>
          ) : (
            <>
              {/* Project */}
              <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
                <div className="text-sm text-[var(--color-neo-text-secondary)] mb-1">Project</div>
                <div className="font-display font-bold text-lg">{projectName}</div>
              </div>

              {/* Agent Count Slider */}
              <div>
                <label className="block font-display font-bold text-sm mb-3 uppercase">
                  <span className="text-[var(--color-neo-text)]">Number of Parallel Agents:</span>{' '}
                  <span className="text-[var(--color-neo-accent)]">{parallelCount}</span>
                </label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={parallelCount}
                  onChange={(e) => setParallelCount(parseInt(e.target.value))}
                  disabled={isRunning}
                  className={`w-full h-2 rounded-full appearance-none cursor-pointer ${
                    isRunning ? 'opacity-50 cursor-not-allowed' : ''
                  }`}
                  style={{
                    background: `linear-gradient(to right, var(--color-neo-accent) 0%, var(--color-neo-accent) ${
                      (parallelCount - 1) * 25
                    }%, var(--color-neo-border) ${(parallelCount - 1) * 25}%, var(--color-neo-border) 100%)`,
                  }}
                />
                <div className="flex justify-between text-xs font-mono mt-2 text-[var(--color-neo-text-secondary)]">
                  <span>1</span>
                  <span>2</span>
                  <span className="font-bold text-[var(--color-neo-accent)]">3</span>
                  <span>4</span>
                  <span>5</span>
                </div>
              </div>

              {/* Preset Display */}
              {settings && (
                <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
                  <div className="text-sm text-[var(--color-neo-text-secondary)] mb-1">Model Preset</div>
                  <div className="font-display font-bold text-lg capitalize mb-1">{settings.preset}</div>
                  <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
                    {settings.available_models.map((m) => m.toUpperCase()).join(' + ')}
                  </div>
                </div>
              )}

              {/* Start/Stop */}
              <button
                onClick={isRunning ? handleStop : handleStart}
                disabled={isBusy}
                className={`neo-btn w-full text-lg py-4 flex items-center justify-center gap-2 ${
                  isRunning ? 'neo-btn-danger' : 'neo-btn-primary'
                } disabled:opacity-50`}
              >
                {isBusy ? (
                  <Loader2 size={20} className="animate-spin" />
                ) : isRunning ? (
                  <>
                    <Square size={20} />
                    Stop Agents
                  </>
                ) : (
                  <>
                    <Play size={20} />
                    Start {parallelCount} Agents
                  </>
                )}
              </button>

              {/* Status */}
              {agentStatus?.parallel_mode && (agentStatus.status === 'running' || agentStatus.status === 'paused') && (
                <div className="neo-card p-4 bg-[var(--color-neo-done)]/10 border-[var(--color-neo-done)]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-display font-bold text-[var(--color-neo-done)]">Running</span>
                    <span className="text-sm font-mono">
                      {agentStatus.parallel_count} agents ({agentStatus.model_preset})
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

