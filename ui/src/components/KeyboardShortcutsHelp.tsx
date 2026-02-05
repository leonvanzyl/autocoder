import { useEffect, useCallback } from 'react'
import { Keyboard } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'

interface Shortcut {
  key: string
  description: string
  context?: string
}

const shortcuts: Shortcut[] = [
  { key: '?', description: 'Show keyboard shortcuts' },
  { key: 'D', description: 'Toggle debug panel' },
  { key: 'T', description: 'Toggle terminal tab' },
  { key: 'N', description: 'Add new feature', context: 'with project' },
  { key: 'E', description: 'Expand project with AI', context: 'with spec & features' },
  { key: 'A', description: 'Toggle AI assistant', context: 'with project' },
  { key: 'G', description: 'Toggle Kanban/Graph view', context: 'with project' },
  { key: ',', description: 'Open settings' },
  { key: 'Esc', description: 'Close modal/panel' },
]

interface KeyboardShortcutsHelpProps {
  isOpen: boolean
  onClose: () => void
}

export function KeyboardShortcutsHelp({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault()
        onClose()
      }
    },
    [onClose]
  )

  useEffect(() => {
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
      return () => window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, handleKeyDown])

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard size={20} className="text-primary" />
            Keyboard Shortcuts
          </DialogTitle>
        </DialogHeader>

        {/* Shortcuts list */}
        <ul className="space-y-1">
          {shortcuts.map((shortcut) => (
            <li
              key={shortcut.key}
              className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
            >
              <div className="flex items-center gap-3">
                <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded border border-border min-w-[2rem] text-center">
                  {shortcut.key}
                </kbd>
                <span className="text-sm">{shortcut.description}</span>
              </div>
              {shortcut.context && (
                <Badge variant="secondary" className="text-xs">
                  {shortcut.context}
                </Badge>
              )}
            </li>
          ))}
        </ul>

        {/* Footer */}
        <p className="text-xs text-muted-foreground text-center pt-2">
          Press ? or Esc to close
        </p>
      </DialogContent>
    </Dialog>
  )
}
