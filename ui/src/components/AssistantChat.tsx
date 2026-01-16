/**
 * Assistant Chat Component
 *
 * Main chat interface for the project assistant.
 * Displays messages and handles user input.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Wifi, WifiOff, Image as ImageIcon, X } from 'lucide-react'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { ChatMessage } from './ChatMessage'
import type { ImageAttachment } from '../lib/types'

interface AssistantChatProps {
  projectName: string
  conversationId?: number | null
  onConversationChange?: (id: number) => void
}

export function AssistantChat({ projectName, conversationId: externalConversationId, onConversationChange }: AssistantChatProps) {
  const [inputValue, setInputValue] = useState('')
  const [attachments, setAttachments] = useState<ImageAttachment[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const currentConversationIdRef = useRef<number | null>(null)

  // Memoize the error handler to prevent infinite re-renders
  const handleError = useCallback((error: string) => {
    console.error('Assistant error:', error)
  }, [])

  const {
    messages,
    isLoading,
    connectionStatus,
    conversationId: internalConversationId,
    start,
    sendMessage,
  } = useAssistantChat({
    projectName,
    onError: handleError,
  })

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Notify parent when conversation ID changes
  useEffect(() => {
    if (internalConversationId && onConversationChange) {
      onConversationChange(internalConversationId)
    }
  }, [internalConversationId, onConversationChange])

  // Start or restart chat when conversation ID changes
  useEffect(() => {
    // Skip if we're already on this conversation
    if (currentConversationIdRef.current === (externalConversationId ?? null)) {
      return
    }

    currentConversationIdRef.current = externalConversationId ?? null
    start(externalConversationId ?? null)
  }, [start, externalConversationId])

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading])

  const handleSend = () => {
    const content = inputValue.trim()
    if ((!content && attachments.length === 0) || isLoading) return

    sendMessage(content, attachments)
    setInputValue('')
    setAttachments([])
  }

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    Array.from(files).forEach((file) => {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        handleError('Only image files are allowed')
        return
      }

      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        handleError('Image file too large (max 10MB)')
        return
      }

      const reader = new FileReader()
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1] // Remove data: prefix
        const mimeType = file.type as 'image/jpeg' | 'image/png'

        const attachment: ImageAttachment = {
          id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          filename: file.name,
          mimeType,
          base64Data: base64,
          previewUrl: `data:${mimeType};base64,${base64}`,
          size: file.size,
        }

        setAttachments((prev) => [...prev, attachment])
      }
      reader.readAsDataURL(file)
    })

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id))
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
            <span className="text-xs text-[var(--color-neo-text-secondary)]">Connected</span>
          </>
        ) : connectionStatus === 'connecting' ? (
          <>
            <Loader2 size={14} className="text-[var(--color-neo-progress)] animate-spin" />
            <span className="text-xs text-[var(--color-neo-text-secondary)]">Connecting...</span>
          </>
        ) : (
          <>
            <WifiOff size={14} className="text-[var(--color-neo-danger)]" />
            <span className="text-xs text-[var(--color-neo-text-secondary)]">Disconnected</span>
          </>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto bg-[var(--color-neo-bg)]">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[var(--color-neo-text-secondary)] text-sm">
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
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {isLoading && messages.length > 0 && (
        <div className="px-4 py-2 border-t-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <div className="flex items-center gap-2 text-[var(--color-neo-text-secondary)] text-sm">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span>Thinking...</span>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t-3 border-[var(--color-neo-border)] p-4 bg-[var(--color-neo-card)]">
        {/* Attachment previews */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {attachments.map((attachment) => (
              <div
                key={attachment.id}
                className="relative border-2 border-[var(--color-neo-border)] p-1 bg-[var(--color-neo-bg)]"
                style={{ boxShadow: 'var(--shadow-neo-sm)' }}
              >
                <img
                  src={attachment.previewUrl}
                  alt={attachment.filename}
                  className="max-w-24 max-h-24 object-contain"
                />
                <button
                  onClick={() => removeAttachment(attachment.id)}
                  className="absolute -top-2 -right-2 bg-[var(--color-neo-danger)] text-white border-2 border-[var(--color-neo-border)] p-0.5 hover:opacity-90"
                  style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                  title="Remove image"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleImageUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || connectionStatus !== 'connected'}
            className="
              neo-btn
              px-3
              disabled:opacity-50 disabled:cursor-not-allowed
            "
            title="Attach images"
          >
            <ImageIcon size={18} />
          </button>
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the codebase..."
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
            disabled={(!inputValue.trim() && attachments.length === 0) || isLoading || connectionStatus !== 'connected'}
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
          Press Enter to send, Shift+Enter for new line • Images max 10MB each
        </p>
      </div>
    </div>
  )
}
