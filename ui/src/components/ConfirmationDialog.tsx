/**
 * Confirmation Dialog Component
 *
 * Neobrutalist styled modal for confirming destructive actions.
 */

import { AlertTriangle } from 'lucide-react'

interface ConfirmationDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
  variant?: 'danger' | 'warning'
}

export function ConfirmationDialog({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'danger',
}: ConfirmationDialogProps) {
  if (!isOpen) return null

  const variantStyles = {
    danger: {
      iconBg: 'bg-[var(--color-neo-danger)]',
      confirmBg: 'bg-[var(--color-neo-danger)] hover:opacity-90',
    },
    warning: {
      iconBg: 'bg-[var(--color-neo-pending)]',
      confirmBg: 'bg-[var(--color-neo-pending)] hover:opacity-90',
    },
  }

  const styles = variantStyles[variant]

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-50 animate-fade-in"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="
            relative bg-white
            border-4 border-[var(--color-neo-border)]
            shadow-[8px_8px_0px_rgba(0,0,0,1)]
            max-w-md w-full
            animate-slide-in
          "
          onClick={(e) => e.stopPropagation()}
        >
          {/* Icon */}
          <div className={`absolute -top-6 left-6 ${styles.iconBg} border-3 border-[var(--color-neo-border)] p-3 shadow-[4px_4px_0px_rgba(0,0,0,1)]`}>
            <AlertTriangle size={24} className="text-white" />
          </div>

          {/* Content */}
          <div className="pt-8 px-6 pb-6">
            <h3 className="font-display font-bold text-xl mb-2">{title}</h3>
            <p className="text-[var(--color-neo-text-secondary)] mb-6">{message}</p>

            {/* Buttons */}
            <div className="flex gap-3 justify-end">
              <button
                onClick={onCancel}
                className="
                  neo-btn
                  px-4 py-2
                  font-medium
                "
              >
                {cancelText}
              </button>
              <button
                onClick={onConfirm}
                className={`
                  neo-btn
                  px-4 py-2
                  font-medium
                  text-white
                  border-[var(--color-neo-border)]
                  shadow-[3px_3px_0px_rgba(0,0,0,1)]
                  ${styles.confirmBg}
                `}
              >
                {confirmText}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
