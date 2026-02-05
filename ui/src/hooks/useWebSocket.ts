/**
 * WebSocket Hook for Real-time Updates
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import type {
  WSMessage,
  AgentStatus,
  DevServerStatus,
  ActiveAgent,
  AgentMascot,
  AgentLogEntry,
  OrchestratorStatus,
  OrchestratorEvent,
} from '../lib/types'

// Activity item for the feed
interface ActivityItem {
  agentName: string
  thought: string
  timestamp: string
  featureId: number
}

// Celebration trigger for overlay
interface CelebrationTrigger {
  agentName: AgentMascot | 'Unknown'
  featureName: string
  featureId: number
}

interface WebSocketState {
  progress: {
    passing: number
    in_progress: number
    total: number
    percentage: number
  }
  agentStatus: AgentStatus
  logs: Array<{ line: string; timestamp: string; featureId?: number; agentIndex?: number }>
  isConnected: boolean
  devServerStatus: DevServerStatus
  devServerUrl: string | null
  devLogs: Array<{ line: string; timestamp: string }>
  // Multi-agent state
  activeAgents: ActiveAgent[]
  recentActivity: ActivityItem[]
  // Per-agent logs for debugging (indexed by agentIndex)
  agentLogs: Map<number, AgentLogEntry[]>
  // Celebration queue to handle rapid successes without race conditions
  celebrationQueue: CelebrationTrigger[]
  celebration: CelebrationTrigger | null
  // Orchestrator state for Mission Control
  orchestratorStatus: OrchestratorStatus | null
}

const MAX_LOGS = 100 // Keep last 100 log lines
const MAX_ACTIVITY = 20 // Keep last 20 activity items
const MAX_AGENT_LOGS = 500 // Keep last 500 log lines per agent

export function useProjectWebSocket(projectName: string | null) {
  const [state, setState] = useState<WebSocketState>({
    progress: { passing: 0, in_progress: 0, total: 0, percentage: 0 },
    agentStatus: 'loading',
    logs: [],
    isConnected: false,
    devServerStatus: 'stopped',
    devServerUrl: null,
    devLogs: [],
    activeAgents: [],
    recentActivity: [],
    agentLogs: new Map(),
    celebrationQueue: [],
    celebration: null,
    orchestratorStatus: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttempts = useRef(0)

  const connect = useCallback(() => {
    if (!projectName) return

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/projects/${encodeURIComponent(projectName)}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setState(prev => ({ ...prev, isConnected: true }))
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data)

          switch (message.type) {
            case 'progress':
              setState(prev => ({
                ...prev,
                progress: {
                  passing: message.passing,
                  in_progress: message.in_progress,
                  total: message.total,
                  percentage: message.percentage,
                },
              }))
              break

            case 'agent_status':
              setState(prev => ({
                ...prev,
                agentStatus: message.status,
                // Clear active agents and orchestrator status when process stops OR crashes to prevent stale UI
                ...((message.status === 'stopped' || message.status === 'crashed') && {
                  activeAgents: [],
                  recentActivity: [],
                  orchestratorStatus: null,
                }),
              }))
              break

            case 'log':
              setState(prev => {
                // Update global logs
                const newLogs = [
                  ...prev.logs.slice(-MAX_LOGS + 1),
                  {
                    line: message.line,
                    timestamp: message.timestamp,
                    featureId: message.featureId,
                    agentIndex: message.agentIndex,
                  },
                ]

                // Also store in per-agent logs if we have an agentIndex
                let newAgentLogs = prev.agentLogs
                if (message.agentIndex !== undefined) {
                  newAgentLogs = new Map(prev.agentLogs)
                  const existingLogs = newAgentLogs.get(message.agentIndex) || []
                  const logEntry: AgentLogEntry = {
                    line: message.line,
                    timestamp: message.timestamp,
                    type: 'output',
                  }
                  newAgentLogs.set(
                    message.agentIndex,
                    [...existingLogs.slice(-MAX_AGENT_LOGS + 1), logEntry]
                  )
                }

                return { ...prev, logs: newLogs, agentLogs: newAgentLogs }
              })
              break

            case 'feature_update':
              // Feature updates will trigger a refetch via React Query
              break

            case 'agent_update':
              setState(prev => {
                // Log state change to per-agent logs
                const newAgentLogs = new Map(prev.agentLogs)
                const existingLogs = newAgentLogs.get(message.agentIndex) || []
                const stateLogEntry: AgentLogEntry = {
                  line: `[STATE] ${message.state}${message.thought ? `: ${message.thought}` : ''}`,
                  timestamp: message.timestamp,
                  type: message.state === 'error' ? 'error' : 'state_change',
                }
                newAgentLogs.set(
                  message.agentIndex,
                  [...existingLogs.slice(-MAX_AGENT_LOGS + 1), stateLogEntry]
                )

                // Get current logs for this agent to attach to ActiveAgent
                const agentLogsArray = newAgentLogs.get(message.agentIndex) || []

                // Update or add the agent in activeAgents
                const existingAgentIdx = prev.activeAgents.findIndex(
                  a => a.agentIndex === message.agentIndex
                )

                let newAgents: ActiveAgent[]
                if (message.state === 'success' || message.state === 'error') {
                  // Remove agent from active list on completion (success or failure)
                  // But keep the logs in agentLogs map for debugging
                  if (message.agentIndex === -1) {
                    // Synthetic completion: remove by featureId
                    // This handles agents that weren't tracked but still completed
                    newAgents = prev.activeAgents.filter(
                      a => a.featureId !== message.featureId
                    )
                  } else {
                    // Normal completion: remove by agentIndex
                    newAgents = prev.activeAgents.filter(
                      a => a.agentIndex !== message.agentIndex
                    )
                  }
                } else if (existingAgentIdx >= 0) {
                  // Update existing agent
                  newAgents = [...prev.activeAgents]
                  newAgents[existingAgentIdx] = {
                    agentIndex: message.agentIndex,
                    agentName: message.agentName,
                    agentType: message.agentType || 'coding',  // Default to coding for backwards compat
                    featureId: message.featureId,
                    featureIds: message.featureIds || [message.featureId],
                    featureName: message.featureName,
                    state: message.state,
                    thought: message.thought,
                    timestamp: message.timestamp,
                    logs: agentLogsArray,
                  }
                } else {
                  // Add new agent
                  newAgents = [
                    ...prev.activeAgents,
                    {
                      agentIndex: message.agentIndex,
                      agentName: message.agentName,
                      agentType: message.agentType || 'coding',  // Default to coding for backwards compat
                      featureId: message.featureId,
                      featureIds: message.featureIds || [message.featureId],
                      featureName: message.featureName,
                      state: message.state,
                      thought: message.thought,
                      timestamp: message.timestamp,
                      logs: agentLogsArray,
                    },
                  ]
                }

                // Add to activity feed if there's a thought
                let newActivity = prev.recentActivity
                if (message.thought) {
                  newActivity = [
                    {
                      agentName: message.agentName,
                      thought: message.thought,
                      timestamp: message.timestamp,
                      featureId: message.featureId,
                    },
                    ...prev.recentActivity.slice(0, MAX_ACTIVITY - 1),
                  ]
                }

                // Handle celebration queue on success
                let newCelebrationQueue = prev.celebrationQueue
                let newCelebration = prev.celebration

                if (message.state === 'success') {
                  const newCelebrationItem: CelebrationTrigger = {
                    agentName: message.agentName,
                    featureName: message.featureName,
                    featureId: message.featureId,
                  }

                  // If no celebration is showing, show this one immediately
                  // Otherwise, add to queue
                  if (!prev.celebration) {
                    newCelebration = newCelebrationItem
                  } else {
                    newCelebrationQueue = [...prev.celebrationQueue, newCelebrationItem]
                  }
                }

                return {
                  ...prev,
                  activeAgents: newAgents,
                  agentLogs: newAgentLogs,
                  recentActivity: newActivity,
                  celebrationQueue: newCelebrationQueue,
                  celebration: newCelebration,
                }
              })
              break

            case 'orchestrator_update':
              setState(prev => {
                const newEvent: OrchestratorEvent = {
                  eventType: message.eventType,
                  message: message.message,
                  timestamp: message.timestamp,
                  featureId: message.featureId,
                  featureName: message.featureName,
                }

                return {
                  ...prev,
                  orchestratorStatus: {
                    state: message.state,
                    message: message.message,
                    codingAgents: message.codingAgents ?? prev.orchestratorStatus?.codingAgents ?? 0,
                    testingAgents: message.testingAgents ?? prev.orchestratorStatus?.testingAgents ?? 0,
                    maxConcurrency: message.maxConcurrency ?? prev.orchestratorStatus?.maxConcurrency ?? 3,
                    readyCount: message.readyCount ?? prev.orchestratorStatus?.readyCount ?? 0,
                    blockedCount: message.blockedCount ?? prev.orchestratorStatus?.blockedCount ?? 0,
                    timestamp: message.timestamp,
                    recentEvents: [newEvent, ...(prev.orchestratorStatus?.recentEvents ?? []).slice(0, 4)],
                  },
                }
              })
              break

            case 'dev_log':
              setState(prev => ({
                ...prev,
                devLogs: [
                  ...prev.devLogs.slice(-MAX_LOGS + 1),
                  { line: message.line, timestamp: message.timestamp },
                ],
              }))
              break

            case 'dev_server_status':
              setState(prev => ({
                ...prev,
                devServerStatus: message.status,
                devServerUrl: message.url,
              }))
              break

            case 'pong':
              // Heartbeat response
              break
          }
        } catch {
          console.error('Failed to parse WebSocket message')
        }
      }

      ws.onclose = (event) => {
        setState(prev => ({ ...prev, isConnected: false }))
        wsRef.current = null

        // Don't retry on application-level errors (4xxx codes won't resolve on retry)
        const isAppError = event.code >= 4000 && event.code <= 4999
        if (isAppError) return

        // Exponential backoff reconnection
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
        reconnectAttempts.current++

        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, delay)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      // Failed to connect, will retry via onclose
    }
  }, [projectName])

  // Send ping to keep connection alive
  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }))
    }
  }, [])

  // Clear celebration and show next one from queue if available
  const clearCelebration = useCallback(() => {
    setState(prev => {
      // Pop the next celebration from the queue if available
      const [nextCelebration, ...remainingQueue] = prev.celebrationQueue
      return {
        ...prev,
        celebration: nextCelebration || null,
        celebrationQueue: remainingQueue,
      }
    })
  }, [])

  // Connect when project changes
  useEffect(() => {
    // Reset state when project changes to clear stale data
    // Use 'loading' for agentStatus to show loading indicator until WebSocket provides actual status
    setState({
      progress: { passing: 0, in_progress: 0, total: 0, percentage: 0 },
      agentStatus: 'loading',
      logs: [],
      isConnected: false,
      devServerStatus: 'stopped',
      devServerUrl: null,
      devLogs: [],
      activeAgents: [],
      recentActivity: [],
      agentLogs: new Map(),
      celebrationQueue: [],
      celebration: null,
      orchestratorStatus: null,
    })

    if (!projectName) {
      // Disconnect if no project
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    connect()

    // Ping every 30 seconds
    const pingInterval = setInterval(sendPing, 30000)

    return () => {
      clearInterval(pingInterval)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [projectName, connect, sendPing])

  // Defense-in-depth: cleanup stale agents for users who leave UI open for hours
  // This catches edge cases where completion messages are missed
  useEffect(() => {
    const STALE_THRESHOLD_MS = 30 * 60 * 1000 // 30 minutes

    const cleanup = setInterval(() => {
      setState(prev => {
        const now = Date.now()
        const fresh = prev.activeAgents.filter(a =>
          now - new Date(a.timestamp).getTime() < STALE_THRESHOLD_MS
        )
        if (fresh.length !== prev.activeAgents.length) {
          return { ...prev, activeAgents: fresh }
        }
        return prev
      })
    }, 60000) // Check every minute

    return () => clearInterval(cleanup)
  }, [])

  // Clear logs function
  const clearLogs = useCallback(() => {
    setState(prev => ({ ...prev, logs: [] }))
  }, [])

  // Clear dev logs function
  const clearDevLogs = useCallback(() => {
    setState(prev => ({ ...prev, devLogs: [] }))
  }, [])

  // Get logs for a specific agent (useful for debugging even after agent completes/fails)
  const getAgentLogs = useCallback((agentIndex: number): AgentLogEntry[] => {
    return state.agentLogs.get(agentIndex) || []
  }, [state.agentLogs])

  // Clear logs for a specific agent
  const clearAgentLogs = useCallback((agentIndex: number) => {
    setState(prev => {
      const newAgentLogs = new Map(prev.agentLogs)
      newAgentLogs.delete(agentIndex)
      return { ...prev, agentLogs: newAgentLogs }
    })
  }, [])

  return {
    ...state,
    clearLogs,
    clearDevLogs,
    clearCelebration,
    getAgentLogs,
    clearAgentLogs,
  }
}
