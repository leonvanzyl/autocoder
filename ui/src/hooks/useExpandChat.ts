/**
 * Hook for managing project expansion chat WebSocket connection
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { ChatMessage, ImageAttachment, ExpandChatServerMessage } from '../lib/types'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

interface CreatedFeature {
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
  const currentAssistantMessageRef = useRef<string | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const pingIntervalRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const isCompleteRef = useRef(false)
  const manuallyDisconnectedRef = useRef(false)

  // Keep isCompleteRef in sync with isComplete state
  useEffect(() => {
    isCompleteRef.current = isComplete
  }, [isComplete])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connect = useCallback(() => {
    // Don't reconnect if manually disconnected
    if (manuallyDisconnectedRef.current) {
      return
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

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

      // Start ping interval to keep connection alive
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30000)
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }

      // Attempt reconnection if not intentionally closed
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
            // Append text to current assistant message or create new one
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1]
              if (lastMessage?.role === 'assistant' && lastMessage.isStreaming) {
                // Append to existing streaming message
                return [
                  ...prev.slice(0, -1),
                  {
                    ...lastMessage,
                    content: lastMessage.content + data.content,
                  },
                ]
              } else {
                // Create new assistant message
                currentAssistantMessageRef.current = generateId()
                return [
                  ...prev,
                  {
                    id: currentAssistantMessageRef.current,
                    role: 'assistant',
                    content: data.content,
                    timestamp: new Date(),
                    isStreaming: true,
                  },
                ]
              }
            })
            break
          }

          case 'features_created': {
            // Features were created
            setFeaturesCreated((prev) => prev + data.count)
            setRecentFeatures(data.features)

            // Add system message about feature creation
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Created ${data.count} new feature${data.count !== 1 ? 's' : ''}!`,
                timestamp: new Date(),
              },
            ])
            break
          }

          case 'expansion_complete': {
            setIsComplete(true)
            setIsLoading(false)

            // Mark current message as done
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1]
              if (lastMessage?.role === 'assistant' && lastMessage.isStreaming) {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, isStreaming: false },
                ]
              }
              return prev
            })

            onComplete?.(data.total_added)
            break
          }

          case 'error': {
            setIsLoading(false)
            onError?.(data.content)

            // Add error as system message
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

          case 'pong': {
            // Keep-alive response, nothing to do
            break
          }

          case 'response_done': {
            // Response complete - hide loading indicator and mark message as done
            setIsLoading(false)

            // Mark current message as done streaming
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1]
              if (lastMessage?.role === 'assistant' && lastMessage.isStreaming) {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMessage, isStreaming: false },
                ]
              }
              return prev
            })
            break
          }
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [projectName, onComplete, onError])

  const start = useCallback(() => {
    connect()

    // Wait for connection then send start message (with timeout to prevent infinite loop)
    let attempts = 0
    const maxAttempts = 50 // 5 seconds max (50 * 100ms)
    const checkAndSend = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setIsLoading(true)
        wsRef.current.send(JSON.stringify({ type: 'start' }))
      } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
        if (attempts++ < maxAttempts) {
          setTimeout(checkAndSend, 100)
        } else {
          onError?.('Connection timeout')
          setIsLoading(false)
        }
      }
    }

    setTimeout(checkAndSend, 100)
  }, [connect, onError])

  const sendMessage = useCallback((content: string, attachments?: ImageAttachment[]) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onError?.('Not connected')
      return
    }

    // Add user message to chat (with attachments for display)
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'user',
        content,
        attachments,
        timestamp: new Date(),
      },
    ])

    setIsLoading(true)

    // Build message payload
    const payload: { type: string; content: string; attachments?: Array<{ filename: string; mimeType: string; base64Data: string }> } = {
      type: 'message',
      content,
    }

    // Add attachments if present (send base64 data, not preview URL)
    if (attachments && attachments.length > 0) {
      payload.attachments = attachments.map((a) => ({
        filename: a.filename,
        mimeType: a.mimeType,
        base64Data: a.base64Data,
      }))
    }

    // Send to server
    wsRef.current.send(JSON.stringify(payload))
  }, [onError])

  const disconnect = useCallback(() => {
    manuallyDisconnectedRef.current = true
    reconnectAttempts.current = maxReconnectAttempts // Prevent reconnection
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
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
    disconnect,
  }
}
