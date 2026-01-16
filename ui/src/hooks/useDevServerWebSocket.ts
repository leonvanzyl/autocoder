/**
 * Dev Server WebSocket Hook
 *
 * Streams dev server status + stdout for a project.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { DevServerStatus, DevServerWSMessage } from '../lib/types'

interface DevServerState {
  status: DevServerStatus
  pid: number | null
  started_at: string | null
  command: string | null
  url: string | null
  api_port: number | null
  web_port: number | null
  logs: Array<{ line: string; timestamp: string }>
  isConnected: boolean
}

const MAX_LOGS = 500
const INITIAL_STATE: DevServerState = {
  status: 'stopped',
  pid: null,
  started_at: null,
  command: null,
  url: null,
  api_port: null,
  web_port: null,
  logs: [],
  isConnected: false,
}

export function useDevServerWebSocket(projectName: string | null) {
  const [state, setState] = useState<DevServerState>(INITIAL_STATE)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttempts = useRef(0)
  const isManualCloseRef = useRef(false)
  const projectRef = useRef<string | null>(projectName)

  const connect = useCallback(() => {
    if (!projectName) return
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }
    isManualCloseRef.current = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/projects/${encodeURIComponent(projectName)}/devserver`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setState(prev => ({ ...prev, isConnected: true }))
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const message: DevServerWSMessage = JSON.parse(event.data)

          if (message.type === 'devserver_status') {
            setState(prev => ({
              ...prev,
              status: message.status,
              pid: message.pid,
              started_at: message.started_at,
              command: message.command,
              url: message.url,
              api_port: message.api_port,
              web_port: message.web_port,
            }))
          } else if (message.type === 'devserver_log') {
            setState(prev => ({
              ...prev,
              logs: [
                ...prev.logs.slice(-MAX_LOGS + 1),
                { line: message.line, timestamp: message.timestamp },
              ],
            }))
          }
        } catch {
          // ignore
        }
      }

      ws.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }))
        wsRef.current = null
        if (isManualCloseRef.current) return
        if (projectRef.current !== projectName) return

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

  useEffect(() => {
    projectRef.current = projectName
    setState(INITIAL_STATE)

    if (!projectName) {
      if (wsRef.current) {
        isManualCloseRef.current = true
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    connect()
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        isManualCloseRef.current = true
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [projectName, connect])

  const clearLogs = useCallback(() => {
    setState(prev => ({ ...prev, logs: [] }))
  }, [])

  return { ...state, clearLogs }
}

