/**
 * Assistant Chat Component
 *
 * Main chat interface for the project assistant.
 * Displays messages and handles user input.
 * Supports conversation history with resume functionality.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Send, Loader2, Wifi, WifiOff, Plus, History } from 'lucide-react'
import { useAssistantChat, type AssistantTier } from '../hooks/useAssistantChat'
import { useAvailableProviders, useSettings } from '../hooks/useProjects'
import { ChatMessage as ChatMessageComponent } from './ChatMessage'
import { ConversationHistory } from './ConversationHistory'
import { QuestionOptions } from './QuestionOptions'
import type { ChatMessage } from '../lib/types'
import { isSubmitEnter } from '../lib/keyboard'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface AssistantChatProps {
  projectName: string
  conversationId?: number | null
  initialMessages?: ChatMessage[]
  isLoadingConversation?: boolean
  onNewChat?: () => void
  onSelectConversation?: (id: number) => void
  onConversationCreated?: (id: number) => void
}

export function AssistantChat({
  projectName,
  conversationId,
  initialMessages,
  isLoadingConversation,
  onNewChat,
  onSelectConversation,
  onConversationCreated,
}: AssistantChatProps) {
  const [inputValue, setInputValue] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const hasStartedRef = useRef(false)
  const lastConversationIdRef = useRef<number | null | undefined>(undefined)

  // Memoize the error handler to prevent infinite re-renders
  const handleError = useCallback((error: string) => {
    console.error('Assistant error:', error)
  }, [])

  const {
    messages,
    isLoading,
    connectionStatus,
    conversationId: activeConversationId,
    currentQuestions,
    currentTier,
    start,
    sendMessage,
    sendAnswer,
    setTier,
    clearMessages,
  } = useAssistantChat({
    projectName,
    onError: handleError,
  })

  // Get provider info for tier model labels
  const { data: providersData } = useAvailableProviders()
  const { data: settings } = useSettings()
  const currentProvider = providersData?.providers?.find(p => p.id === (settings?.api_provider ?? 'claude'))
  const providerTiers = currentProvider?.tiers
  const hasMultipleTiers = providerTiers
    ? new Set(Object.values(providerTiers)).size > 1
    : false

  // Notify parent when a NEW conversation is created (not when switching to existing)
  // Track activeConversationId to fire callback only once when it transitions from null to a value
  const previousActiveConversationIdRef = useRef<number | null>(activeConversationId)
  useEffect(() => {
    const hadNoConversation = previousActiveConversationIdRef.current === null
    const nowHasConversation = activeConversationId !== null

    if (hadNoConversation && nowHasConversation && onConversationCreated) {
      onConversationCreated(activeConversationId)
    }

    previousActiveConversationIdRef.current = activeConversationId
  }, [activeConversationId, onConversationCreated])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Start or resume the chat session when component mounts or conversationId changes
  useEffect(() => {
    // Skip if we're loading conversation details
    if (isLoadingConversation) {
      return
    }

    // Only start if conversationId has actually changed
    if (lastConversationIdRef.current === conversationId && hasStartedRef.current) {
      return
    }

    // Check if we're switching to a different conversation (not initial mount)
    const isSwitching = lastConversationIdRef.current !== undefined &&
                        lastConversationIdRef.current !== conversationId

    lastConversationIdRef.current = conversationId
    hasStartedRef.current = true

    // Clear existing messages when switching conversations
    if (isSwitching) {
      clearMessages()
    }

    // Start the session with the conversation ID (or null for new)
    start(conversationId)
  }, [conversationId, isLoadingConversation, start, clearMessages])

  // Handle starting a new chat
  const handleNewChat = useCallback(() => {
    clearMessages()
    onNewChat?.()
  }, [clearMessages, onNewChat])

  // Handle selecting a conversation from history
  const handleSelectConversation = useCallback((id: number) => {
    setShowHistory(false)
    onSelectConversation?.(id)
  }, [onSelectConversation])

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading])

  const handleSend = () => {
    const content = inputValue.trim()
    if (!content || isLoading || isLoadingConversation) return

    sendMessage(content)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isSubmitEnter(e)) {
      e.preventDefault()
      handleSend()
    }
  }

  // Combine initial messages (from resumed conversation) with live messages
  // Merge both arrays with deduplication by message ID to prevent history loss
  const displayMessages = useMemo(() => {
    const isConversationSynced = lastConversationIdRef.current === conversationId && !isLoadingConversation

    // If not synced yet, show only initialMessages (or empty)
    if (!isConversationSynced) {
      return initialMessages ?? []
    }

    // If no initial messages, just show live messages
    if (!initialMessages || initialMessages.length === 0) {
      return messages
    }

    // Merge both arrays, deduplicating by ID (live messages take precedence)
    const messageMap = new Map<string, ChatMessage>()
    for (const msg of initialMessages) {
      messageMap.set(msg.id, msg)
    }
    for (const msg of messages) {
      messageMap.set(msg.id, msg)
    }
    return Array.from(messageMap.values())
  }, [initialMessages, messages, conversationId, isLoadingConversation])

  return (
    <div className="flex flex-col h-full">
      {/* Header with actions and connection status */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background">
        {/* Action buttons */}
        <div className="flex items-center gap-1 relative">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNewChat}
            className="h-8 w-8"
            title="New conversation"
            disabled={isLoading}
          >
            <Plus size={16} />
          </Button>
          <Button
            variant={showHistory ? 'secondary' : 'ghost'}
            size="icon"
            onClick={() => setShowHistory(!showHistory)}
            className="h-8 w-8"
            title="Conversation history"
          >
            <History size={16} />
          </Button>

          {/* History dropdown */}
          <ConversationHistory
            projectName={projectName}
            currentConversationId={conversationId ?? activeConversationId}
            isOpen={showHistory}
            onClose={() => setShowHistory(false)}
            onSelectConversation={handleSelectConversation}
          />
        </div>

        {/* Tier toggle + Connection status */}
        <div className="flex items-center gap-2">
          {/* Tier toggle - only show when provider has multiple distinct tier models */}
          {hasMultipleTiers && providerTiers && (
            <div className="flex rounded-md border border-border overflow-hidden" title="Model quality tier">
              {(['low', 'mid', 'high'] as AssistantTier[]).map((tier) => {
                const modelId = providerTiers[tier]
                const modelName = currentProvider?.models?.find(m => m.id === modelId)?.name
                // Short label: take last word (e.g., "Claude Haiku" -> "Haiku")
                const shortLabel = modelName?.split(' ').pop() ?? tier.toUpperCase()
                return (
                  <button
                    key={tier}
                    onClick={() => setTier(tier)}
                    className={`px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                      currentTier === tier
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-background text-muted-foreground hover:bg-muted hover:text-foreground'
                    }`}
                    title={`${tier} tier: ${modelName ?? modelId}`}
                  >
                    {shortLabel}
                  </button>
                )
              })}
            </div>
          )}

          {connectionStatus === 'connected' ? (
            <>
              <Wifi size={14} className="text-green-500" />
              <span className="text-xs text-muted-foreground">Connected</span>
            </>
          ) : connectionStatus === 'connecting' ? (
            <>
              <Loader2 size={14} className="text-primary animate-spin" />
              <span className="text-xs text-muted-foreground">Connecting...</span>
            </>
          ) : (
            <>
              <WifiOff size={14} className="text-destructive" />
              <span className="text-xs text-muted-foreground">Disconnected</span>
            </>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto bg-background">
        {isLoadingConversation ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <div className="flex items-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span>Loading conversation...</span>
            </div>
          </div>
        ) : displayMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            {isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                <span>Connecting to assistant...</span>
              </div>
            ) : (
              <span>Ask me anything about the codebase</span>
            )}
          </div>
        ) : (
          <div className="py-4">
            {displayMessages.map((message) => (
              <ChatMessageComponent key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {isLoading && displayMessages.length > 0 && (
        <div className="px-4 py-2 border-t border-border bg-background">
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span>Thinking...</span>
          </div>
        </div>
      )}

      {/* Structured questions from assistant */}
      {currentQuestions && (
        <div className="border-t border-border bg-background">
          <QuestionOptions
            questions={currentQuestions}
            onSubmit={sendAnswer}
          />
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-border p-4 bg-card">
        <div className="flex gap-2">
          <Textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the codebase..."
            disabled={isLoading || isLoadingConversation || connectionStatus !== 'connected' || !!currentQuestions}
            className="flex-1 resize-none min-h-[44px] max-h-[120px]"
            rows={1}
          />
          <Button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading || isLoadingConversation || connectionStatus !== 'connected' || !!currentQuestions}
            title="Send message"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {currentQuestions ? 'Select an option above to continue' : 'Press Enter to send, Shift+Enter for new line'}
        </p>
      </div>
    </div>
  )
}
