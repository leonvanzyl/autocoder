import { Globe, Square, Loader2, ExternalLink, AlertTriangle } from 'lucide-react'
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
    mutationFn: () => startDevServer(projectName),
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
  const startDevServerMutation = useStartDevServer(projectName)
  const stopDevServerMutation = useStopDevServer(projectName)

  const isLoading = startDevServerMutation.isPending || stopDevServerMutation.isPending

  const handleStart = () => {
    // Clear any previous errors before starting
    stopDevServerMutation.reset()
    startDevServerMutation.mutate()
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
    <div className="flex items-center gap-2">
      {isStopped ? (
        <button
          onClick={handleStart}
          disabled={isLoading}
          className="neo-btn text-sm py-2 px-3"
          style={isCrashed ? {
            backgroundColor: 'var(--color-neo-danger)',
            color: '#ffffff',
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
            color: '#ffffff',
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

      {/* Show URL as clickable link when server is running */}
      {isRunning && url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="neo-btn text-sm py-2 px-3 gap-1"
          style={{
            backgroundColor: 'var(--color-neo-progress)',
            color: '#ffffff',
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
