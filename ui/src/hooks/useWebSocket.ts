/**
 * WebSocket Hook for Real-time Updates
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import type { WSMessage, AgentStatus, DevServerStatus } from '../lib/types'

interface WebSocketState {
  progress: {
    passing: number
    in_progress: number
    total: number
    percentage: number
  }
  agentStatus: AgentStatus
  logs: Array<{ line: string; timestamp: string }>
  isConnected: boolean
  devServerStatus: DevServerStatus
  devServerUrl: string | null
  devLogs: Array<{ line: string; timestamp: string }>
}

const MAX_LOGS = 100 // Keep last 100 log lines

export function useProjectWebSocket(projectName: string | null) {
  const [state, setState] = useState<WebSocketState>({
    progress: { passing: 0, in_progress: 0, total: 0, percentage: 0 },
    agentStatus: 'stopped',
    logs: [],
    isConnected: false,
    devServerStatus: 'stopped',
    devServerUrl: null,
    devLogs: [],
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
              }))
              break

            case 'log':
              setState(prev => ({
                ...prev,
                logs: [
                  ...prev.logs.slice(-MAX_LOGS + 1),
                  { line: message.line, timestamp: message.timestamp },
                ],
              }))
              break

            case 'feature_update':
              // Feature updates will trigger a refetch via React Query
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

      ws.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }))
        wsRef.current = null

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

  // Connect when project changes
  useEffect(() => {
    // Reset state when project changes to clear stale data
    setState({
      progress: { passing: 0, in_progress: 0, total: 0, percentage: 0 },
      agentStatus: 'stopped',
      logs: [],
      isConnected: false,
      devServerStatus: 'stopped',
      devServerUrl: null,
      devLogs: [],
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

  // Clear logs function
  const clearLogs = useCallback(() => {
    setState(prev => ({ ...prev, logs: [] }))
  }, [])

  // Clear dev logs function
  const clearDevLogs = useCallback(() => {
    setState(prev => ({ ...prev, devLogs: [] }))
  }, [])

  return {
    ...state,
    clearLogs,
    clearDevLogs,
  }
}
