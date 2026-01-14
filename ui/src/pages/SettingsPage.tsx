/**
 * Settings Page
 * =============
 *
 * Wider, less cramped settings hub. Mirrors the quick Settings modal but with an Advanced tab.
 */

import { useState } from 'react'
import { Settings as SettingsIcon, SlidersHorizontal, Brain, Sparkles, FileText } from 'lucide-react'
import { ModelSettingsContent } from '../components/ModelSettingsContent'
import { AdvancedSettingsContent } from '../components/AdvancedSettingsContent'
import { MultiModelGeneratePanel } from '../components/MultiModelGeneratePanel'
import { ProjectConfigEditor } from '../components/ProjectConfigEditor'
import type { RunSettings } from '../components/SettingsModal'

type SettingsPageTab = 'run' | 'models' | 'generate' | 'config' | 'advanced'

export function SettingsPage({
  initialTab = 'run',
  projectName,
  yoloEnabled,
  runSettings,
  onChangeRunSettings,
  onClose,
}: {
  initialTab?: SettingsPageTab
  projectName: string
  yoloEnabled: boolean
  runSettings: RunSettings
  onChangeRunSettings: (next: RunSettings) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<SettingsPageTab>(initialTab)

  const canUseParallel = !yoloEnabled

  return (
    <div className="space-y-6">
      <div className="neo-card p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <SettingsIcon className="text-[var(--color-neo-accent)]" size={28} />
            <div>
              <h2 className="font-display text-2xl font-bold uppercase">Settings</h2>
              <div className="text-sm text-[var(--color-neo-text-secondary)]">Run, models, and advanced configuration.</div>
            </div>
          </div>
          <button className="neo-btn neo-btn-secondary text-sm" onClick={onClose} title="Back to project">
            Back
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className={`neo-btn text-sm ${tab === 'run' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('run')}
          >
            <SlidersHorizontal size={18} />
            Run
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'models' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('models')}
          >
            <Brain size={18} />
            Models
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'generate' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('generate')}
          >
            <Sparkles size={18} />
            Generate
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'config' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('config')}
          >
            <FileText size={18} />
            Config
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'advanced' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTab('advanced')}
          >
            Advanced
          </button>
        </div>
      </div>

      {tab === 'run' ? (
        <div className="neo-card p-4">
          <div className="font-display font-bold uppercase mb-3">Applies next start</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              className={`neo-card p-4 text-left transition-all ${runSettings.mode === 'standard' ? 'ring-4 ring-[var(--color-neo-accent)]' : ''}`}
              onClick={() => onChangeRunSettings({ ...runSettings, mode: 'standard' })}
            >
              <div className="font-display font-bold uppercase">Standard</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">Single agent run.</div>
            </button>
            <button
              className={`neo-card p-4 text-left transition-all ${runSettings.mode === 'parallel' ? 'ring-4 ring-[var(--color-neo-accent)]' : ''} ${
                canUseParallel ? '' : 'opacity-50 cursor-not-allowed'
              }`}
              disabled={!canUseParallel}
              onClick={() => onChangeRunSettings({ ...runSettings, mode: 'parallel' })}
              title={!canUseParallel ? 'Disable YOLO to enable parallel mode' : 'Parallel mode'}
            >
              <div className="font-display font-bold uppercase">Parallel</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">Worktree + multiple agents.</div>
            </button>
          </div>

          {runSettings.mode === 'parallel' && (
            <div className="neo-card p-4 mt-4">
              <div className="font-display font-bold uppercase text-sm mb-3">Parallel</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Agents</div>
                  <select
                    value={runSettings.parallelCount}
                    onChange={(e) => onChangeRunSettings({ ...runSettings, parallelCount: Number(e.target.value) })}
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
                    <span className="font-mono text-sm font-bold">{runSettings.parallelPreset}</span>
                    <button className="neo-btn neo-btn-secondary text-sm py-2 px-3" onClick={() => setTab('models')}>
                      Change
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : tab === 'models' ? (
        <ModelSettingsContent
          onPresetApplied={(presetId) =>
            onChangeRunSettings({
              ...runSettings,
              parallelPreset: presetId as any,
            })
          }
        />
      ) : tab === 'generate' ? (
        <MultiModelGeneratePanel projectName={projectName} />
      ) : tab === 'config' ? (
        <ProjectConfigEditor projectName={projectName} />
      ) : (
        <AdvancedSettingsContent />
      )}
    </div>
  )
}
