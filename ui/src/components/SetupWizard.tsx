import { useEffect, useCallback } from 'react'
import { CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { useSetupStatus, useHealthCheck } from '../hooks/useProjects'

interface SetupWizardProps {
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const { data: setupStatus, isLoading: setupLoading, error: setupError } = useSetupStatus()
  const { data: health, error: healthError } = useHealthCheck()

  const isApiHealthy = health?.status === 'healthy' && !healthError
  const isReady = isApiHealthy && setupStatus?.claude_cli && setupStatus?.credentials

  // Memoize the completion check to avoid infinite loops
  const checkAndComplete = useCallback(() => {
    if (isReady) {
      onComplete()
    }
  }, [isReady, onComplete])

  // Auto-complete if everything is ready
  useEffect(() => {
    checkAndComplete()
  }, [checkAndComplete])

  return (
    <div className="min-h-screen bg-[var(--color-neo-bg)] flex items-center justify-center p-4">
      <div className="neo-card w-full max-w-lg p-8">
        <h1 className="font-display text-3xl font-bold text-center mb-2">
          Setup Wizard
        </h1>
        <p className="text-center text-[var(--color-neo-text-secondary)] mb-8">
          Let's make sure everything is ready to go
        </p>

        <div className="space-y-4">
          {/* API Health */}
          <SetupItem
            label="Backend Server"
            description="FastAPI server is running"
            status={healthError ? 'error' : isApiHealthy ? 'success' : 'loading'}
          />

          {/* Claude CLI */}
          <SetupItem
            label="Claude CLI"
            description="Claude Code CLI is installed"
            status={
              setupLoading
                ? 'loading'
                : setupError
                ? 'error'
                : setupStatus?.claude_cli
                ? 'success'
                : 'error'
            }
            helpLink="https://docs.anthropic.com/claude/claude-code"
            helpText="Install Claude Code"
          />

          {/* Credentials */}
          <SetupItem
            label="Anthropic Credentials"
            description="API credentials are configured"
            status={
              setupLoading
                ? 'loading'
                : setupError
                ? 'error'
                : setupStatus?.credentials
                ? 'success'
                : 'error'
            }
            helpLink="https://console.anthropic.com/account/keys"
            helpText="Get API Key"
          />

          {/* Node.js */}
          <SetupItem
            label="Node.js"
            description="Node.js is installed (for UI dev)"
            status={
              setupLoading
                ? 'loading'
                : setupError
                ? 'error'
                : setupStatus?.node
                ? 'success'
                : 'warning'
            }
            helpLink="https://nodejs.org"
            helpText="Install Node.js"
            optional
          />
        </div>

        {/* Continue Button */}
        {isReady && (
          <button
            onClick={onComplete}
            className="neo-btn neo-btn-success w-full mt-8"
          >
            Continue to Dashboard
          </button>
        )}

        {/* Error Message */}
        {(healthError || setupError) && (
          <div className="mt-6 p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)]">
            <p className="font-bold mb-2">Setup Error</p>
            <p className="text-sm">
              {healthError
                ? 'Cannot connect to the backend server. Make sure to run start_ui.py first.'
                : 'Failed to check setup status.'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

interface SetupItemProps {
  label: string
  description: string
  status: 'success' | 'error' | 'warning' | 'loading'
  helpLink?: string
  helpText?: string
  optional?: boolean
}

function SetupItem({
  label,
  description,
  status,
  helpLink,
  helpText,
  optional,
}: SetupItemProps) {
  return (
    <div className="flex items-start gap-4 p-4 bg-[var(--color-neo-bg)] border-3 border-[var(--color-neo-border)]">
      {/* Status Icon */}
      <div className="flex-shrink-0 mt-1">
        {status === 'success' ? (
          <CheckCircle2 size={24} className="text-[var(--color-neo-done)]" />
        ) : status === 'error' ? (
          <XCircle size={24} className="text-[var(--color-neo-danger)]" />
        ) : status === 'warning' ? (
          <XCircle size={24} className="text-[var(--color-neo-pending)]" />
        ) : (
          <Loader2 size={24} className="animate-spin text-[var(--color-neo-progress)]" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-display font-bold">{label}</span>
          {optional && (
            <span className="text-xs text-[var(--color-neo-text-secondary)]">
              (optional)
            </span>
          )}
        </div>
        <p className="text-sm text-[var(--color-neo-text-secondary)]">
          {description}
        </p>
        {(status === 'error' || status === 'warning') && helpLink && (
          <a
            href={helpLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-2 text-sm text-[var(--color-neo-accent)] hover:underline"
          >
            {helpText} <ExternalLink size={12} />
          </a>
        )}
      </div>
    </div>
  )
}
