import { useEffect, useCallback } from 'react'
import { CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { useSetupStatus, useHealthCheck } from '../hooks/useProjects'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

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
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardContent className="p-8">
          <h1 className="font-display text-3xl font-bold text-center mb-2">
            Setup Wizard
          </h1>
          <p className="text-center text-muted-foreground mb-8">
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

            {/* Gemini (chat-only) */}
            <SetupItem
              label="Gemini (assistant chat only)"
              description="Optional: set GEMINI_API_KEY to use Gemini for the read-only assistant. Coding agents still use Claude/Anthropic."
              status={
                setupLoading
                  ? 'loading'
                  : setupError
                  ? 'warning'
                  : setupStatus?.gemini
                  ? 'success'
                  : 'warning'
              }
              helpLink="https://ai.google.dev/gemini-api/docs/openai-compatibility"
              helpText="Configure Gemini"
              optional
            />
          </div>

          {/* Continue Button */}
          {isReady && (
            <Button
              onClick={onComplete}
              className="w-full mt-8 bg-green-500 hover:bg-green-600 text-white"
            >
              Continue to Dashboard
            </Button>
          )}

          {/* Error Message */}
          {(healthError || setupError) && (
            <Alert variant="destructive" className="mt-6">
              <AlertTitle>Setup Error</AlertTitle>
              <AlertDescription>
                {healthError
                  ? 'Cannot connect to the backend server. Make sure to run start_ui.py first.'
                  : 'Failed to check setup status.'}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
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
    <div className="flex items-start gap-4 p-4 bg-background border-2 border-border rounded-lg">
      {/* Status Icon */}
      <div className="flex-shrink-0 mt-1">
        {status === 'success' ? (
          <CheckCircle2 size={24} className="text-green-500" />
        ) : status === 'error' ? (
          <XCircle size={24} className="text-destructive" />
        ) : status === 'warning' ? (
          <XCircle size={24} className="text-yellow-500" />
        ) : (
          <Loader2 size={24} className="animate-spin text-primary" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-display font-bold text-foreground">{label}</span>
          {optional && (
            <span className="text-xs text-muted-foreground">
              (optional)
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {description}
        </p>
        {(status === 'error' || status === 'warning') && helpLink && (
          <a
            href={helpLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-2 text-sm text-primary hover:underline"
          >
            {helpText} <ExternalLink size={12} />
          </a>
        )}
      </div>
    </div>
  )
}
