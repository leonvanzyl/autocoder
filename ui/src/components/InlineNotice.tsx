import { X } from 'lucide-react'

export type InlineNoticeType = 'success' | 'error' | 'info'

const STYLES: Record<InlineNoticeType, { border: string; bg: string; text: string }> = {
  success: {
    border: 'border-[var(--color-neo-done)]',
    bg: 'bg-[var(--color-neo-done)]/10',
    text: 'text-[var(--color-neo-text)]',
  },
  error: {
    border: 'border-[var(--color-neo-danger)]',
    bg: 'bg-[var(--color-neo-danger)]/10',
    text: 'text-[var(--color-neo-danger)]',
  },
  info: {
    border: 'border-[var(--color-neo-progress)]',
    bg: 'bg-[var(--color-neo-progress)]/10',
    text: 'text-[var(--color-neo-text)]',
  },
}

export function InlineNotice({
  type = 'info',
  message,
  onClose,
}: {
  type?: InlineNoticeType
  message: string
  onClose?: () => void
}) {
  const styles = STYLES[type]
  return (
    <div className={`neo-card p-3 border-3 ${styles.border} ${styles.bg}`}>
      <div className="flex items-start justify-between gap-3">
        <div className={`text-sm ${styles.text}`}>{message}</div>
        {onClose && (
          <button className="neo-btn neo-btn-secondary text-xs" onClick={onClose} title="Dismiss">
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  )
}
