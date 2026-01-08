/**
 * Hook for managing chat-to-features WebSocket connection
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { createFeature } from '../lib/api'
import type { ChatMessage, Feature, FeatureCreate } from '../lib/types'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

// ============================================================================
// Type Definitions
// ============================================================================

export interface FeatureSuggestion {
  index: number
  name: string
  category: string
  description: string
  steps: string[]
  reasoning: string
}

interface ChatToFeaturesTextMessage {
  type: 'text'
  content: string
}

interface ChatToFeaturesFeatureSuggestionMessage {
  type: 'feature_suggestion'
  index: number
  feature: {
    name: string
    category: string
    description: string
    steps: string[]
    reasoning: string
  }
}

interface ChatToFeaturesFeatureCreatedMessage {
  type: 'feature_created'
  feature_index: number
  feature_id: number
  feature: Feature
}

interface ChatToFeaturesResponseDoneMessage {
  type: 'response_done'
}

interface ChatToFeaturesErrorMessage {
  type: 'error'
  content: string
}

interface ChatToFeaturesPongMessage {
  type: 'pong'
}

interface ChatToFeaturesFeatureRejectedMessage {
  type: 'feature_rejected'
  feature_index: number
}

interface ChatToFeaturesHistoryMessage {
  type: 'history'
  data: {
    conversation_id: number | null
    messages: Array<{
      id: string
      role: 'user' | 'assistant' | 'system'
      content: string
      timestamp: string
    }>
    pending_suggestions: Array<{
      index: number
      name: string
      category: string
      description: string
      steps: string[]
      reasoning: string
    }>
  }
}

type ChatToFeaturesServerMessage =
  | ChatToFeaturesTextMessage
  | ChatToFeaturesFeatureSuggestionMessage
  | ChatToFeaturesFeatureCreatedMessage
  | ChatToFeaturesResponseDoneMessage
  | ChatToFeaturesErrorMessage
  | ChatToFeaturesPongMessage
  | ChatToFeaturesFeatureRejectedMessage
  | ChatToFeaturesHistoryMessage

// ============================================================================
// Hook Options and Return Types
// ============================================================================

export interface UseChatToFeaturesOptions {
  projectName: string
  onFeatureCreated?: (feature: Feature) => void
  onError?: (error: string) => void
}

export interface UseChatToFeaturesReturn {
  // State
  messages: ChatMessage[]
  isLoading: boolean
  isConnected: boolean
  connectionStatus: ConnectionStatus
  pendingSuggestions: FeatureSuggestion[]

  // Actions
  connect: () => void
  disconnect: () => void
  sendMessage: (content: string) => void
  acceptFeature: (index: number) => Promise<void>
  rejectFeature: (index: number) => void
  clearHistory: () => void
}

// ============================================================================
// Helper Functions
// ============================================================================

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useChatToFeatures({
  projectName,
  onFeatureCreated,
  onError,
}: UseChatToFeaturesOptions): UseChatToFeaturesReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected')
  const [pendingSuggestions, setPendingSuggestions] = useState<FeatureSuggestion[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const currentAssistantMessageRef = useRef<string | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3
  const pingIntervalRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  // Compute isConnected from connectionStatus
  const isConnected = connectionStatus === 'connected'

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
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    setConnectionStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/projects/${encodeURIComponent(projectName)}/chat`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
      reconnectAttempts.current = 0

      // Send start message to initialize conversation
      ws.send(JSON.stringify({ type: 'start' }))

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
        const data = JSON.parse(event.data) as ChatToFeaturesServerMessage

        switch (data.type) {
          case 'text': {
            // Append text to current assistant message or create new one
            setMessages((prev: ChatMessage[]) => {
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

          case 'feature_suggestion': {
            // Add feature suggestion to pending list
            const suggestion: FeatureSuggestion = {
              index: data.index,
              name: data.feature.name,
              category: data.feature.category,
              description: data.feature.description,
              steps: data.feature.steps,
              reasoning: data.feature.reasoning,
            }

            setPendingSuggestions((prev: FeatureSuggestion[]) => [...prev, suggestion])

            // Also add a system message about the suggestion
            setMessages((prev: ChatMessage[]) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Feature suggested: ${suggestion.name} (${suggestion.category})`,
                timestamp: new Date(),
              },
            ])
            break
          }

          case 'feature_created': {
            // Remove from pending suggestions by index (server echoes back feature_index)
            setPendingSuggestions((prev: FeatureSuggestion[]) =>
              prev.filter((s: FeatureSuggestion) => s.index !== data.feature_index)
            )

            // Add system message about creation
            setMessages((prev: ChatMessage[]) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `Feature created: ${data.feature.name} (ID: ${data.feature_id})`,
                timestamp: new Date(),
              },
            ])

            // Notify parent component
            onFeatureCreated?.(data.feature)
            break
          }

          case 'response_done': {
            setIsLoading(false)

            // Mark current message as done streaming
            setMessages((prev: ChatMessage[]) => {
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
            setMessages((prev: ChatMessage[]) => [
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

          case 'feature_rejected': {
            // Server acknowledgment of rejection - no action needed
            // Client already removed the suggestion locally in rejectFeature()
            break
          }

          case 'history': {
            // Restore conversation history from server on reconnect
            const historyData = data.data
            if (historyData && historyData.messages.length > 0) {
              // Restore messages
              setMessages(
                historyData.messages.map((m: { id: string; role: 'user' | 'assistant' | 'system'; content: string; timestamp: string }) => ({
                  id: m.id,
                  role: m.role,
                  content: m.content,
                  timestamp: new Date(m.timestamp),
                }))
              )

              // Restore pending suggestions
              if (historyData.pending_suggestions) {
                setPendingSuggestions(historyData.pending_suggestions)
              }

              console.log(`Restored ${historyData.messages.length} messages from server`)
            }
            break
          }
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [projectName, onError, onFeatureCreated])

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

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        onError?.('Not connected to chat server')
        return
      }

      // Add user message to chat
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        {
          id: generateId(),
          role: 'user',
          content,
          timestamp: new Date(),
        },
      ])

      setIsLoading(true)

      // Send to server
      wsRef.current.send(
        JSON.stringify({
          type: 'message',
          content,
        })
      )
    },
    [onError]
  )

  const acceptFeature = useCallback(
    async (index: number) => {
      // Find the suggestion
      const suggestion = pendingSuggestions.find((s: FeatureSuggestion) => s.index === index)
      if (!suggestion) {
        onError?.('Feature suggestion not found')
        return
      }

      try {
        // Send accept message to WebSocket (server will create feature)
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({
              type: 'accept_feature',
              feature_index: index,
            })
          )
        } else {
          // Fallback: call REST API directly if WebSocket is not connected
          const featureData: FeatureCreate = {
            name: suggestion.name,
            category: suggestion.category,
            description: suggestion.description,
            steps: suggestion.steps,
          }

          const createdFeature = await createFeature(projectName, featureData)

          // Remove from pending
          setPendingSuggestions((prev: FeatureSuggestion[]) => prev.filter((s: FeatureSuggestion) => s.index !== index))

          // Add system message
          setMessages((prev: ChatMessage[]) => [
            ...prev,
            {
              id: generateId(),
              role: 'system',
              content: `Feature created: ${createdFeature.name} (ID: ${createdFeature.id})`,
              timestamp: new Date(),
            },
          ])

          // Notify parent
          onFeatureCreated?.(createdFeature)
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to create feature'
        onError?.(errorMessage)

        // Add error message to chat
        setMessages((prev: ChatMessage[]) => [
          ...prev,
          {
            id: generateId(),
            role: 'system',
            content: `Error creating feature: ${errorMessage}`,
            timestamp: new Date(),
          },
        ])
      }
    },
    [pendingSuggestions, projectName, onError, onFeatureCreated]
  )

  const rejectFeature = useCallback(
    (index: number) => {
      // Find the suggestion
      const suggestion = pendingSuggestions.find((s: FeatureSuggestion) => s.index === index)
      if (!suggestion) {
        return
      }

      // Send reject message to WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'reject_feature',
            feature_index: index,
          })
        )
      }

      // Remove from pending suggestions
      setPendingSuggestions((prev: FeatureSuggestion[]) => prev.filter((s: FeatureSuggestion) => s.index !== index))

      // Add system message
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        {
          id: generateId(),
          role: 'system',
          content: `Feature suggestion dismissed: ${suggestion.name}`,
          timestamp: new Date(),
        },
      ])
    },
    [pendingSuggestions]
  )

  const clearHistory = useCallback(() => {
    setMessages([])
    setPendingSuggestions([])
  }, [])

  return {
    messages,
    isLoading,
    isConnected,
    connectionStatus,
    pendingSuggestions,
    connect,
    disconnect,
    sendMessage,
    acceptFeature,
    rejectFeature,
    clearHistory,
  }
}
