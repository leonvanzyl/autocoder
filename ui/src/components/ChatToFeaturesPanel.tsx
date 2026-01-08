/**
 * Chat-to-Features Panel Component
 *
 * Slide-in panel container for the chat-to-features interface.
 * Slides in from the left side of the screen (opposite of AssistantPanel).
 */

import { X, Sparkles } from 'lucide-react'
import { ChatToFeaturesChat } from './ChatToFeaturesChat'
import type { Feature } from '../lib/types'

interface ChatToFeaturesPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
  onFeatureCreated?: (feature: Feature) => void
}

export function ChatToFeaturesPanel({
  projectName,
  isOpen,
  onClose,
  onFeatureCreated,
}: ChatToFeaturesPanelProps) {
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
          fixed left-0 top-0 bottom-0 z-50
          w-[400px] max-w-[90vw]
          bg-white
          border-r-4 border-[var(--color-neo-border)]
          shadow-[8px_0_0px_rgba(0,0,0,1)]
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        role="dialog"
        aria-label="Feature Suggestions"
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b-3 border-[var(--color-neo-border)] bg-[var(--color-neo-pending)]">
          <div className="flex items-center gap-2">
            <div className="bg-white border-2 border-[var(--color-neo-border)] p-1.5 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              <Sparkles size={18} />
            </div>
            <div>
              <h2 className="font-display font-bold text-[var(--color-neo-text)]">
                Feature Suggestions
              </h2>
              <p className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
                {projectName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="
              neo-btn neo-btn-ghost
              p-2
              bg-white/20 border-white/40
              hover:bg-white/30
              text-[var(--color-neo-text)]
            "
            title="Close Feature Suggestions (F)"
            aria-label="Close Feature Suggestions"
          >
            <X size={18} />
          </button>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          {isOpen && (
            <ChatToFeaturesChat
              projectName={projectName}
              onFeatureCreated={onFeatureCreated}
            />
          )}
        </div>
      </div>
    </>
  )
}
