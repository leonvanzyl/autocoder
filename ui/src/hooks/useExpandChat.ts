/**
 * Hook for managing expand-project chat WebSocket connection
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { ChatMessage, ImageAttachment, ExpandChatServerMessage, ExpandChatClientMessage } from '../lib/types'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface CreatedFeature {
  id: number
  name: string
  category: string
}

interface UseExpandChatOptions {
  projectName: string
  onComplete?: (totalAdded: number) => void
  onError?: (error: string) => void
}

interface UseExpandChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  isComplete: boolean
  connectionStatus: ConnectionStatus
  featuresCreated: number
  recentFeatures: CreatedFeature[]
  start: () => void
  sendMessage: (content: string, attachments?: ImageAttachment[]) => void
  finish: () => void
  disconnect: () => void
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

export function useExpandChat({
  projectName,
  onComplete,
  onError,
}: UseExpandChatOptions): UseExpandChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [featuresCreated, setFeaturesCreated] = useState(0)
  const [recentFeatures, setRecentFeatures] = useState<CreatedFeature[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const pingIntervalRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const isCompleteRef = useRef(false)
  const manuallyDisconnectedRef = useRef(false)

  useEffect(() => {
    isCompleteRef.current = isComplete
  }, [isComplete])

  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  const sendClientMessage = useCallback((msg: ExpandChatClientMessage) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify(msg))
  }, [])

  const connect = useCallback(() => {
    if (manuallyDisconnectedRef.current) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setConnectionStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/expand/ws/${encodeURIComponent(projectName)}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      reconnectAttempts.current = 0
      manuallyDisconnectedRef.current = false

      // Keep-alive ping
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          sendClientMessage({ type: 'ping' })
        }
      }, 30000)

      // Start/resume session
      sendClientMessage({ type: 'start' })
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }

      if (
        !manuallyDisconnectedRef.current &&
        reconnectAttempts.current < maxReconnectAttempts &&
        !isCompleteRef.current
      ) {
        reconnectAttempts.current++
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000)
        reconnectTimeoutRef.current = window.setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      setConnectionStatus('error')
      onError?.('WebSocket connection error')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ExpandChatServerMessage

        switch (data.type) {
          case 'text': {
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              if (last?.role === 'assistant' && last.isStreaming) {
                return [...prev.slice(0, -1), { ...last, content: last.content + data.content }]
              }
              return [
                ...prev,
                {
                  id: generateId(),
                  role: 'assistant',
                  content: data.content,
                  timestamp: new Date(),
                  isStreaming: true,
                },
              ]
            })
            break
          }

          case 'features_created': {
            setFeaturesCreated((prev) => prev + data.count)
            setRecentFeatures(data.features)
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Created ${data.count} new feature${data.count !== 1 ? 's' : ''}.`,
                timestamp: new Date(),
              },
            ])
            break
          }

          case 'expansion_complete': {
            setIsComplete(true)
            setIsLoading(false)

            // Finish current streaming message (if any)
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              if (last?.role === 'assistant' && last.isStreaming) {
                return [...prev.slice(0, -1), { ...last, isStreaming: false }]
              }
              return prev
            })

            onComplete?.(data.total_added)
            break
          }

          case 'response_done': {
            setIsLoading(false)
            setMessages((prev) => {
              const last = prev[prev.length - 1]
              if (last?.role === 'assistant' && last.isStreaming) {
                return [...prev.slice(0, -1), { ...last, isStreaming: false }]
              }
              return prev
            })
            break
          }

          case 'error': {
            setIsLoading(false)
            onError?.(data.content)
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Error: ${data.content}`,
                timestamp: new Date(),
              },
            ])
            break
          }

          case 'pong':
            break
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [projectName, onComplete, onError, sendClientMessage])

  const start = useCallback(() => {
    manuallyDisconnectedRef.current = false
    connect()
  }, [connect])

  const sendMessage = useCallback(
    (content: string, attachments?: ImageAttachment[]) => {
      const trimmed = content.trim()
      if ((!trimmed && (!attachments || attachments.length === 0)) || connectionStatus !== 'connected') return

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'user',
          content: trimmed,
          attachments,
          timestamp: new Date(),
        },
      ])
      setIsLoading(true)

      sendClientMessage({
        type: 'message',
        content: trimmed,
        attachments,
      })
    },
    [connectionStatus, sendClientMessage]
  )

  const finish = useCallback(() => {
    if (connectionStatus !== 'connected') return
    setIsLoading(true)
    sendClientMessage({ type: 'done' })
  }, [connectionStatus, sendClientMessage])

  const disconnect = useCallback(() => {
    manuallyDisconnectedRef.current = true
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    wsRef.current?.close()
    wsRef.current = null
    setConnectionStatus('disconnected')
  }, [])

  return {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    featuresCreated,
    recentFeatures,
    start,
    sendMessage,
    finish,
    disconnect,
  }
}

