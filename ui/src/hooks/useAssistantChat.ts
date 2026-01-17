/**
 * Hook for managing assistant chat WebSocket connection
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { ChatMessage, AssistantChatServerMessage, ImageAttachment } from '../lib/types'
import { getAssistantConversation } from '../lib/api'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

interface UseAssistantChatOptions {
  projectName: string
  onError?: (error: string) => void
}

interface UseAssistantChatReturn {
  messages: ChatMessage[]
  isLoading: boolean
  isLoadingConversation: boolean
  connectionStatus: ConnectionStatus
  conversationId: number | null
  start: (conversationId?: number | null) => void
  sendMessage: (content: string, attachments?: ImageAttachment[]) => void
  disconnect: () => void
  clearMessages: () => void
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

export function useAssistantChat({
  projectName,
  onError,
}: UseAssistantChatOptions): UseAssistantChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingConversation, setIsLoadingConversation] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [conversationId, setConversationId] = useState<number | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const currentAssistantMessageRef = useRef<string | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const pingIntervalRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

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
    // Prevent multiple connection attempts
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    setConnectionStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/assistant/ws/${encodeURIComponent(projectName)}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      reconnectAttempts.current = 0

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
      if (reconnectAttempts.current < maxReconnectAttempts) {
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
        const data = JSON.parse(event.data) as AssistantChatServerMessage

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

          case 'tool_call': {
            // Show tool call as system message
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Using tool: ${data.tool}`,
                timestamp: new Date(),
              },
            ])
            break
          }

          case 'conversation_created': {
            setConversationId(data.conversation_id)
            break
          }

          case 'response_done': {
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
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [projectName, onError])

  const mergeMessages = useCallback((base: ChatMessage[], incoming: ChatMessage[]) => {
    if (incoming.length === 0) return base
    if (base.length === 0) return incoming
    const map = new Map<string, ChatMessage>()
    base.forEach((m) => map.set(m.id, m))
    incoming.forEach((m) => map.set(m.id, m))
    return Array.from(map.values())
  }, [])

  const start = useCallback(async (existingConversationId?: number | null) => {
    // Disconnect existing connection if any
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      // Clear ping interval
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }
      wsRef.current.close()
      wsRef.current = null
    }

    // Clear messages and reset state when switching conversations
    setMessages([])
    setConnectionStatus('disconnected')
    setConversationId(null)

    // Load conversation history if resuming
    if (existingConversationId) {
      setIsLoadingConversation(true)
      try {
        const conversation = await getAssistantConversation(projectName, existingConversationId)
        const historyMessages: ChatMessage[] = conversation.messages.map((m) => ({
          id: m.id.toString(),
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
          timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
        }))
        setMessages((prev) => mergeMessages(prev, historyMessages))
        setConversationId(existingConversationId)
      } catch (error) {
        console.error('Failed to load conversation:', error)
      } finally {
        setIsLoadingConversation(false)
      }
    } else {
      setIsLoadingConversation(false)
    }

    connect()

    // Wait for connection then send start message
    const checkAndSend = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setIsLoading(true)
        const payload: { type: string; conversation_id?: number } = { type: 'start' }
        if (existingConversationId) {
          payload.conversation_id = existingConversationId
          setConversationId(existingConversationId)
        }
        wsRef.current.send(JSON.stringify(payload))
      } else if (wsRef.current?.readyState === WebSocket.CONNECTING) {
        setTimeout(checkAndSend, 100)
      }
    }

    setTimeout(checkAndSend, 100)
  }, [connect, mergeMessages, projectName])

  const sendMessage = useCallback((content: string, attachments: ImageAttachment[] = []) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onError?.('Not connected')
      return
    }
    if (isLoadingConversation) {
      return
    }

    // Add user message to chat
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'user',
        content,
        attachments: attachments.length > 0 ? attachments : undefined,
        timestamp: new Date(),
      },
    ])

    setIsLoading(true)

    // Send to server
    wsRef.current.send(
      JSON.stringify({
        type: 'message',
        content,
        attachments: attachments.length > 0 ? attachments : undefined,
      })
    )
  }, [isLoadingConversation, onError])

  const disconnect = useCallback(() => {
    reconnectAttempts.current = maxReconnectAttempts // Prevent reconnection
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setConnectionStatus('disconnected')
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setConversationId(null)
  }, [])

  return {
    messages,
    isLoading,
    isLoadingConversation,
    connectionStatus,
    conversationId,
    start,
    sendMessage,
    disconnect,
    clearMessages,
  }
}
