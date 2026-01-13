import { useEffect, useRef, useState } from 'react'
import { X, Loader2, AlertCircle, Moon, Sun } from 'lucide-react'
import { useSettings, useUpdateSettings, useAvailableModels } from '../hooks/useProjects'

interface SettingsModalProps {
  onClose: () => void
}

// Dark mode helper functions
function getInitialDarkMode(): boolean {
  if (typeof window === 'undefined') return false
  const saved = localStorage.getItem('darkMode')
  if (saved !== null) return saved === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyDarkMode(isDark: boolean): void {
  if (isDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
  localStorage.setItem('darkMode', String(isDark))
}

export function SettingsModal({ onClose }: SettingsModalProps) {
  const { data: settings, isLoading, isError, refetch } = useSettings()
  const { data: modelsData } = useAvailableModels()
  const updateSettings = useUpdateSettings()
  const modalRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const [darkMode, setDarkMode] = useState(getInitialDarkMode)

  // Apply dark mode on initial load
  useEffect(() => {
    applyDarkMode(darkMode)
  }, [])

  const handleDarkModeToggle = () => {
    const newValue = !darkMode
    setDarkMode(newValue)
    applyDarkMode(newValue)
  }

  // Focus trap - keep focus within modal
  useEffect(() => {
    const modal = modalRef.current
    if (!modal) return

    // Focus the close button when modal opens
    closeButtonRef.current?.focus()

    const focusableElements = modal.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    const handleTabKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement?.focus()
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement?.focus()
        }
      }
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleTabKey)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('keydown', handleTabKey)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [onClose])

  const handleYoloToggle = () => {
    if (settings && !updateSettings.isPending) {
      updateSettings.mutate({ yolo_mode: !settings.yolo_mode })
    }
  }

  const handleModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ model: modelId })
    }
  }

  const models = modelsData?.models ?? []
  const isSaving = updateSettings.isPending

  return (
    <div
      className="neo-modal-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={modalRef}
        className="neo-modal w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="settings-title"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 id="settings-title" className="font-display text-xl font-bold">
            Settings
            {isSaving && (
              <Loader2 className="inline-block ml-2 animate-spin" size={16} />
            )}
          </h2>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2"
            aria-label="Close settings"
          >
            <X size={20} />
          </button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin" size={24} />
            <span className="ml-2">Loading settings...</span>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)] mb-4">
            <div className="flex items-center gap-2">
              <AlertCircle size={18} />
              <span>Failed to load settings</span>
            </div>
            <button
              onClick={() => refetch()}
              className="mt-2 underline text-sm"
            >
              Retry
            </button>
          </div>
        )}

        {/* Settings Content */}
        {settings && !isLoading && (
          <div className="space-y-6">
            {/* Dark Mode Toggle */}
            <div>
              <div className="flex items-center justify-between">
                <div>
                  <label
                    id="darkmode-label"
                    className="font-display font-bold text-base"
                  >
                    Dark Mode
                  </label>
                  <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                    Switch to dark theme
                  </p>
                </div>
                <button
                  onClick={handleDarkModeToggle}
                  className={`relative w-14 h-8 rounded-none border-3 border-[var(--color-neo-border)] transition-colors ${
                    darkMode
                      ? 'bg-[var(--color-neo-progress)]'
                      : 'bg-[var(--color-neo-card)]'
                  }`}
                  role="switch"
                  aria-checked={darkMode}
                  aria-labelledby="darkmode-label"
                >
                  <span
                    className={`absolute top-1 w-5 h-5 bg-[var(--color-neo-border)] transition-all flex items-center justify-center ${
                      darkMode ? 'left-7' : 'left-1'
                    }`}
                  >
                    {darkMode ? <Moon size={12} className="text-[var(--color-neo-bg)]" /> : <Sun size={12} className="text-[var(--color-neo-bg)]" />}
                  </span>
                </button>
              </div>
            </div>

            {/* YOLO Mode Toggle */}
            <div>
              <div className="flex items-center justify-between">
                <div>
                  <label
                    id="yolo-label"
                    className="font-display font-bold text-base"
                  >
                    YOLO Mode
                  </label>
                  <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                    Skip testing for rapid prototyping
                  </p>
                </div>
                <button
                  onClick={handleYoloToggle}
                  disabled={isSaving}
                  className={`relative w-14 h-8 rounded-none border-3 border-[var(--color-neo-border)] transition-colors ${
                    settings.yolo_mode
                      ? 'bg-[var(--color-neo-pending)]'
                      : 'bg-[var(--color-neo-card)]'
                  } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                  role="switch"
                  aria-checked={settings.yolo_mode}
                  aria-labelledby="yolo-label"
                >
                  <span
                    className={`absolute top-1 w-5 h-5 bg-[var(--color-neo-border)] transition-transform ${
                      settings.yolo_mode ? 'left-7' : 'left-1'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Model Selection - Radio Group */}
            <div>
              <label
                id="model-label"
                className="font-display font-bold text-base block mb-2"
              >
                Model
              </label>
              <div
                className="flex border-3 border-[var(--color-neo-border)]"
                role="radiogroup"
                aria-labelledby="model-label"
              >
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => handleModelChange(model.id)}
                    disabled={isSaving}
                    role="radio"
                    aria-checked={settings.model === model.id}
                    className={`flex-1 py-3 px-4 font-display font-bold text-sm transition-colors ${
                      settings.model === model.id
                        ? 'bg-[var(--color-neo-accent)] text-white'
                        : 'bg-[var(--color-neo-card)] text-[var(--color-neo-text)] hover:bg-[var(--color-neo-bg)]'
                    } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {model.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Update Error */}
            {updateSettings.isError && (
              <div className="p-3 bg-red-50 border-3 border-red-200 text-red-700 text-sm">
                Failed to save settings. Please try again.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
