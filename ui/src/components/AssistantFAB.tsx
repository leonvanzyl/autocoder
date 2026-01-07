/**
 * Floating Action Button for toggling the Assistant panel
 */

import { MessageCircle, X } from 'lucide-react'

interface AssistantFABProps {
  onClick: () => void
  isOpen: boolean
}

export function AssistantFAB({ onClick, isOpen }: AssistantFABProps) {
  return (
    <button
      onClick={onClick}
      className={`
        fixed bottom-6 right-6 z-50
        w-14 h-14
        flex items-center justify-center
        bg-[var(--color-neo-progress)] text-white
        border-3 border-[var(--color-neo-border)]
        rounded-full
        shadow-neo-md
        transition-all duration-200
        hover:shadow-neo-lg hover:-translate-y-0.5
        active:shadow-neo-sm active:translate-y-0.5
        ${isOpen ? 'rotate-0' : ''}
      `}
      title={isOpen ? 'Close Assistant (Press A)' : 'Open Assistant (Press A)'}
      aria-label={isOpen ? 'Close Assistant' : 'Open Assistant'}
    >
      {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
    </button>
  )
}
