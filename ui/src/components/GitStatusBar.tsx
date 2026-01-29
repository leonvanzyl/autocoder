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
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { GitStatus } from '../lib/types'
import * as api from '../lib/api'

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

  if (error) {
    return (
      <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}>
        <AlertCircle size={14} className="text-destructive" />
        <span>Git: Error</span>
      </div>
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
