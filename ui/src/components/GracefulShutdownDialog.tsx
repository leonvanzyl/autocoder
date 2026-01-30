import { useEffect } from 'react'
import { Square, Clock, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useStopAgent, useGracefulStopAgent } from '../hooks/useProjects'

interface GracefulShutdownDialogProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
  activeAgentCount: number
}

export function GracefulShutdownDialog({
  projectName,
  isOpen,
  onClose,
  activeAgentCount,
}: GracefulShutdownDialogProps) {
  const stopAgent = useStopAgent(projectName)
  const gracefulStopAgent = useGracefulStopAgent(projectName)

  const isLoading = stopAgent.isPending || gracefulStopAgent.isPending

  // Auto-close when all agents complete (during graceful shutdown)
  useEffect(() => {
    if (isOpen && activeAgentCount === 0 && gracefulStopAgent.isSuccess) {
      onClose()
    }
  }, [isOpen, activeAgentCount, gracefulStopAgent.isSuccess, onClose])

  const handleImmediateStop = async () => {
    await stopAgent.mutateAsync()
    onClose()
  }

  const handleGracefulStop = async () => {
    await gracefulStopAgent.mutateAsync()
    // Don't close immediately - let it stay open so user can see progress
    // The dialog will auto-close when agents complete
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Square className="h-5 w-5 text-destructive" />
            Stop Agent
          </DialogTitle>
          <DialogDescription className="pt-2">
            {activeAgentCount > 0 ? (
              <>
                There {activeAgentCount === 1 ? 'is' : 'are'} currently{' '}
                <span className="font-semibold text-foreground">
                  {activeAgentCount} agent{activeAgentCount > 1 ? 's' : ''}
                </span>{' '}
                working on features. How would you like to stop?
              </>
            ) : (
              'No agents are currently working. The orchestrator will stop immediately.'
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3 py-4">
          {activeAgentCount > 0 && (
            <Button
              variant="outline"
              className="justify-start h-auto py-3 px-4"
              onClick={handleGracefulStop}
              disabled={isLoading}
            >
              <div className="flex items-start gap-3">
                {isLoading && gracefulStopAgent.isPending ? (
                  <Loader2 className="h-5 w-5 mt-0.5 animate-spin text-muted-foreground" />
                ) : (
                  <Clock className="h-5 w-5 mt-0.5 text-muted-foreground" />
                )}
                <div className="text-left">
                  <div className="font-medium">Wait for completion</div>
                  <div className="text-sm text-muted-foreground">
                    Let running agents finish their current features, then stop.
                    No new features will be started.
                  </div>
                </div>
              </div>
            </Button>
          )}

          <Button
            variant={activeAgentCount > 0 ? 'destructive' : 'default'}
            className="justify-start h-auto py-3 px-4"
            onClick={handleImmediateStop}
            disabled={isLoading}
          >
            <div className="flex items-start gap-3">
              {isLoading && stopAgent.isPending ? (
                <Loader2 className="h-5 w-5 mt-0.5 animate-spin" />
              ) : (
                <Square className="h-5 w-5 mt-0.5" />
              )}
              <div className="text-left">
                <div className="font-medium">Stop immediately</div>
                <div className={`text-sm ${activeAgentCount > 0 ? 'text-destructive-foreground/80' : 'text-muted-foreground'}`}>
                  {activeAgentCount > 0
                    ? 'Terminate all agents now. Work in progress may be lost.'
                    : 'Stop the orchestrator.'}
                </div>
              </div>
            </div>
          </Button>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
