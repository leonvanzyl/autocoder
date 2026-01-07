/**
 * Model Settings Panel
 * ===================
 *
 * UI component for configuring AI model selection.
 * Neobrutalist design matching the app's style.
 */

import { useState } from 'react'
import { X, Brain } from 'lucide-react'
import {
  useModelSettings,
  usePresets,
  useApplyPreset,
  useUpdateModelSettings,
} from '../hooks/useModelSettings'

interface ModelSettingsPanelProps {
  onClose: () => void
}

export function ModelSettingsPanel({ onClose }: ModelSettingsPanelProps) {
  const { data: settings, isLoading } = useModelSettings()
  const { data: presets } = usePresets()
  const applyPreset = useApplyPreset()
  const updateSettings = useUpdateModelSettings()

  const [selectedPreset, setSelectedPreset] = useState(settings?.preset || 'balanced')
  const [autoDetect, setAutoDetect] = useState(settings?.auto_detect_simple ?? true)

  const handlePresetChange = (preset: string) => {
    setSelectedPreset(preset)
    applyPreset.mutate(preset)
  }

  const handleAutoDetectToggle = () => {
    const newValue = !autoDetect
    setAutoDetect(newValue)
    updateSettings.mutate({ auto_detect_simple: newValue })
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <Brain className="text-[var(--color-neo-accent)]" size={32} />
            <h2 className="font-display text-2xl font-bold uppercase">
              Model Settings
            </h2>
          </div>
          <button
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2"
            aria-label="Close"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-pulse text-4xl">⏳</div>
            </div>
          ) : (
            <>
              {/* Preset Selection */}
              <div>
                <h3 className="font-display font-bold text-lg mb-3 uppercase">
                  📦 Model Preset
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {presets?.presets &&
                    Object.entries(presets.presets).map(([id, preset]) => (
                      <button
                        key={id}
                        onClick={() => handlePresetChange(id)}
                        className={`
                          neo-card p-4 text-left transition-all
                          ${
                            selectedPreset === id
                              ? 'ring-4 ring-[var(--color-neo-accent)] translate-x-[-4px] translate-y-[-4px]'
                              : ''
                          }
                        `}
                      >
                        <div className="font-display font-bold text-sm mb-2 uppercase">
                          {preset.name}
                        </div>
                        <div className="text-sm text-[var(--color-neo-text-secondary)] mb-3">
                          {preset.description}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {preset.models.map((model) => (
                            <span
                              key={model}
                              className="neo-badge font-mono text-xs"
                            >
                              {model.toUpperCase()}
                            </span>
                          ))}
                        </div>
                      </button>
                    ))}
                </div>
              </div>

              {/* Current Configuration */}
              {settings && (
                <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
                  <h3 className="font-display font-bold text-lg mb-3 uppercase">
                    ⚙️ Current Configuration
                  </h3>
                  <div className="space-y-2 font-mono text-sm">
                    <div className="flex justify-between">
                      <span className="text-[var(--color-neo-text-secondary)]">Preset:</span>
                      <span className="font-bold">{settings.preset}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--color-neo-text-secondary)]">Models:</span>
                      <span className="font-bold">
                        {settings.available_models.map((m) => m.toUpperCase()).join(' + ')}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--color-neo-text-secondary)]">Fallback:</span>
                      <span className="font-bold">{settings.fallback_model.toUpperCase()}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Category Mapping */}
              {settings?.category_mapping && (
                <div>
                  <h3 className="font-display font-bold text-lg mb-3 uppercase">
                    📋 Category Mapping
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(settings.category_mapping).map(([category, model]) => (
                      <div
                        key={category}
                        className="neo-card p-3 flex justify-between items-center"
                      >
                        <span className="font-display font-semibold capitalize text-sm">
                          {category}
                        </span>
                        <span className="neo-badge font-mono text-xs font-bold">
                          {model.toUpperCase()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Auto-Detect Toggle */}
              <div>
                <label className="neo-card p-4 flex items-center justify-between cursor-pointer">
                  <div>
                    <div className="font-display font-bold text-base mb-1">
                      Auto-Detect Simple Tasks
                    </div>
                    <div className="text-sm text-[var(--color-neo-text-secondary)]">
                      Automatically use cheaper models for simple tasks (tests, docs, etc.)
                    </div>
                  </div>
                  <button
                    onClick={handleAutoDetectToggle}
                    className={`
                      relative w-14 h-8 rounded-full transition-colors
                      ${autoDetect ? 'bg-[var(--color-neo-accent)]' : 'bg-[var(--color-neo-text-secondary)]'}
                    `}
                  >
                    <div
                      className={`
                        absolute top-1 w-6 h-6 bg-white rounded-full border-3 border-[var(--color-neo-border)]
                        transition-transform
                        ${autoDetect ? 'translate-x-7' : 'translate-x-1'}
                      `}
                    />
                  </button>
                </label>
              </div>

              {/* Info Box */}
              <div className="neo-card p-4 bg-[var(--color-neo-progress)]/10 border-[var(--color-neo-progress)]">
                <div className="font-display font-bold mb-1 text-[var(--color-neo-progress)]">
                  💡 Pro Tip
                </div>
                <div className="text-sm">
                  <strong className="font-bold">Balanced (Opus + Haiku)</strong> is recommended for
                  most Pro users. Opus handles complex features while Haiku tackles tests and
                  documentation.
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
