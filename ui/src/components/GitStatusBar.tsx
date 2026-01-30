import { useState, useEffect } from 'react'
import {
  GitBranch,
  ArrowUp,
  ArrowDown,
  FileEdit,
  FilePlus,
  Check,
  RefreshCw,
  AlertCircle,
  WifiOff,
  KeyRound,
  Clock,
  HelpCircle,
  CloudOff,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { GitStatus, GitErrorType } from '../lib/types'
import * as api from '../lib/api'

// Get icon and label for error type
function getErrorDisplay(errorType: GitErrorType): { icon: typeof AlertCircle; label: string } {
  switch (errorType) {
    case 'git_not_installed':
      return { icon: AlertCircle, label: 'Git not installed' }
    case 'auth_failed':
      return { icon: KeyRound, label: 'Auth failed' }
    case 'timeout':
      return { icon: Clock, label: 'Timeout' }
    case 'network':
      return { icon: WifiOff, label: 'Network error' }
    case 'no_remote':
      return { icon: CloudOff, label: 'No remote' }
    default:
      return { icon: HelpCircle, label: 'Error' }
  }
}

interface GitStatusBarProps {
  projectName: string | null
  className?: string
}

export function GitStatusBar({ projectName, className = '' }: GitStatusBarProps) {
  const [status, setStatus] = useState<GitStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = async () => {
    if (!projectName) return

    setIsLoading(true)
    setError(null)

    try {
      const data = await api.getGitStatus(projectName)
      setStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch git status')
      setStatus(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()

    // Refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [projectName])

  if (!projectName) {
    return null
  }

  // Handle API fetch errors
  if (error) {
    return (
      <TooltipProvider>
        <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1.5 cursor-help">
                <AlertCircle size={14} className="text-destructive" />
                <span>Git: Fetch error</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              <p className="font-medium">{error}</p>
              <p className="text-xs text-muted-foreground mt-1">Click refresh to retry</p>
            </TooltipContent>
          </Tooltip>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatus}
            disabled={isLoading}
            className="h-6 w-6 p-0"
            title="Retry"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </TooltipProvider>
    )
  }

  // Handle structured git errors from the API response
  if (status?.error) {
    const { icon: ErrorIcon, label } = getErrorDisplay(status.error.error_type)
    return (
      <TooltipProvider>
        <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-1.5 cursor-help">
                <ErrorIcon size={14} className="text-yellow-500" />
                <span>Git: {label}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              <p className="font-medium">{status.error.message}</p>
              <p className="text-xs text-muted-foreground mt-1">{status.error.action}</p>
            </TooltipContent>
          </Tooltip>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatus}
            disabled={isLoading}
            className="h-6 w-6 p-0"
            title="Refresh git status"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </TooltipProvider>
    )
  }

  if (!status || !status.isRepo) {
    return (
      <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
        <GitBranch size={14} />
        <span>Not a git repo</span>
      </div>
    )
  }

  const hasChanges = status.modified > 0 || status.staged > 0 || status.untracked > 0

  return (
    <div className={`flex items-center gap-3 text-sm ${className}`}>
      {/* Branch name */}
      <div className="flex items-center gap-1.5 text-foreground">
        <GitBranch size={14} className="text-primary" />
        <span className="font-medium">{status.branch || 'HEAD'}</span>
      </div>

      {/* Ahead/Behind indicators */}
      {(status.ahead > 0 || status.behind > 0) && (
        <div className="flex items-center gap-2 text-muted-foreground">
          {status.ahead > 0 && (
            <span className="flex items-center gap-0.5" title={`${status.ahead} commit(s) ahead`}>
              <ArrowUp size={12} />
              {status.ahead}
            </span>
          )}
          {status.behind > 0 && (
            <span className="flex items-center gap-0.5" title={`${status.behind} commit(s) behind`}>
              <ArrowDown size={12} />
              {status.behind}
            </span>
          )}
        </div>
      )}

      {/* Change indicators */}
      {hasChanges ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          {status.staged > 0 && (
            <span
              className="flex items-center gap-0.5 text-green-500"
              title={`${status.staged} staged file(s)`}
            >
              <Check size={12} />
              {status.staged}
            </span>
          )}
          {status.modified > 0 && (
            <span
              className="flex items-center gap-0.5 text-yellow-500"
              title={`${status.modified} modified file(s)`}
            >
              <FileEdit size={12} />
              {status.modified}
            </span>
          )}
          {status.untracked > 0 && (
            <span
              className="flex items-center gap-0.5 text-blue-500"
              title={`${status.untracked} untracked file(s)`}
            >
              <FilePlus size={12} />
              {status.untracked}
            </span>
          )}
        </div>
      ) : (
        <span className="text-muted-foreground flex items-center gap-1">
          <Check size={12} className="text-green-500" />
          Clean
        </span>
      )}

      {/* Refresh button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={fetchStatus}
        disabled={isLoading}
        className="h-6 w-6 p-0"
        title="Refresh git status"
      >
        <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
      </Button>
    </div>
  )
}

export default GitStatusBar
