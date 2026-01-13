/**
 * Architect Assistant Panel Component
 *
 * Slide-in panel container for the Architect Assistant chat.
 * The Architect Assistant is the central command hub for project management.
 * Slides in from the right side of the screen.
 */

import { X, Cpu } from 'lucide-react'
import { AssistantChat } from './AssistantChat'

interface AssistantPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
  agentStatus?: 'running' | 'paused' | 'stopped'
}

export function AssistantPanel({ projectName, isOpen, onClose, agentStatus = 'stopped' }: AssistantPanelProps) {
  return (
    <>
      {/* Backdrop - click to close */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity duration-300"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`
          fixed right-0 top-0 bottom-0 z-50
          w-[480px] max-w-[90vw]
          bg-[#16161d]
          border-l border-white/10
          shadow-[-20px_0_60px_rgba(0,0,0,0.5)]
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
        role="dialog"
        aria-label="Architect Assistant"
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-gradient-to-r from-[#6366f1] via-[#8b5cf6] to-[#a855f7]">
          <div className="flex items-center gap-3">
            <div className="bg-white/15 backdrop-blur-sm rounded-xl p-2.5">
              <Cpu size={22} className="text-white" />
            </div>
            <div>
              <h2 className="font-semibold text-white text-lg tracking-tight">Architect Assistant</h2>
              <p className="text-xs text-white/70 font-mono">{projectName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
            title="Close Assistant (Press A)"
            aria-label="Close Assistant"
          >
            <X size={18} />
          </button>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden bg-[#0f0f14]">
          {isOpen && <AssistantChat projectName={projectName} agentStatus={agentStatus} />}
        </div>
      </div>
    </>
  )
}
