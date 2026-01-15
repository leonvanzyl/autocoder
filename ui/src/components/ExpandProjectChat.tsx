/**
 * Expand Project Chat Component
 *
 * Chat interface for adding new features to an existing project.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, X, CheckCircle2, AlertCircle, Wifi, WifiOff, RotateCcw, Paperclip, Plus, Check } from 'lucide-react'
import { useExpandChat } from '../hooks/useExpandChat'
import { ChatMessage } from './ChatMessage'
import { TypingIndicator } from './TypingIndicator'
import type { ImageAttachment } from '../lib/types'

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5 MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png']

interface ExpandProjectChatProps {
  projectName: string
  onComplete: (featuresAdded: number) => void
  onCancel: () => void
}

export function ExpandProjectChat({ projectName, onComplete, onCancel }: ExpandProjectChatProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pendingAttachments, setPendingAttachments] = useState<ImageAttachment[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleError = useCallback((err: string) => setError(err), [])

  const {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    featuresCreated,
    start,
    sendMessage,
    finish,
    disconnect,
  } = useExpandChat({
    projectName,
    onComplete,
    onError: handleError,
  })

  useEffect(() => {
    start()
    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    if (!isLoading && inputRef.current) inputRef.current.focus()
  }, [isLoading])

  const handleSendMessage = () => {
    const trimmed = input.trim()
    if ((!trimmed && pendingAttachments.length === 0) || isLoading) return
    sendMessage(trimmed, pendingAttachments.length ? pendingAttachments : undefined)
    setInput('')
    setPendingAttachments([])
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return

    Array.from(files).forEach((file) => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(`Invalid file type: ${file.name}. Only JPEG and PNG are supported.`)
        return
      }
      if (file.size > MAX_FILE_SIZE) {
        setError(`File too large: ${file.name}. Maximum size is 5 MB.`)
        return
      }

      const reader = new FileReader()
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string
        const base64Data = dataUrl.split(',')[1]

        const attachment: ImageAttachment = {
          id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          filename: file.name,
          mimeType: file.type as 'image/jpeg' | 'image/png',
          base64Data,
          previewUrl: dataUrl,
          size: file.size,
        }

        setPendingAttachments((prev) => [...prev, attachment])
      }
      reader.onerror = () => setError(`Failed to read file: ${file.name}`)
      reader.readAsDataURL(file)
    })
  }, [])

  const handleRemoveAttachment = useCallback((id: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      handleFileSelect(e.dataTransfer.files)
    },
    [handleFileSelect]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const ConnectionIndicator = () => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <span className="flex items-center gap-1 text-xs text-[var(--color-neo-done)]">
            <Wifi size={12} />
            Connected
          </span>
        )
      case 'connecting':
        return (
          <span className="flex items-center gap-1 text-xs text-[var(--color-neo-pending)]">
            <Wifi size={12} className="animate-pulse" />
            Connecting...
          </span>
        )
      case 'error':
        return (
          <span className="flex items-center gap-1 text-xs text-[var(--color-neo-danger)]">
            <WifiOff size={12} />
            Error
          </span>
        )
      default:
        return (
          <span className="flex items-center gap-1 text-xs text-[var(--color-neo-text-secondary)]">
            <WifiOff size={12} />
            Disconnected
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col h-full bg-[var(--color-neo-bg)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)] bg-white">
        <div className="flex items-center gap-3">
          <h2 className="font-display font-bold text-lg text-[var(--color-neo-text)]">
            Expand Project: {projectName}
          </h2>
          <ConnectionIndicator />
          {featuresCreated > 0 && (
            <span className="flex items-center gap-1 text-sm text-[var(--color-neo-done)] font-bold">
              <Plus size={14} />
              {featuresCreated} added
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {!isComplete && featuresCreated > 0 && (
            <button
              onClick={finish}
              disabled={isLoading || connectionStatus !== 'connected'}
              className="neo-btn neo-btn-success text-sm"
              title="Finish and close this expansion"
            >
              <Check size={18} />
              <span className="hidden sm:inline">Finish</span>
            </button>
          )}

          <button onClick={onCancel} className="neo-btn neo-btn-ghost p-2" title="Close">
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-[var(--color-neo-danger)] text-white border-b-3 border-[var(--color-neo-border)]">
          <AlertCircle size={16} />
          <span className="flex-1 text-sm">{error}</span>
          <button onClick={() => setError(null)} className="p-1 hover:opacity-70 transition-opacity rounded">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <div className="neo-card p-6 max-w-md bg-white">
              <h3 className="font-display font-bold text-lg mb-2">
                Starting Project Expansion
              </h3>
              <p className="text-sm text-[var(--color-neo-text-secondary)]">
                Connecting to Claude to help you add new features...
              </p>
              {connectionStatus === 'error' && (
                <button onClick={start} className="neo-btn neo-btn-primary mt-4 text-sm">
                  <RotateCcw size={14} />
                  Retry
                </button>
              )}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {isLoading && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!isComplete && (
        <div
          className="p-4 border-t-3 border-[var(--color-neo-border)] bg-white"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {pendingAttachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="relative group border-3 border-[var(--color-neo-border)] p-1 bg-white"
                  style={{ boxShadow: 'var(--shadow-neo-sm)' }}
                >
                  <img
                    src={attachment.previewUrl}
                    alt={attachment.filename}
                    className="w-16 h-16 object-cover"
                  />
                  <button
                    onClick={() => handleRemoveAttachment(attachment.id)}
                    className="absolute -top-2 -right-2 bg-[var(--color-neo-danger)] text-white rounded-full p-0.5 border-2 border-[var(--color-neo-border)] hover:scale-110 transition-transform"
                    title="Remove attachment"
                  >
                    <X size={12} />
                  </button>
                  <span className="text-xs truncate block max-w-16 mt-1 text-center">
                    {attachment.filename.length > 10 ? `${attachment.filename.substring(0, 7)}...` : attachment.filename}
                  </span>
                </div>
              ))}
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png"
            multiple
            onChange={(e) => handleFileSelect(e.target.files)}
            className="hidden"
          />

          <div className="flex gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={connectionStatus !== 'connected'}
              className="neo-btn neo-btn-ghost p-3"
              title="Attach image (JPEG/PNG, max 5MB)"
            >
              <Paperclip size={18} />
            </button>

            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={pendingAttachments.length ? 'Add a message with your image(s)...' : 'Describe what to add...'}
              className="neo-input flex-1"
              disabled={isLoading || connectionStatus !== 'connected'}
            />

            <button
              onClick={handleSendMessage}
              disabled={(!input.trim() && pendingAttachments.length === 0) || isLoading || connectionStatus !== 'connected'}
              className="neo-btn neo-btn-primary px-6"
            >
              <Send size={18} />
            </button>
          </div>

          <p className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
            Press Enter to send. Drag & drop or click <Paperclip size={12} className="inline" /> to attach images.
          </p>
        </div>
      )}

      {/* Completion footer */}
      {isComplete && (
        <div className="p-4 border-t-3 border-[var(--color-neo-border)] bg-[var(--color-neo-done)] text-black">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={20} />
              <span className="font-bold">
                Added {featuresCreated} new feature{featuresCreated !== 1 ? 's' : ''}!
              </span>
            </div>
            <button onClick={() => onComplete(featuresCreated)} className="neo-btn bg-white">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

