/**
 * Settings Modal
 * ==============
 *
 * Quick run configuration for the next start.
 *
 * Keep the modal lightweight (small monitors). Full settings live on the Settings page.
 */

import { useMemo } from 'react'
import { X, Settings as SettingsIcon, SlidersHorizontal, ExternalLink } from 'lucide-react'

export interface RunSettings {
  mode: 'standard' | 'parallel'
  parallelCount: number
  parallelPreset: 'quality' | 'balanced' | 'economy' | 'cheap' | 'experimental' | 'custom'
}

interface SettingsModalProps {
  onClose: () => void
  yoloEnabled: boolean
  settings: RunSettings
  onChange: (next: RunSettings) => void
  onOpenSettingsPage?: () => void
}

export function SettingsModal({
  onClose,
  yoloEnabled,
  settings,
  onChange,
  onOpenSettingsPage,
}: SettingsModalProps) {
  const canUseParallel = !yoloEnabled

  const modeOptions = useMemo(
    () => [
      { id: 'standard' as const, label: 'Standard', help: 'Single agent run.' },
      { id: 'parallel' as const, label: 'Parallel', help: 'Worktree + multiple agents.' },
    ],
    []
  )

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-5xl h-[100dvh] sm:h-auto sm:max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <SettingsIcon className="text-[var(--color-neo-accent)]" size={28} />
            <h2 className="font-display text-2xl font-bold uppercase">Settings</h2>
          </div>
          <div className="flex items-center gap-2">
            {onOpenSettingsPage && (
              <button
                onClick={onOpenSettingsPage}
                className="neo-btn neo-btn-secondary text-sm"
                title="Open the full Settings page"
              >
                <ExternalLink size={18} />
                <span className="hidden sm:inline">Open</span>
              </button>
            )}
            <button onClick={onClose} className="neo-btn neo-btn-ghost p-2" aria-label="Close">
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-110px)]">
          <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
            <div className="font-display font-bold uppercase mb-2">Applies next start</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Start/stop controls stay in the header. Use the Settings page for Models + Advanced.
            </div>
          </div>

          {/* Mode */}
          <div className="mt-6">
            <div className="font-display font-bold uppercase text-sm mb-2 flex items-center gap-2">
              <SlidersHorizontal size={18} />
              Run Mode
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {modeOptions.map((opt) => {
                const disabled = opt.id === 'parallel' && !canUseParallel
                const active = settings.mode === opt.id
                return (
                  <button
                    key={opt.id}
                    className={`neo-card p-4 text-left transition-all ${
                      active ? 'ring-4 ring-[var(--color-neo-accent)] translate-x-[-4px] translate-y-[-4px]' : ''
                    } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                    disabled={disabled}
                    onClick={() => onChange({ ...settings, mode: opt.id })}
                    title={disabled ? 'Disable YOLO to enable parallel mode' : opt.help}
                  >
                    <div className="font-display font-bold uppercase">{opt.label}</div>
                    <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">{opt.help}</div>
                    {opt.id === 'parallel' && yoloEnabled && (
                      <div className="text-xs font-mono mt-2 text-[var(--color-neo-danger)]">
                        Disabled while YOLO is enabled
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Parallel settings */}
          {settings.mode === 'parallel' && (
            <div className="neo-card p-4 mt-6">
              <div className="font-display font-bold uppercase text-sm mb-3">Parallel</div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Agents</div>
                  <select
                    value={settings.parallelCount}
                    onChange={(e) => onChange({ ...settings, parallelCount: Number(e.target.value) })}
                    className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                  >
                    <option value={1}>1 agent</option>
                    <option value={2}>2 agents</option>
                    <option value={3}>3 agents</option>
                    <option value={4}>4 agents</option>
                    <option value={5}>5 agents</option>
                  </select>
                </div>
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Preset (from Models)</div>
                  <div className="neo-card p-3 bg-[var(--color-neo-bg)] flex items-center justify-between">
                    <span className="font-mono text-sm font-bold">{settings.parallelPreset}</span>
                    {onOpenSettingsPage && (
                      <button
                        className="neo-btn neo-btn-secondary text-sm py-2 px-3"
                        onClick={onOpenSettingsPage}
                        title="Change models/presets in the Settings page"
                      >
                        Open
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
