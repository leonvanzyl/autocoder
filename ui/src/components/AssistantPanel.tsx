/**
 * Assistant Panel Component
 *
 * Slide-in panel container for the project assistant chat.
 * Slides in from the right side of the screen.
 */

import { useState } from 'react'
import { X, Bot, History } from 'lucide-react'
import { AssistantChat } from './AssistantChat'
import { ConversationHistory } from './ConversationHistory'
import { useAssistantConversations } from '../hooks/useAssistantConversations'

interface AssistantPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

export function AssistantPanel({ projectName, isOpen, onClose }: AssistantPanelProps) {
  const [showHistory, setShowHistory] = useState(false)
  const [loadConversationId, setLoadConversationId] = useState<number | null>(null)
  const { conversations, isLoading, deleteConversation, refetch } = useAssistantConversations(
    isOpen ? projectName : null
  )

  const handleLoadConversation = (id: number) => {
    setLoadConversationId(id)
    setShowHistory(false)
  }

  const handleNewConversation = () => {
    setLoadConversationId(null)
    setShowHistory(false)
  }

  return (
    <>
      {/* Backdrop - click to close */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity duration-300"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`
          fixed right-0 top-0 bottom-0 z-50
          bg-white
          border-l-4 border-[var(--color-neo-border)]
          shadow-[-8px_0_0px_rgba(0,0,0,1)]
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
        style={{
          width: showHistory ? '700px' : '400px',
          maxWidth: '90vw',
        }}
        role="dialog"
        aria-label="Project Assistant"
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-progress)] flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="bg-white border-2 border-[var(--color-neo-border)] p-1.5 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              <Bot size={18} />
            </div>
            <div>
              <h2 className="font-display font-bold text-white">Project Assistant</h2>
              <p className="text-xs text-white/80 font-mono">{projectName}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setShowHistory(!showHistory)
                if (!showHistory) refetch()
              }}
              className="
                neo-btn neo-btn-ghost
                p-2
                bg-white/20 border-white/40
                hover:bg-white/30
                text-white
              "
              title="Toggle chat history"
            >
              <History size={18} />
            </button>
            <button
              onClick={onClose}
              className="
                neo-btn neo-btn-ghost
                p-2
                bg-white/20 border-white/40
                hover:bg-white/30
                text-white
              "
              title="Close Assistant (Press A)"
              aria-label="Close Assistant"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 flex overflow-hidden">
          {/* Conversation history sidebar */}
          {showHistory && (
            <div className="w-64 border-r-2 border-[var(--color-neo-border)] flex-shrink-0 overflow-hidden">
              <ConversationHistory
                conversations={conversations}
                isLoading={isLoading}
                currentConversationId={loadConversationId}
                onLoadConversation={handleLoadConversation}
                onDeleteConversation={deleteConversation}
                onNewConversation={handleNewConversation}
              />
            </div>
          )}

          {/* Chat area */}
          <div className="flex-1 overflow-hidden min-w-0">
            {isOpen && (
              <AssistantChat
                projectName={projectName}
                conversationId={loadConversationId}
                onConversationChange={setLoadConversationId}
              />
            )}
          </div>
        </div>
      </div>
    </>
  )
}
