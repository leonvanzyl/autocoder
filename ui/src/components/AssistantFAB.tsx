/**
 * Floating Action Button for toggling the Assistant panel
 */

import { MessageCircle, X } from 'lucide-react'

interface AssistantFABProps {
  onClick: () => void
  isOpen: boolean
  bottomOffsetPx?: number
}

export function AssistantFAB({ onClick, isOpen, bottomOffsetPx }: AssistantFABProps) {
  return (
    <button
      onClick={onClick}
      className={`
        fixed right-6 z-50
        w-14 h-14
        flex items-center justify-center
        bg-[var(--color-neo-progress)] text-[var(--color-neo-text-on-bright)]
        border-3 border-[var(--color-neo-border)]
        shadow-neo-md
        transition-all duration-200
        hover:shadow-neo-lg
        active:shadow-neo-sm
        ${isOpen ? 'rotate-0' : ''}
      `}
      style={{ bottom: bottomOffsetPx ?? 64 }}
      title={isOpen ? 'Close Assistant (Press A)' : 'Open Assistant (Press A)'}
      aria-label={isOpen ? 'Close Assistant' : 'Open Assistant'}
    >
      {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
    </button>
  )
}
