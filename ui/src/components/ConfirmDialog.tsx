/**
 * ConfirmDialog Component
 *
 * A reusable confirmation dialog following the neobrutalism design system.
 * Used to confirm destructive actions like deleting projects.
 */

import { AlertTriangle, X } from 'lucide-react'

interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning'
  isLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null

  const variantColors = {
    danger: {
      icon: 'var(--color-neo-danger)',
      button: 'neo-btn-danger',
    },
    warning: {
      icon: 'var(--color-neo-pending)',
      button: 'neo-btn-warning',
    },
  }

  const colors = variantColors[variant]

  return (
    <div className="neo-modal-backdrop" onClick={onCancel}>
      <div
        className="neo-modal w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <div
              className="p-2 border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]"
              style={{ backgroundColor: colors.icon }}
            >
              <AlertTriangle size={20} className="text-white" />
            </div>
            <h2 className="font-display font-bold text-lg text-[#1a1a1a]">
              {title}
            </h2>
          </div>
          <button
            onClick={onCancel}
            className="neo-btn neo-btn-ghost p-2"
            disabled={isLoading}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-[var(--color-neo-text-secondary)] mb-6">
            {message}
          </p>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              onClick={onCancel}
              className="neo-btn"
              disabled={isLoading}
            >
              {cancelLabel}
            </button>
            <button
              onClick={onConfirm}
              className={`neo-btn ${colors.button}`}
              disabled={isLoading}
            >
              {isLoading ? 'Deleting...' : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
