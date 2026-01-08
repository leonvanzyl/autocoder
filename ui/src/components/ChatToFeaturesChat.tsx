/**
 * Chat-to-Features Chat Component
 *
 * Main chat interface for feature suggestions.
 * Displays messages, pending suggestions, and handles user input.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Wifi, WifiOff } from 'lucide-react'
import { useChatToFeatures } from '../hooks/useChatToFeatures'
import { ChatMessage } from './ChatMessage'
import { FeatureSuggestionCard } from './FeatureSuggestionCard'
import type { Feature } from '../lib/types'

interface ChatToFeaturesChatProps {
  projectName: string
  onFeatureCreated?: (feature: Feature) => void
}

export function ChatToFeaturesChat({
  projectName,
  onFeatureCreated,
}: ChatToFeaturesChatProps) {
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Memoize the callbacks to prevent infinite re-renders
  const handleError = useCallback((error: string) => {
    console.error('Chat-to-features error:', error)
  }, [])

  const handleFeatureCreated = useCallback(
    (feature: Feature) => {
      onFeatureCreated?.(feature)
    },
    [onFeatureCreated]
  )

  const {
    messages,
    isLoading,
    connectionStatus,
    pendingSuggestions,
    connect,
    sendMessage,
    acceptFeature,
    rejectFeature,
  } = useChatToFeatures({
    projectName,
    onFeatureCreated: handleFeatureCreated,
    onError: handleError,
  })

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingSuggestions])

  // Connect when component mounts
  useEffect(() => {
    connect()
  }, [connect])

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading && connectionStatus === 'connected') {
      inputRef.current?.focus()
    }
  }, [isLoading, connectionStatus])

  const handleSend = () => {
    const content = inputValue.trim()
    if (!content || isLoading) return

    sendMessage(content)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Connection status indicator */}
      <div className="flex items-center gap-2 px-4 py-2 border-b-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
        {connectionStatus === 'connected' ? (
          <>
            <Wifi size={14} className="text-[var(--color-neo-done)]" />
            <span className="text-xs text-[var(--color-neo-text-secondary)]">
              Connected
            </span>
          </>
        ) : connectionStatus === 'connecting' ? (
          <>
            <Loader2
              size={14}
              className="text-[var(--color-neo-progress)] animate-spin"
            />
            <span className="text-xs text-[var(--color-neo-text-secondary)]">
              Connecting...
            </span>
          </>
        ) : (
          <>
            <WifiOff size={14} className="text-[var(--color-neo-danger)]" />
            <span className="text-xs text-[var(--color-neo-text-secondary)]">
              Disconnected
            </span>
          </>
        )}
      </div>

      {/* Messages and suggestions area */}
      <div className="flex-1 overflow-y-auto bg-[var(--color-neo-bg)]">
        {messages.length === 0 && pendingSuggestions.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[var(--color-neo-text-secondary)] text-sm px-4 text-center">
            {connectionStatus === 'connecting' ? (
              <div className="flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                <span>Connecting...</span>
              </div>
            ) : (
              <span>
                Describe the features you want to add to your project, and
                I'll suggest structured implementations
              </span>
            )}
          </div>
        ) : (
          <div className="py-4">
            {/* Messages */}
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {/* Pending Suggestions */}
            {pendingSuggestions.length > 0 && (
              <div className="px-4 mt-4">
                <div className="mb-3 pb-2 border-b-2 border-[var(--color-neo-border)]">
                  <h4 className="font-display font-bold text-[var(--color-neo-text)]">
                    Suggested Features
                  </h4>
                  <p className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
                    Review and accept the features you want to add
                  </p>
                </div>
                <div className="space-y-3">
                  {pendingSuggestions.map((suggestion) => (
                    <FeatureSuggestionCard
                      key={suggestion.index}
                      suggestion={suggestion}
                      onAccept={() => acceptFeature(suggestion.index)}
                      onReject={() => rejectFeature(suggestion.index)}
                    />
                  ))}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {isLoading && messages.length > 0 && (
        <div className="px-4 py-2 border-t-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <div className="flex items-center gap-2 text-[var(--color-neo-text-secondary)] text-sm">
            <div className="flex gap-1">
              <span
                className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce"
                style={{ animationDelay: '0ms' }}
              />
              <span
                className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce"
                style={{ animationDelay: '150ms' }}
              />
              <span
                className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce"
                style={{ animationDelay: '300ms' }}
              />
            </div>
            <span>Analyzing your request...</span>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t-3 border-[var(--color-neo-border)] p-4 bg-white">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the features you want..."
            disabled={isLoading || connectionStatus !== 'connected'}
            className="
              flex-1
              neo-input
              resize-none
              min-h-[44px]
              max-h-[120px]
              py-2.5
            "
            rows={1}
          />
          <button
            onClick={handleSend}
            disabled={
              !inputValue.trim() ||
              isLoading ||
              connectionStatus !== 'connected'
            }
            className="
              neo-btn neo-btn-primary
              px-4
              disabled:opacity-50 disabled:cursor-not-allowed
            "
            title="Send message"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
        <p className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
