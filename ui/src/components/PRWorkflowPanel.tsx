import { useState, useEffect } from 'react'
import {
  GitPullRequest,
  GitBranch,
  Upload,
  Check,
  X,
  Clock,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  Plus,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { PRStatus, PRChecksResponse } from '../lib/types'
import * as api from '../lib/api'

interface PRWorkflowPanelProps {
  projectName: string | null
  className?: string
}

function PRStateBadge({ state }: { state: string }) {
  const stateConfig: Record<string, { color: string; icon: typeof Check }> = {
    OPEN: { color: 'bg-green-500/20 text-green-600', icon: GitPullRequest },
    CLOSED: { color: 'bg-red-500/20 text-red-600', icon: X },
    MERGED: { color: 'bg-purple-500/20 text-purple-600', icon: Check },
  }

  const config = stateConfig[state.toUpperCase()] || stateConfig.OPEN
  const Icon = config.icon

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.color}`}>
      <Icon size={12} />
      {state}
    </span>
  )
}

function CheckStatusIcon({ conclusion, state }: { conclusion: string | null; state: string }) {
  if (state === 'PENDING' || state === 'IN_PROGRESS') {
    return <Clock size={14} className="text-yellow-500 animate-pulse" />
  }
  if (conclusion === 'SUCCESS') {
    return <Check size={14} className="text-green-500" />
  }
  if (conclusion === 'FAILURE') {
    return <X size={14} className="text-red-500" />
  }
  return <Clock size={14} className="text-muted-foreground" />
}

export function PRWorkflowPanel({ projectName, className = '' }: PRWorkflowPanelProps) {
  const [status, setStatus] = useState<PRStatus | null>(null)
  const [checks, setChecks] = useState<PRChecksResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isPushing, setIsPushing] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  // Create PR form state
  const [prTitle, setPrTitle] = useState('')
  const [prBody, setPrBody] = useState('')
  const [prBaseBranch, setPrBaseBranch] = useState('main')
  const [prDraft, setPrDraft] = useState(false)

  const fetchStatus = async () => {
    if (!projectName) return

    setIsLoading(true)
    setError(null)

    try {
      const [statusData, checksData] = await Promise.all([
        api.getPRStatus(projectName),
        api.getPRChecks(projectName).catch(() => null),
      ])
      setStatus(statusData)
      setChecks(checksData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch PR status')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [projectName])

  const handlePush = async () => {
    if (!projectName) return

    setIsPushing(true)
    try {
      await api.pushBranch(projectName)
      await fetchStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to push')
    } finally {
      setIsPushing(false)
    }
  }

  const handleCreatePR = async () => {
    if (!projectName || !prTitle) return

    setIsCreating(true)
    try {
      const result = await api.createPR(projectName, {
        title: prTitle,
        body: prBody,
        base_branch: prBaseBranch,
        draft: prDraft,
      })

      if (result.success) {
        setShowCreateForm(false)
        setPrTitle('')
        setPrBody('')
        await fetchStatus()
      } else {
        setError(result.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create PR')
    } finally {
      setIsCreating(false)
    }
  }

  if (!projectName) {
    return null
  }

  return (
    <div className={`bg-card border-2 border-border rounded-lg ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <GitPullRequest size={18} className="text-primary" />
          <span className="font-medium">Pull Request</span>
          {status?.hasPR && status.pr && (
            <PRStateBadge state={status.pr.state} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation()
              fetchStatus()
            }}
            disabled={isLoading}
            className="h-7 w-7 p-0"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </Button>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-border p-3 space-y-4">
          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {/* Not authenticated */}
          {status && !status.authenticated && (
            <div className="text-sm text-muted-foreground">
              <p>GitHub CLI not authenticated.</p>
              <p className="text-xs mt-1">Run <code className="bg-muted px-1 rounded">gh auth login</code> to authenticate.</p>
            </div>
          )}

          {/* Current branch info */}
          {status?.currentBranch && (
            <div className="flex items-center gap-2 text-sm">
              <GitBranch size={14} className="text-muted-foreground" />
              <span className="text-muted-foreground">Branch:</span>
              <span className="font-medium">{status.currentBranch}</span>
            </div>
          )}

          {/* Existing PR */}
          {status?.hasPR && status.pr && (
            <div className="space-y-3">
              <div className="p-3 bg-muted/50 rounded-lg space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <a
                      href={status.pr.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium hover:text-primary transition-colors flex items-center gap-1"
                    >
                      #{status.pr.number} {status.pr.title}
                      <ExternalLink size={12} />
                    </a>
                    <div className="text-xs text-muted-foreground mt-1">
                      {status.pr.base_branch} &larr; {status.pr.head_branch}
                    </div>
                  </div>
                </div>

                {/* PR stats */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  {status.pr.additions !== null && (
                    <span className="text-green-500">+{status.pr.additions}</span>
                  )}
                  {status.pr.deletions !== null && (
                    <span className="text-red-500">-{status.pr.deletions}</span>
                  )}
                  {status.pr.changed_files !== null && (
                    <span>{status.pr.changed_files} files</span>
                  )}
                </div>

                {/* Mergeable status */}
                {status.pr.mergeable !== null && (
                  <div className={`text-xs flex items-center gap-1 ${
                    status.pr.mergeable ? 'text-green-500' : 'text-yellow-500'
                  }`}>
                    {status.pr.mergeable ? <Check size={12} /> : <AlertCircle size={12} />}
                    {status.pr.mergeable ? 'Ready to merge' : 'Has conflicts'}
                  </div>
                )}
              </div>

              {/* CI Checks */}
              {checks?.hasChecks && checks.summary && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">CI Checks</span>
                    <span className="text-xs">
                      {checks.summary.passing}/{checks.summary.total} passing
                    </span>
                  </div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {checks.checks.slice(0, 5).map((check, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 min-w-0">
                          <CheckStatusIcon conclusion={check.conclusion} state={check.state} />
                          <span className="truncate">{check.name}</span>
                        </div>
                        {check.detailsUrl && (
                          <a
                            href={check.detailsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline shrink-0"
                          >
                            Details
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* No PR - show create option */}
          {status && status.authenticated && !status.hasPR && (
            <div className="space-y-3">
              {!showCreateForm ? (
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePush}
                    disabled={isPushing}
                    className="w-full gap-2"
                  >
                    <Upload size={14} />
                    {isPushing ? 'Pushing...' : 'Push to Remote'}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setShowCreateForm(true)}
                    className="w-full gap-2"
                  >
                    <Plus size={14} />
                    Create Pull Request
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Title</Label>
                    <input
                      type="text"
                      value={prTitle}
                      onChange={(e) => setPrTitle(e.target.value)}
                      placeholder="PR title..."
                      className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Description</Label>
                    <textarea
                      value={prBody}
                      onChange={(e) => setPrBody(e.target.value)}
                      placeholder="PR description..."
                      rows={3}
                      className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded resize-none"
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="space-y-1.5 flex-1">
                      <Label className="text-xs">Base Branch</Label>
                      <input
                        type="text"
                        value={prBaseBranch}
                        onChange={(e) => setPrBaseBranch(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded"
                      />
                    </div>
                    <label className="flex items-center gap-2 text-sm cursor-pointer pt-5">
                      <input
                        type="checkbox"
                        checked={prDraft}
                        onChange={(e) => setPrDraft(e.target.checked)}
                        className="rounded"
                      />
                      Draft
                    </label>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowCreateForm(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleCreatePR}
                      disabled={isCreating || !prTitle}
                      className="flex-1"
                    >
                      {isCreating ? 'Creating...' : 'Create PR'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default PRWorkflowPanel
