import { useState } from 'react'
import { Globe, Square, Loader2, ExternalLink, AlertTriangle, X } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { DevServerStatus } from '../lib/types'
import { startDevServer, stopDevServer } from '../lib/api'

// Re-export DevServerStatus from lib/types for consumers that import from here
export type { DevServerStatus }

// ============================================================================
// React Query Hooks (Internal)
// ============================================================================

/**
 * Internal hook to start the dev server for a project.
 * Invalidates the dev-server-status query on success.
 */
function useStartDevServer(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (port?: number) => startDevServer(projectName, undefined, port),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dev-server-status', projectName] })
    },
  })
}

/**
 * Internal hook to stop the dev server for a project.
 * Invalidates the dev-server-status query on success.
 */
function useStopDevServer(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => stopDevServer(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dev-server-status', projectName] })
    },
  })
}

// ============================================================================
// Component
// ============================================================================

interface DevServerControlProps {
  projectName: string
  status: DevServerStatus
  url: string | null
}

/**
 * DevServerControl provides start/stop controls for a project's development server.
 *
 * Features:
 * - Toggle button to start/stop the dev server
 * - Shows loading state during operations
 * - Displays clickable URL when server is running
 * - Uses neobrutalism design with cyan accent when running
 */
export function DevServerControl({ projectName, status, url }: DevServerControlProps) {
  const [showPortDialog, setShowPortDialog] = useState(false)
  const [portValue, setPortValue] = useState(3000)
  const startDevServerMutation = useStartDevServer(projectName)
  const stopDevServerMutation = useStopDevServer(projectName)

  const isLoading = startDevServerMutation.isPending || stopDevServerMutation.isPending

  const handleStartClick = () => {
    // Clear any previous errors before showing dialog
    stopDevServerMutation.reset()
    setShowPortDialog(true)
  }

  const handleConfirmStart = () => {
    setShowPortDialog(false)
    startDevServerMutation.mutate(portValue)
  }

  const handleCancelStart = () => {
    setShowPortDialog(false)
  }

  const handleStop = () => {
    // Clear any previous errors before stopping
    startDevServerMutation.reset()
    stopDevServerMutation.mutate()
  }

  // Server is stopped when status is 'stopped' or 'crashed' (can restart)
  const isStopped = status === 'stopped' || status === 'crashed'
  // Server is in a running state
  const isRunning = status === 'running'
  // Server has crashed
  const isCrashed = status === 'crashed'

  return (
    <div className="flex items-center gap-2 relative">
      {isStopped ? (
        <button
          onClick={handleStartClick}
          disabled={isLoading}
          className="neo-btn text-sm py-2 px-3"
          style={isCrashed ? {
            backgroundColor: 'var(--color-neo-danger)',
            color: 'var(--color-neo-text-on-bright)',
          } : undefined}
          title={isCrashed ? "Dev Server Crashed - Click to Restart" : "Start Dev Server"}
          aria-label={isCrashed ? "Restart Dev Server (crashed)" : "Start Dev Server"}
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : isCrashed ? (
            <AlertTriangle size={18} />
          ) : (
            <Globe size={18} />
          )}
        </button>
      ) : (
        <button
          onClick={handleStop}
          disabled={isLoading}
          className="neo-btn text-sm py-2 px-3"
          style={{
            backgroundColor: 'var(--color-neo-progress)',
            color: 'var(--color-neo-text-on-bright)',
          }}
          title="Stop Dev Server"
          aria-label="Stop Dev Server"
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Square size={18} />
          )}
        </button>
      )}

      {/* Port selection dialog */}
      {showPortDialog && (
        <div className="absolute top-full left-0 mt-2 z-50 neo-card p-3 min-w-[200px]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-bold">Port</span>
            <button
              onClick={handleCancelStart}
              className="p-1 hover:bg-[var(--color-neo-bg-secondary)] rounded"
              aria-label="Cancel"
            >
              <X size={14} />
            </button>
          </div>
          <input
            type="number"
            value={portValue}
            onChange={(e) => setPortValue(parseInt(e.target.value) || 3000)}
            className="w-full px-2 py-1 text-sm font-mono border-2 border-[var(--color-neo-border)] rounded mb-2"
            min={1}
            max={65535}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleConfirmStart()
              if (e.key === 'Escape') handleCancelStart()
            }}
          />
          <div className="flex gap-2">
            <button
              onClick={handleConfirmStart}
              className="neo-btn text-sm py-1 px-3 flex-1"
              style={{
                backgroundColor: 'var(--color-neo-progress)',
                color: 'var(--color-neo-text-on-bright)',
              }}
            >
              Start
            </button>
            <button
              onClick={handleCancelStart}
              className="neo-btn text-sm py-1 px-3"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Show URL as clickable link when server is running */}
      {isRunning && url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="neo-btn text-sm py-2 px-3 gap-1"
          style={{
            backgroundColor: 'var(--color-neo-progress)',
            color: 'var(--color-neo-text-on-bright)',
            textDecoration: 'none',
          }}
          title={`Open ${url} in new tab`}
        >
          <span className="font-mono text-xs">{url}</span>
          <ExternalLink size={14} />
        </a>
      )}

      {/* Error display */}
      {(startDevServerMutation.error || stopDevServerMutation.error) && (
        <span className="text-xs font-mono text-[var(--color-neo-danger)] ml-2">
          {String((startDevServerMutation.error || stopDevServerMutation.error)?.message || 'Operation failed')}
        </span>
      )}
    </div>
  )
}
