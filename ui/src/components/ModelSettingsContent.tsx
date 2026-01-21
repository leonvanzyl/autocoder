/**
 * Model Settings Content
 * ======================
 *
 * Reusable content for configuring model selection settings.
 * (Wrapped by `ModelSettingsPanel` and also embedded in the unified Settings modal.)
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Brain, Info } from 'lucide-react'
import { useApplyPreset, useModelSettings, usePresets, useUpdateModelSettings } from '../hooks/useModelSettings'
import { InlineNotice, type InlineNoticeType } from './InlineNotice'
import { HelpModal } from './HelpModal'

export function ModelSettingsContent({
  projectName,
  onPresetApplied,
}: {
  projectName?: string | null
  onPresetApplied?: (presetId: string) => void
}) {
  const { data: settings, isLoading } = useModelSettings(projectName)
  const { data: presets } = usePresets()
  const applyPreset = useApplyPreset()
  const updateSettings = useUpdateModelSettings()

  const [selectedPreset, setSelectedPreset] = useState('balanced')
  const [autoDetect, setAutoDetect] = useState(true)
  const [mode, setMode] = useState<'preset' | 'custom'>('preset')
  const [customModels, setCustomModels] = useState<{ opus: boolean; sonnet: boolean; haiku: boolean }>({
    opus: true,
    sonnet: false,
    haiku: true,
  })
  const [assistantModel, setAssistantModel] = useState<'auto' | 'opus' | 'sonnet' | 'haiku'>('auto')
  const [showHelp, setShowHelp] = useState(false)
  const [notice, setNotice] = useState<{ type: InlineNoticeType; message: string } | null>(null)
  const noticeTimer = useRef<number | null>(null)

  useEffect(() => {
    if (settings?.preset) setSelectedPreset(settings.preset)
    if (typeof settings?.auto_detect_simple === 'boolean') setAutoDetect(settings.auto_detect_simple)
    if (settings?.preset === 'custom') {
      setMode('custom')
    } else {
      setMode('preset')
    }
    if (settings?.available_models) {
      setCustomModels({
        opus: settings.available_models.includes('opus'),
        sonnet: settings.available_models.includes('sonnet'),
        haiku: settings.available_models.includes('haiku'),
      })
    }
    if (settings && typeof settings.assistant_model !== 'undefined') {
      setAssistantModel(settings.assistant_model ? settings.assistant_model : 'auto')
    }
  }, [settings])

  useEffect(() => {
    return () => {
      if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    }
  }, [])

  const flash = (type: InlineNoticeType, message: string) => {
    setNotice({ type, message })
    if (noticeTimer.current) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2500)
  }

  const handlePresetChange = async (preset: string) => {
    setSelectedPreset(preset)
    try {
      await applyPreset.mutateAsync({ projectName, preset })
      onPresetApplied?.(preset)
      flash('success', 'Preset applied.')
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  const selectedCustomModels = useMemo(() => {
    const models: Array<'opus' | 'sonnet' | 'haiku'> = []
    if (customModels.opus) models.push('opus')
    if (customModels.sonnet) models.push('sonnet')
    if (customModels.haiku) models.push('haiku')
    return models
  }, [customModels])

  const applyCustomModels = async () => {
    if (selectedCustomModels.length === 0) return
    setMode('custom')
    try {
      await updateSettings.mutateAsync({ projectName, settings: { available_models: selectedCustomModels } })
      // The backend will set preset to "custom" unless it matches a known preset.
      onPresetApplied?.('custom')
      flash('success', 'Custom model selection saved.')
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  const handleAutoDetectToggle = () => {
    const newValue = !autoDetect
    setAutoDetect(newValue)
    updateSettings.mutate(
      { projectName, settings: { auto_detect_simple: newValue } },
      {
        onSuccess: () => flash('success', 'Auto-detect updated.'),
        onError: (e: any) => flash('error', String(e?.message || e)),
      }
    )
  }

  const applyAssistantModel = async (next: 'auto' | 'opus' | 'sonnet' | 'haiku') => {
    setAssistantModel(next)
    try {
      await updateSettings.mutateAsync({ projectName, settings: { assistant_model: next === 'auto' ? null : next } })
      flash('success', 'Assistant model saved.')
    } catch (e: any) {
      flash('error', String(e?.message || e))
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse text-4xl">…</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {notice && (
        <InlineNotice type={notice.type} message={notice.message} onClose={() => setNotice(null)} />
      )}
      {/* Mode toggle (compact) */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-display font-bold uppercase">Models</div>
        <div className="flex gap-2">
          <button
            className="neo-btn neo-btn-secondary text-sm"
            onClick={() => setShowHelp(true)}
            title="Explain model settings"
          >
            <Info size={16} />
            Help
          </button>
          <button
            className={`neo-btn text-sm ${mode === 'preset' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setMode('preset')}
            title="Use presets"
          >
            Presets
          </button>
          <button
            className={`neo-btn text-sm ${mode === 'custom' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setMode('custom')}
            title="Choose models manually"
          >
            Custom
          </button>
        </div>
      </div>

      {/* Preset Selection */}
      {mode === 'preset' && (
        <div>
        <div className="flex items-center gap-2 mb-3">
          <Brain className="text-[var(--color-neo-accent)]" size={18} />
          <h3 className="font-display font-bold text-lg uppercase">Model Presets</h3>
        </div>

        {/* Compact dropdown on small screens */}
        <div className="sm:hidden neo-card p-3 mb-3 bg-[var(--color-neo-bg)]">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Preset</div>
          <select
            value={selectedPreset}
            onChange={(e) => handlePresetChange(e.target.value)}
            className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
          >
            {presets?.presets &&
              Object.entries(presets.presets).map(([id, preset]) => (
                <option key={id} value={id}>
                  {preset.name}
                </option>
              ))}
          </select>
        </div>

        <div className="hidden sm:grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {presets?.presets &&
            Object.entries(presets.presets).map(([id, preset]) => (
              <button
                key={id}
                onClick={() => handlePresetChange(id)}
                className={`
                  neo-card p-3 text-left transition-colors duration-200
                  ${selectedPreset === id ? 'ring-4 ring-[var(--color-neo-accent)] shadow-neo-lg' : ''}
                `}
              >
                <div className="font-display font-bold text-sm mb-2 uppercase">{preset.name}</div>
                <div className="text-sm text-[var(--color-neo-text-secondary)] mb-3">{preset.description}</div>
                <div className="flex flex-wrap gap-1.5">
                  {preset.models.map((model) => (
                    <span key={model} className="neo-badge font-mono text-xs">
                      {model.toUpperCase()}
                    </span>
                  ))}
                </div>
              </button>
            ))}
        </div>
        </div>
      )}

      {/* Custom model selection */}
      {mode === 'custom' && (
        <div className="neo-card p-4">
          <div className="font-display font-bold uppercase mb-3">Custom Models</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
              <span className="font-display font-bold text-sm">Opus</span>
              <input
                type="checkbox"
                checked={customModels.opus}
                onChange={(e) => setCustomModels({ ...customModels, opus: e.target.checked })}
                className="w-5 h-5"
              />
            </label>
            <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
              <span className="font-display font-bold text-sm">Sonnet</span>
              <input
                type="checkbox"
                checked={customModels.sonnet}
                onChange={(e) => setCustomModels({ ...customModels, sonnet: e.target.checked })}
                className="w-5 h-5"
              />
            </label>
            <label className="neo-card p-3 flex items-center justify-between cursor-pointer">
              <span className="font-display font-bold text-sm">Haiku</span>
              <input
                type="checkbox"
                checked={customModels.haiku}
                onChange={(e) => setCustomModels({ ...customModels, haiku: e.target.checked })}
                className="w-5 h-5"
              />
            </label>
          </div>

          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="text-sm text-[var(--color-neo-text-secondary)] font-mono">
              Selected: {selectedCustomModels.length ? selectedCustomModels.join(', ') : '(none)'}
            </div>
            <button
              className="neo-btn neo-btn-primary text-sm"
              onClick={applyCustomModels}
              disabled={selectedCustomModels.length === 0 || updateSettings.isPending}
              title="Apply custom model selection"
            >
              Apply
            </button>
          </div>
        </div>
      )}

      {/* Current Configuration (collapsed by default) */}
      {settings && (
        <details className="neo-card p-4 bg-[var(--color-neo-bg)]">
          <summary className="cursor-pointer font-display font-bold text-lg uppercase">Current Configuration</summary>
          <div className="mt-3 space-y-2 font-mono text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-neo-text-secondary)]">Preset:</span>
              <span className="font-bold">{settings.preset}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-neo-text-secondary)]">Models:</span>
              <span className="font-bold">{settings.available_models.map((m) => m.toUpperCase()).join(' + ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-neo-text-secondary)]">Fallback:</span>
              <span className="font-bold">{settings.fallback_model.toUpperCase()}</span>
            </div>
          </div>
        </details>
      )}

      {/* Category Mapping */}
      {settings?.category_mapping && (
        <details className="neo-card p-4">
          <summary className="cursor-pointer font-display font-bold text-lg uppercase">Category Mapping</summary>
          <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(settings.category_mapping).map(([category, model]) => (
              <div key={category} className="neo-card p-3 flex justify-between items-center">
                <span className="font-display font-semibold capitalize text-sm">{category}</span>
                <span className="neo-badge font-mono text-xs font-bold">{model.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Auto-Detect Toggle */}
      <div>
        <label className="neo-card p-4 flex items-center justify-between cursor-pointer">
          <div>
            <div className="font-display font-bold text-base mb-1">Auto-Detect Simple Tasks</div>
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

      {/* Assistant model override */}
      <div className="neo-card p-4">
        <div className="font-display font-bold text-base mb-1">Assistant Chat Model</div>
        <div className="text-sm text-[var(--color-neo-text-secondary)] mb-3">
          Controls the model used by the Web UI Assistant (not the feature workers).
        </div>
        <div className="flex flex-wrap gap-2">
          {(['auto', 'opus', 'sonnet', 'haiku'] as const).map((m) => (
            <button
              key={m}
              className={`neo-btn text-sm ${assistantModel === m ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
              onClick={() => applyAssistantModel(m)}
              disabled={updateSettings.isPending}
              title={m === 'auto' ? 'Use the best available model' : `Force ${m.toUpperCase()}`}
            >
              {m === 'auto' ? 'Auto' : m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <HelpModal isOpen={showHelp} title="Model Settings — what each knob does" onClose={() => setShowHelp(false)}>
        <div className="space-y-3 text-sm">
          <p>
            These settings control <span className="font-bold">Claude model selection</span> for feature workers and UI
            assistant chat.
          </p>
          <div className="neo-card p-3 bg-[var(--color-neo-bg)] space-y-2">
            <div className="font-display font-bold uppercase text-xs">Presets</div>
            <p className="text-[var(--color-neo-text-secondary)]">
              Quick bundles (Quality/Balanced/Economy). Best default for most runs.
            </p>
          </div>
          <div className="neo-card p-3 bg-[var(--color-neo-bg)] space-y-2">
            <div className="font-display font-bold uppercase text-xs">Custom</div>
            <p className="text-[var(--color-neo-text-secondary)]">
              Manually choose which tiers are available (Opus/Sonnet/Haiku). Useful for cost control.
            </p>
          </div>
          <div className="neo-card p-3 bg-[var(--color-neo-bg)] space-y-2">
            <div className="font-display font-bold uppercase text-xs">Auto‑Detect Simple Tasks</div>
            <p className="text-[var(--color-neo-text-secondary)]">
              Lets AutoCoder pick cheaper models for low‑risk tasks (tests/docs). Turn off if you want strict quality.
            </p>
          </div>
          <div className="text-xs text-[var(--color-neo-text-secondary)]">
            Assistant Chat Model only affects the in‑UI assistant, not feature workers.
          </div>
        </div>
      </HelpModal>
    </div>
  )
}
