import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { IDEType } from '../lib/types'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'

interface IDESelectionModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (ide: IDEType, remember: boolean) => void
  isLoading?: boolean
}

const IDE_OPTIONS: { id: IDEType; name: string; description: string }[] = [
  { id: 'vscode', name: 'VS Code', description: 'Microsoft Visual Studio Code' },
  { id: 'cursor', name: 'Cursor', description: 'AI-powered code editor' },
  { id: 'antigravity', name: 'Antigravity', description: 'Claude-native development environment' },
]

export function IDESelectionModal({ isOpen, onClose, onSelect, isLoading }: IDESelectionModalProps) {
  const [selectedIDE, setSelectedIDE] = useState<IDEType | null>(null)
  const [rememberChoice, setRememberChoice] = useState(true)

  const handleConfirm = () => {
    if (selectedIDE && !isLoading) {
      onSelect(selectedIDE, rememberChoice)
    }
  }

  const handleClose = () => {
    setSelectedIDE(null)
    setRememberChoice(true)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Choose Your IDE</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <p className="text-sm text-muted-foreground">
            Select your preferred IDE to open projects. This will be saved for future use.
          </p>
          
          <div className="space-y-2">
            <Label className="font-medium">IDE Selection</Label>
            <div className="space-y-2" role="radiogroup" aria-label="IDE selection">
              {IDE_OPTIONS.map((ide) => (
                <button
                  type="button"
                  role="radio"
                  aria-checked={selectedIDE === ide.id}
                  key={ide.id}
                  onClick={() => setSelectedIDE(ide.id)}
                  disabled={isLoading}
                  className={`w-full flex items-center justify-between p-3 rounded-lg border-2 transition-colors text-left ${
                    selectedIDE === ide.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50 hover:bg-muted/50'
                  } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div>
                    <div className="font-medium">{ide.name}</div>
                    <div className="text-sm text-muted-foreground">{ide.description}</div>
                  </div>
                  {selectedIDE === ide.id && (
                    <div className="w-4 h-4 rounded-full bg-primary" />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="remember-ide"
              checked={rememberChoice}
              onCheckedChange={(checked) => setRememberChoice(checked === true)}
              disabled={isLoading}
            />
            <label
              htmlFor="remember-ide"
              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
            >
              Remember my choice
            </label>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!selectedIDE || isLoading}>
            {isLoading && <Loader2 className="mr-2 animate-spin" size={16} />}
            Open in {selectedIDE ? IDE_OPTIONS.find(o => o.id === selectedIDE)?.name : 'IDE'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
