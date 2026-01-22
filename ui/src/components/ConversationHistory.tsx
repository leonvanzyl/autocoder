/**
 * Conversation History Component
 *
 * Sidebar showing past assistant conversations with ability to load them.
 */

import { useState } from 'react'
import { MessageSquare, Trash2, Loader2 } from 'lucide-react'
import { ConfirmationDialog } from './ConfirmationDialog'
import type { AssistantConversation } from '../lib/types'

interface ConversationHistoryProps {
  conversations: AssistantConversation[]
  isLoading: boolean
  currentConversationId: number | null
  onLoadConversation: (id: number) => void
  onDeleteConversation: (id: number) => Promise<unknown>
  deleteInFlight?: boolean
  deleteError?: string | null
  onNewConversation: () => void
}

export function ConversationHistory({
  conversations,
  isLoading,
  currentConversationId,
  onLoadConversation,
  onDeleteConversation,
  deleteInFlight = false,
  deleteError = null,
  onNewConversation,
}: ConversationHistoryProps) {
  const [pendingDelete, setPendingDelete] = useState<number | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [localDeleteError, setLocalDeleteError] = useState<string | null>(null)

  const handleDeleteClick = (id: number) => {
    setPendingDelete(id)
    setShowConfirm(true)
    setLocalDeleteError(null)
  }

  const handleConfirmDelete = async () => {
    if (pendingDelete === null) return
    setLocalDeleteError(null)
    try {
      await onDeleteConversation(pendingDelete)
      setShowConfirm(false)
      setPendingDelete(null)
    } catch (e: any) {
      setLocalDeleteError(String(e?.message || e))
      setShowConfirm(true)
    }
  }

  const handleCancelDelete = () => {
    setShowConfirm(false)
    setPendingDelete(null)
    setLocalDeleteError(null)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="flex flex-col h-full bg-[var(--color-neo-bg)]">
      {/* Header */}
      <div className="px-4 py-3 border-b-2 border-[var(--color-neo-border)]">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-display font-bold text-sm">Chat History</h3>
          <button
            onClick={onNewConversation}
            className="text-xs neo-btn px-2 py-1"
            title="Start new conversation"
          >
            + New
          </button>
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-[var(--color-neo-text-secondary)]" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--color-neo-text-secondary)]">
            No conversations yet
          </div>
        ) : (
          <div className="py-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`
                  group px-4 py-2 mx-2 mb-1
                  border-2 border-[var(--color-neo-border)]
                  cursor-pointer
                  transition-all
                  ${
                    conv.id === currentConversationId
                      ? 'bg-[var(--color-neo-progress)] text-white'
                      : 'bg-white hover:bg-[var(--color-neo-hover-subtle)] hover:shadow-neo-md'
                  }
                `}
              >
                <div
                  className="flex items-start gap-2"
                  onClick={() => onLoadConversation(conv.id)}
                >
                  <MessageSquare size={14} className="mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {conv.title || `Conversation #${conv.id}`}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`
                        text-xs
                        ${conv.id === currentConversationId ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}
                      `}>
                        {conv.message_count} messages
                      </span>
                      <span className={`
                        text-xs
                        ${conv.id === currentConversationId ? 'text-white/80' : 'text-[var(--color-neo-text-secondary)]'}
                      `}>
                        • {formatDate(conv.updated_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteClick(conv.id)
                    }}
                    className="
                      opacity-0 group-hover:opacity-100
                      p-1 hover:bg-black/10 rounded
                      transition-opacity
                    "
                    title="Delete conversation"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={showConfirm}
        title="Delete Conversation?"
        message={
          <div className="space-y-3">
            <div>This action cannot be undone. All messages in this conversation will be permanently deleted.</div>
            {(localDeleteError || deleteError) && (
              <div className="neo-card p-3 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
                {localDeleteError || deleteError}
              </div>
            )}
          </div>
        }
        confirmText="Delete"
        cancelText="Cancel"
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        confirmDisabled={deleteInFlight}
        cancelDisabled={deleteInFlight}
        variant="danger"
      />
    </div>
  )
}
