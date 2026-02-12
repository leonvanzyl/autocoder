import { useState } from 'react'
import { ChevronDown, ChevronUp, Code, FlaskConical, Clock, Lock, Sparkles } from 'lucide-react'
import { OrchestratorAvatar } from './OrchestratorAvatar'
import type { OrchestratorStatus, OrchestratorState } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface OrchestratorStatusCardProps {
  status: OrchestratorStatus
}

// Get a friendly state description
function getStateText(state: OrchestratorState): string {
  switch (state) {
    case 'idle':
      return 'Standing by...'
    case 'initializing':
      return 'Setting up features...'
    case 'scheduling':
      return 'Planning next moves...'
    case 'spawning':
      return 'Deploying agents...'
    case 'monitoring':
      return 'Watching progress...'
    case 'complete':
      return 'Mission accomplished!'
    case 'draining':
      return 'Draining agents...'
    case 'paused':
      return 'Paused'
    default:
      return 'Orchestrating...'
  }
}

// Get state color
function getStateColor(state: OrchestratorState): string {
  switch (state) {
    case 'complete':
      return 'text-primary'
    case 'spawning':
      return 'text-primary'
    case 'scheduling':
    case 'monitoring':
      return 'text-primary'
    case 'initializing':
      return 'text-yellow-600 dark:text-yellow-400'
    case 'draining':
      return 'text-amber-600 dark:text-amber-400'
    case 'paused':
      return 'text-muted-foreground'
    default:
      return 'text-muted-foreground'
  }
}

// Format timestamp to relative time
function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now.getTime() - then.getTime()
  const diffSecs = Math.floor(diffMs / 1000)

  if (diffSecs < 5) return 'just now'
  if (diffSecs < 60) return `${diffSecs}s ago`
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins}m ago`
  return `${Math.floor(diffMins / 60)}h ago`
}

export function OrchestratorStatusCard({ status }: OrchestratorStatusCardProps) {
  const [showEvents, setShowEvents] = useState(false)

  return (
    <Card className="mb-4 bg-primary/10 border-primary/30 py-4">
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <OrchestratorAvatar state={status.state} size="md" />

          {/* Main content */}
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-lg text-primary">
                Maestro
              </span>
              <span className={`text-sm font-medium ${getStateColor(status.state)}`}>
                {getStateText(status.state)}
              </span>
            </div>

            {/* Current message */}
            <p className="text-sm text-foreground mb-3 line-clamp-2">
              {status.message}
            </p>

            {/* Status badges row */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Coding agents badge */}
              <Badge variant="outline" className="bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700">
                <Code size={12} />
                Coding: {status.codingAgents}
              </Badge>

              {/* Testing agents badge */}
              <Badge variant="outline" className="bg-purple-100 text-purple-700 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700">
                <FlaskConical size={12} />
                Testing: {status.testingAgents}
              </Badge>

              {/* Ready queue badge */}
              <Badge variant="outline" className="bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700">
                <Clock size={12} />
                Ready: {status.readyCount}
              </Badge>

              {/* Blocked badge (only show if > 0) */}
              {status.blockedCount > 0 && (
                <Badge variant="outline" className="bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700">
                  <Lock size={12} />
                  Blocked: {status.blockedCount}
                </Badge>
              )}
            </div>
          </div>

          {/* Recent events toggle */}
          {status.recentEvents.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowEvents(!showEvents)}
              className="text-primary hover:bg-primary/10"
            >
              <Sparkles size={12} />
              Activity
              {showEvents ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </Button>
          )}
        </div>

        {/* Collapsible recent events */}
        {showEvents && status.recentEvents.length > 0 && (
          <div className="mt-3 pt-3 border-t border-primary/20">
            <div className="space-y-1.5">
              {status.recentEvents.map((event, idx) => (
                <div
                  key={`${event.timestamp}-${idx}`}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="text-primary shrink-0 font-mono">
                    {formatRelativeTime(event.timestamp)}
                  </span>
                  <span className="text-foreground">
                    {event.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
