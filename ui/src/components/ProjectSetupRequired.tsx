/**
 * Project Setup Required Component
 *
 * Shown when a project exists but doesn't have a spec file (e.g., after full reset).
 * Offers the same options as new project creation: Claude or manual spec.
 */

import { useState } from 'react'
import { Bot, FileEdit, Loader2, AlertTriangle } from 'lucide-react'
import { SpecCreationChat } from './SpecCreationChat'
import { startAgent } from '../lib/api'

type InitializerStatus = 'idle' | 'starting' | 'error'

interface ProjectSetupRequiredProps {
  projectName: string
  onSetupComplete: () => void
}

export function ProjectSetupRequired({ projectName, onSetupComplete }: ProjectSetupRequiredProps) {
  const [showChat, setShowChat] = useState(false)
  const [initializerStatus, setInitializerStatus] = useState<InitializerStatus>('idle')
  const [initializerError, setInitializerError] = useState<string | null>(null)
  const [yoloModeSelected, setYoloModeSelected] = useState(false)

  const handleClaudeSelect = () => {
    setShowChat(true)
  }

  const handleManualSelect = () => {
    // For manual, just refresh to show the empty project
    // User can edit prompts/app_spec.txt directly
    onSetupComplete()
  }

  const handleSpecComplete = async (_specPath: string, yoloMode: boolean = false) => {
    setYoloModeSelected(yoloMode)
    setInitializerStatus('starting')
    try {
      await startAgent(projectName, { yoloMode })
      onSetupComplete()
    } catch (err) {
      setInitializerStatus('error')
      setInitializerError(err instanceof Error ? err.message : 'Failed to start agent')
    }
  }

  const handleRetryInitializer = () => {
    setInitializerError(null)
    setInitializerStatus('idle')
    handleSpecComplete('', yoloModeSelected)
  }

  const handleChatCancel = () => {
    setShowChat(false)
  }

  const handleExitToProject = () => {
    onSetupComplete()
  }

  // Full-screen chat view
  if (showChat) {
    return (
      <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
        <SpecCreationChat
          projectName={projectName}
          onComplete={handleSpecComplete}
          onCancel={handleChatCancel}
          onExitToProject={handleExitToProject}
          initializerStatus={initializerStatus}
          initializerError={initializerError}
          onRetryInitializer={handleRetryInitializer}
        />
      </div>
    )
  }

  return (
    <div className="neo-card p-8 max-w-2xl mx-auto mt-12">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-[var(--color-neo-warning)] border-3 border-[var(--color-neo-border)]">
          <AlertTriangle size={24} />
        </div>
        <div>
          <h2 className="font-display font-bold text-2xl">Setup Required</h2>
          <p className="text-[var(--color-neo-text-secondary)]">
            Project <strong>{projectName}</strong> needs an app specification to get started.
          </p>
        </div>
      </div>

      {/* Options */}
      <div className="space-y-4">
        {/* Claude option */}
        <button
          onClick={handleClaudeSelect}
          className={`
            w-full text-left p-4
            border-3 border-[var(--color-neo-border)]
            bg-white
            shadow-[4px_4px_0px_rgba(0,0,0,1)]
            hover:translate-x-[-2px] hover:translate-y-[-2px]
            hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
            transition-all duration-150
          `}
        >
          <div className="flex items-start gap-4">
            <div className="p-2 bg-[var(--color-neo-progress)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              <Bot size={24} className="text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-[#1a1a1a]">Create with Claude</span>
                <span className="neo-badge bg-[var(--color-neo-done)] text-xs">
                  Recommended
                </span>
              </div>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                Interactive conversation to define features and generate your app specification automatically.
              </p>
            </div>
          </div>
        </button>

        {/* Manual option */}
        <button
          onClick={handleManualSelect}
          className={`
            w-full text-left p-4
            border-3 border-[var(--color-neo-border)]
            bg-white
            shadow-[4px_4px_0px_rgba(0,0,0,1)]
            hover:translate-x-[-2px] hover:translate-y-[-2px]
            hover:shadow-[6px_6px_0px_rgba(0,0,0,1)]
            transition-all duration-150
          `}
        >
          <div className="flex items-start gap-4">
            <div className="p-2 bg-[var(--color-neo-pending)] border-2 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              <FileEdit size={24} />
            </div>
            <div className="flex-1">
              <span className="font-bold text-lg text-[#1a1a1a]">Edit Templates Manually</span>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                Edit the template files directly in <code className="bg-gray-100 px-1">prompts/app_spec.txt</code>. Best for developers who want full control.
              </p>
            </div>
          </div>
        </button>
      </div>

      {initializerStatus === 'starting' && (
        <div className="mt-6 flex items-center justify-center gap-2 text-[var(--color-neo-text-secondary)]">
          <Loader2 size={16} className="animate-spin" />
          <span>Starting agent...</span>
        </div>
      )}

      {initializerError && (
        <div className="mt-6 p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
          <p className="font-bold mb-2">Failed to start agent</p>
          <p className="text-sm">{initializerError}</p>
          <button
            onClick={handleRetryInitializer}
            className="mt-3 neo-btn bg-white text-[var(--color-neo-danger)]"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}
