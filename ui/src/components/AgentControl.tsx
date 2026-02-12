import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Square, Loader2, GitBranch, Clock, Pause, PlayCircle } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  useGracefulPauseAgent,
  useGracefulResumeAgent,
  useSettings,
  useUpdateProjectSettings,
} from '../hooks/useProjects'
import { useNextScheduledRun } from '../hooks/useSchedules'
import { formatNextRun, formatEndTime } from '../lib/timeUtils'
import { ScheduleModal } from './ScheduleModal'
import type { AgentStatus } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
  defaultConcurrency?: number
}

export function AgentControl({ projectName, status, defaultConcurrency = 3 }: AgentControlProps) {
  const { data: settings } = useSettings()
  const yoloMode = settings?.yolo_mode ?? false

  // Concurrency: 1 = single agent, 2-5 = parallel
  const [concurrency, setConcurrency] = useState(defaultConcurrency)

  // Sync concurrency when project changes or defaultConcurrency updates
  useEffect(() => {
    setConcurrency(defaultConcurrency)
  }, [defaultConcurrency])

  // Debounced save for concurrency changes
  const updateProjectSettings = useUpdateProjectSettings(projectName)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleConcurrencyChange = useCallback((newConcurrency: number) => {
    setConcurrency(newConcurrency)

    // Clear previous timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current)
    }

    // Debounce save (500ms)
    saveTimeoutRef.current = setTimeout(() => {
      updateProjectSettings.mutate({ default_concurrency: newConcurrency })
    }, 500)
  }, [updateProjectSettings])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [])

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const gracefulPause = useGracefulPauseAgent(projectName)
  const gracefulResume = useGracefulResumeAgent(projectName)
  const { data: nextRun } = useNextScheduledRun(projectName)

  const [showScheduleModal, setShowScheduleModal] = useState(false)

  const isLoading = startAgent.isPending || stopAgent.isPending || gracefulPause.isPending || gracefulResume.isPending
  const isRunning = status === 'running' || status === 'paused' || status === 'pausing' || status === 'paused_graceful'
  const isLoadingStatus = status === 'loading'
  const isParallel = concurrency > 1

  const handleStart = () => startAgent.mutate({
    yoloMode,
    parallelMode: isParallel,
    maxConcurrency: concurrency,
    testingAgentRatio: settings?.testing_agent_ratio,
  })
  const handleStop = () => stopAgent.mutate()

  const isStopped = status === 'stopped' || status === 'crashed'

  return (
    <>
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Concurrency slider - visible when stopped */}
        {isStopped && (
          <div className="flex items-center gap-2">
            <GitBranch size={16} className={isParallel ? 'text-primary' : 'text-muted-foreground'} />
            <input
              type="range"
              min={1}
              max={5}
              value={concurrency}
              onChange={(e) => handleConcurrencyChange(Number(e.target.value))}
              disabled={isLoading}
              className="w-16 h-2 accent-primary cursor-pointer"
              title={`${concurrency} concurrent agent${concurrency > 1 ? 's' : ''}`}
              aria-label="Set number of concurrent agents"
            />
            <span className="text-xs font-semibold min-w-[1.5rem] text-center">
              {concurrency}x
            </span>
          </div>
        )}

        {/* Show concurrency indicator when running with multiple agents */}
        {isRunning && isParallel && (
          <Badge variant="secondary" className="gap-1">
            <GitBranch size={14} />
            {concurrency}x
          </Badge>
        )}

        {/* Schedule status display */}
        {nextRun?.is_currently_running && nextRun.next_end && (
          <Badge variant="default" className="gap-1">
            <Clock size={14} />
            Running until {formatEndTime(nextRun.next_end)}
          </Badge>
        )}

        {!nextRun?.is_currently_running && nextRun?.next_start && (
          <Badge variant="secondary" className="gap-1">
            <Clock size={14} />
            Next: {formatNextRun(nextRun.next_start)}
          </Badge>
        )}

        {/* Start/Stop/Pause/Resume buttons */}
        {isLoadingStatus ? (
          <Button disabled variant="outline" size="sm">
            <Loader2 size={18} className="animate-spin" />
          </Button>
        ) : isStopped ? (
          <Button
            onClick={handleStart}
            disabled={isLoading}
            variant={yoloMode ? 'secondary' : 'default'}
            size="sm"
            title={yoloMode ? 'Start Agent (YOLO Mode)' : 'Start Agent'}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Play size={18} />
            )}
          </Button>
        ) : (
          <div className="flex items-center gap-1.5">
            {/* Pausing indicator */}
            {status === 'pausing' && (
              <Badge variant="secondary" className="gap-1 animate-pulse">
                <Loader2 size={12} className="animate-spin" />
                Pausing...
              </Badge>
            )}

            {/* Paused indicator + Resume button */}
            {status === 'paused_graceful' && (
              <>
                <Badge variant="outline" className="gap-1">
                  Paused
                </Badge>
                <Button
                  onClick={() => gracefulResume.mutate()}
                  disabled={isLoading}
                  variant="default"
                  size="sm"
                  title="Resume agent"
                >
                  {gracefulResume.isPending ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <PlayCircle size={18} />
                  )}
                </Button>
              </>
            )}

            {/* Graceful pause button (only when running normally) */}
            {status === 'running' && (
              <Button
                onClick={() => gracefulPause.mutate()}
                disabled={isLoading}
                variant="outline"
                size="sm"
                title="Pause agent (finish current work first)"
              >
                {gracefulPause.isPending ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Pause size={18} />
                )}
              </Button>
            )}

            {/* Stop button (always available) */}
            <Button
              onClick={handleStop}
              disabled={isLoading}
              variant="destructive"
              size="sm"
              title="Stop Agent (immediate)"
            >
              {stopAgent.isPending ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Square size={18} />
              )}
            </Button>
          </div>
        )}

        {/* Clock button to open schedule modal */}
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowScheduleModal(true)}
          title="Manage schedules"
        >
          <Clock size={18} />
        </Button>
      </div>

      {/* Schedule Modal */}
      <ScheduleModal
        projectName={projectName}
        isOpen={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
      />
    </>
  )
}
