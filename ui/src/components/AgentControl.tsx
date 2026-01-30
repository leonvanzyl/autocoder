import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Square, Loader2, GitBranch, Clock, PauseCircle, PlayCircle } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  useEffectiveSettingsV2,
  useUpdateProjectSettings,
  usePausePickup,
  useResumePickup,
} from '../hooks/useProjects'
import { useNextScheduledRun } from '../hooks/useSchedules'
import { formatNextRun, formatEndTime } from '../lib/timeUtils'
import { ScheduleModal } from './ScheduleModal'
import { GracefulShutdownDialog } from './GracefulShutdownDialog'
import type { AgentStatus, AgentStatusResponse } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
  agentStatusResponse?: AgentStatusResponse
  defaultConcurrency?: number
}

export function AgentControl({ projectName, status, agentStatusResponse, defaultConcurrency = 3 }: AgentControlProps) {
  // Use V2 effective settings which properly merges app + project overrides
  const { data: effectiveSettings } = useEffectiveSettingsV2(projectName)

  // Extract settings from V2 response (settings is a Record<string, unknown>)
  const yoloMode = (effectiveSettings?.settings?.yoloMode as boolean) ?? false
  const model = effectiveSettings?.settings?.coderModel as string | undefined
  const testingAgentRatio = (effectiveSettings?.settings?.testingAgentRatio as number) ?? 1

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
  const pausePickup = usePausePickup(projectName)
  const resumePickup = useResumePickup(projectName)
  const { data: nextRun } = useNextScheduledRun(projectName)

  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [showShutdownDialog, setShowShutdownDialog] = useState(false)

  const isLoading = startAgent.isPending || stopAgent.isPending
  const isPausePickupLoading = pausePickup.isPending || resumePickup.isPending
  const isRunning = status === 'running' || status === 'paused'
  const isLoadingStatus = status === 'loading'
  const isParallel = concurrency > 1

  // Get orchestrator state from response
  const pickupPaused = agentStatusResponse?.pickup_paused ?? false
  const gracefulShutdown = agentStatusResponse?.graceful_shutdown ?? false
  const activeAgentCount = agentStatusResponse?.active_agent_count ?? 0

  const handleStart = () => startAgent.mutate({
    yoloMode,
    model,
    parallelMode: isParallel,
    maxConcurrency: concurrency,
    testingAgentRatio,
  })

  const handleStopClick = () => {
    // If there are active agents, show the graceful shutdown dialog
    if (activeAgentCount > 0) {
      setShowShutdownDialog(true)
    } else {
      // No active agents, stop immediately
      stopAgent.mutate()
    }
  }

  const handleTogglePickupPause = () => {
    if (pickupPaused) {
      resumePickup.mutate()
    } else {
      pausePickup.mutate()
    }
  }

  const isStopped = status === 'stopped' || status === 'crashed'

  return (
    <>
      <div className="flex items-center gap-4">
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

        {/* Pickup paused badge */}
        {isRunning && pickupPaused && !gracefulShutdown && (
          <Badge variant="outline" className="gap-1 border-amber-500 text-amber-600">
            <PauseCircle size={14} />
            Pickup Paused
          </Badge>
        )}

        {/* Graceful shutdown badge */}
        {isRunning && gracefulShutdown && (
          <Badge variant="outline" className="gap-1 border-orange-500 text-orange-600">
            <Clock size={14} />
            Shutting down ({activeAgentCount} running)
          </Badge>
        )}

        {/* Pause pickup toggle - visible when running */}
        {isRunning && !gracefulShutdown && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTogglePickupPause}
                  disabled={isPausePickupLoading}
                  className={pickupPaused ? 'border-amber-500' : ''}
                >
                  {isPausePickupLoading ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : pickupPaused ? (
                    <PlayCircle size={18} className="text-green-600" />
                  ) : (
                    <PauseCircle size={18} />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {pickupPaused
                  ? 'Resume claiming new features'
                  : 'Pause claiming new features (running agents continue)'}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
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

        {/* Start/Stop button */}
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
          <Button
            onClick={handleStopClick}
            disabled={isLoading || gracefulShutdown}
            variant="destructive"
            size="sm"
            title={gracefulShutdown ? 'Shutting down...' : (yoloMode ? 'Stop Agent (YOLO Mode)' : 'Stop Agent')}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Square size={18} />
            )}
          </Button>
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

      {/* Graceful Shutdown Dialog */}
      <GracefulShutdownDialog
        projectName={projectName}
        isOpen={showShutdownDialog}
        onClose={() => setShowShutdownDialog(false)}
        activeAgentCount={activeAgentCount}
      />
    </>
  )
}
