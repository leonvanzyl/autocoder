/**
 * Settings Page
 * =============
 *
 * Wider, less cramped settings hub. Mirrors the quick Settings modal but with an Advanced tab.
 */

import { useMemo, useState } from 'react'
import { Settings as SettingsIcon, SlidersHorizontal, Brain, Sparkles, FileText, Activity, Wrench } from 'lucide-react'
import { ModelSettingsContent } from '../components/ModelSettingsContent'
import { EngineSettingsContent } from '../components/EngineSettingsContent'
import { AdvancedSettingsContent } from '../components/AdvancedSettingsContent'
import { MultiModelGeneratePanel } from '../components/MultiModelGeneratePanel'
import { GsdToSpecPanel } from '../components/GsdToSpecPanel'
import { ProjectConfigEditor } from '../components/ProjectConfigEditor'
import { ProjectMaintenance } from '../components/ProjectMaintenance'
import { DiagnosticsContent } from '../components/DiagnosticsContent'
import type { RunSettings } from '../components/SettingsModal'
import type { ProjectSummary } from '../lib/types'

type SettingsPageTab = 'run' | 'models' | 'engines' | 'generate' | 'config' | 'advanced' | 'diagnostics'

export function SettingsPage({
  initialTab = 'run',
  projectName,
  projects,
  onSelectProject,
  yoloEnabled,
  runSettings,
  onChangeRunSettings,
  onClose,
}: {
  initialTab?: SettingsPageTab
  projectName: string | null
  projects: ProjectSummary[]
  onSelectProject: (name: string | null) => void
  yoloEnabled: boolean
  runSettings: RunSettings
  onChangeRunSettings: (next: RunSettings) => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<SettingsPageTab>(initialTab)
  const activeScope: 'global' | 'project' = useMemo(() => {
    if (tab === 'advanced' || tab === 'diagnostics') return 'global'
    if (tab === 'models' || tab === 'engines' || tab === 'generate' || tab === 'config') return 'project'
    return projectName ? 'project' : 'global'
  }, [projectName, tab])

  const canUseParallel = !yoloEnabled
  const projectTabsEnabled = Boolean(projectName)

  const projectOptions = useMemo(() => {
    return [...projects].sort((a, b) => a.name.localeCompare(b.name))
  }, [projects])

  const setTabWithHash = (next: SettingsPageTab) => {
    setTab(next)
    const route =
      next === 'advanced'
        ? '#/settings/advanced'
          : next === 'models'
            ? '#/settings/models'
            : next === 'engines'
              ? '#/settings/engines'
              : next === 'generate'
                ? '#/settings/generate'
                : next === 'config'
                  ? '#/settings/config'
                  : next === 'diagnostics'
                    ? '#/settings/diagnostics'
                    : '#/settings'
    window.location.hash = route
  }

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
          <button
            className="neo-btn neo-btn-secondary text-sm"
            onClick={onClose}
            title={projectName ? 'Back to project' : 'Back to dashboard'}
          >
            Back
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="neo-card neo-card-flat p-3">
            <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Scope</div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={`neo-btn neo-btn-sm ${activeScope === 'project' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
                onClick={() => setTabWithHash('models')}
              >
                Project
              </button>
              <button
                type="button"
                className={`neo-btn neo-btn-sm ${activeScope === 'global' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
                onClick={() => setTabWithHash('advanced')}
              >
                Global
              </button>
            </div>
            <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
              Global = this machine/UI. Project = per-project config.
            </div>
          </div>

          <div className="neo-card neo-card-flat p-3 lg:col-span-2">
            <div className="flex flex-col sm:flex-row sm:items-end gap-3">
              <div className="flex-1 min-w-[220px]">
                <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Project (optional)</div>
                <select
                  className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                  value={projectName ?? ''}
                  onChange={(e) => onSelectProject(e.target.value ? e.target.value : null)}
                  title="Select project to enable project-scoped tabs"
                >
                  <option value="">— Select a project —</option>
                  {projectOptions.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {!projectTabsEnabled && (
                <div className="text-sm text-[var(--color-neo-text-secondary)]">
                  Pick a project to unlock <span className="font-display font-semibold">Models / Generate / Config</span>.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className={`neo-btn text-sm ${tab === 'run' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTabWithHash('run')}
          >
            <SlidersHorizontal size={18} />
            Run
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'models' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'} ${
              projectTabsEnabled ? '' : 'opacity-70'
            }`}
            onClick={() => setTabWithHash('models')}
            title={!projectTabsEnabled ? 'Select a project to edit models' : undefined}
          >
            <Brain size={18} />
            Models
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'engines' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'} ${
              projectTabsEnabled ? '' : 'opacity-70'
            }`}
            onClick={() => setTabWithHash('engines')}
            title={!projectTabsEnabled ? 'Select a project to edit engines' : undefined}
          >
            <Wrench size={18} />
            Engines
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'generate' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'} ${
              projectTabsEnabled ? '' : 'opacity-70'
            }`}
            onClick={() => setTabWithHash('generate')}
            title={!projectTabsEnabled ? 'Select a project to generate specs' : undefined}
          >
            <Sparkles size={18} />
            Generate
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'config' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'} ${
              projectTabsEnabled ? '' : 'opacity-70'
            }`}
            onClick={() => setTabWithHash('config')}
            title={!projectTabsEnabled ? 'Select a project to edit autocoder.yaml' : undefined}
          >
            <FileText size={18} />
            Config
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'advanced' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTabWithHash('advanced')}
          >
            Advanced
          </button>
          <button
            className={`neo-btn text-sm ${tab === 'diagnostics' ? 'bg-[var(--color-neo-accent)] text-white' : 'neo-btn-secondary'}`}
            onClick={() => setTabWithHash('diagnostics')}
          >
            <Activity size={18} />
            Diagnostics
          </button>
        </div>
      </div>

      {tab === 'run' ? (
        <div className="neo-card p-4">
          <div className="font-display font-bold uppercase mb-3">Applies next start</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              className={`neo-card p-4 text-left transition-colors duration-200 cursor-pointer ${runSettings.mode === 'standard' ? 'ring-4 ring-[var(--color-neo-accent)]' : ''}`}
              onClick={() => onChangeRunSettings({ ...runSettings, mode: 'standard' })}
            >
              <div className="font-display font-bold uppercase">Standard</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">Single agent run.</div>
            </button>
            <button
              className={`neo-card p-4 text-left transition-colors duration-200 ${runSettings.mode === 'parallel' ? 'ring-4 ring-[var(--color-neo-accent)]' : ''} ${
                canUseParallel ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'
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
        projectName ? (
          <ModelSettingsContent
            projectName={projectName}
            onPresetApplied={(presetId) =>
              onChangeRunSettings({
                ...runSettings,
                parallelPreset: presetId as any,
              })
            }
          />
        ) : (
          <div className="neo-card p-6">
            <div className="font-display font-bold uppercase mb-2">Select a project</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Models are project-scoped. Pick a project from the selector above to continue.
            </div>
          </div>
        )
      ) : tab === 'engines' ? (
        projectName ? (
          <EngineSettingsContent projectName={projectName} />
        ) : (
          <div className="neo-card p-6">
            <div className="font-display font-bold uppercase mb-2">Select a project</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Engines are project-scoped. Pick a project from the selector above to continue.
            </div>
          </div>
        )
      ) : tab === 'generate' ? (
        projectName ? (
          <div className="space-y-6">
            <GsdToSpecPanel projectName={projectName} />
            <MultiModelGeneratePanel projectName={projectName} />
          </div>
        ) : (
          <div className="neo-card p-6">
            <div className="font-display font-bold uppercase mb-2">Select a project</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Spec generation is project-scoped. Pick a project from the selector above to continue.
            </div>
          </div>
        )
      ) : tab === 'config' ? (
        projectName ? (
          <div className="space-y-6">
            <ProjectConfigEditor projectName={projectName} />
            <ProjectMaintenance projectName={projectName} />
          </div>
        ) : (
          <div className="neo-card p-6">
            <div className="font-display font-bold uppercase mb-2">Select a project</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Project config is per-project. Pick a project from the selector above to continue.
            </div>
          </div>
        )
      ) : tab === 'diagnostics' ? (
        <DiagnosticsContent />
      ) : (
        <AdvancedSettingsContent />
      )}
    </div>
  )
}
