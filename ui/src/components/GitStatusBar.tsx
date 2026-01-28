import { GitBranch, GitCommit, AlertCircle } from 'lucide-react'
import type { GitStatusResponse } from '../lib/types'

interface GitStatusBarProps {
  gitStatus: GitStatusResponse | undefined
  isLoading: boolean
}

export function GitStatusBar({ gitStatus, isLoading }: GitStatusBarProps) {
  if (isLoading || !gitStatus) {
    return null
  }

  if (!gitStatus.has_git) {
    return (
      <div className="neo-card p-3 border-slate-700/50">
        <div className="flex items-center gap-2 text-slate-500 text-xs">
          <GitBranch size={14} />
          <span>No git repository</span>
        </div>
      </div>
    )
  }

  const timeAgo = gitStatus.last_commit_time
    ? formatTimeAgo(gitStatus.last_commit_time)
    : null

  return (
    <div className="neo-card p-3">
      <div className="flex items-center justify-between gap-4">
        {/* Branch info */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-1.5">
            <GitBranch size={14} className="text-purple-400 flex-shrink-0" />
            <span className="text-sm font-mono font-medium text-purple-300 truncate">
              {gitStatus.branch ?? 'detached'}
            </span>
          </div>

          {/* Dirty indicator */}
          {gitStatus.is_dirty && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-medium flex-shrink-0">
              <AlertCircle size={10} />
              {gitStatus.uncommitted_count} uncommitted
            </span>
          )}
        </div>

        {/* Last commit */}
        <div className="flex items-center gap-3 text-xs text-slate-400 flex-shrink-0">
          {gitStatus.last_commit_hash && (
            <div className="flex items-center gap-1.5">
              <GitCommit size={12} className="text-slate-500" />
              <span className="font-mono text-slate-300">{gitStatus.last_commit_hash}</span>
              <span className="max-w-[200px] truncate hidden lg:inline">
                {gitStatus.last_commit_message}
              </span>
            </div>
          )}

          {timeAgo && (
            <span className="text-slate-500">{timeAgo}</span>
          )}

          {gitStatus.total_commits > 0 && (
            <span className="text-slate-500">
              {gitStatus.total_commits} commit{gitStatus.total_commits !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function formatTimeAgo(dateStr: string): string {
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)
    const diffMin = Math.floor(diffSec / 60)
    const diffHour = Math.floor(diffMin / 60)
    const diffDay = Math.floor(diffHour / 24)

    if (diffSec < 60) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    if (diffHour < 24) return `${diffHour}h ago`
    if (diffDay < 30) return `${diffDay}d ago`
    return date.toLocaleDateString()
  } catch {
    return ''
  }
}
