import { Loader2, AlertCircle, Check, Moon, Sun } from 'lucide-react'
import { useSettings, useUpdateSettings, useAvailableModels } from '../hooks/useProjects'
import { useTheme, THEMES } from '../hooks/useTheme'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { data: settings, isLoading, isError, refetch } = useSettings()
  const { data: modelsData } = useAvailableModels()
  const updateSettings = useUpdateSettings()
  const { theme, setTheme, darkMode, toggleDarkMode } = useTheme()

  const handleYoloToggle = () => {
    if (settings && !updateSettings.isPending) {
      updateSettings.mutate({ yolo_mode: !settings.yolo_mode })
    }
  }

  const handleCoderModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ coder_model: modelId })
    }
  }

  const handleTesterModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ tester_model: modelId })
    }
  }

  const handleInitializerModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ initializer_model: modelId })
    }
  }

  const handleTestingRatioChange = (ratio: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ testing_agent_ratio: ratio })
    }
  }

  const models = modelsData?.models ?? []
  const isSaving = updateSettings.isPending

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm max-h-[85vh] flex flex-col">
        <DialogHeader className="shrink-0 pb-4 border-b border-border">
          <DialogTitle className="flex items-center gap-2">
            Settings
            {isSaving && <Loader2 className="animate-spin" size={16} />}
          </DialogTitle>
        </DialogHeader>

        {/* Scrollable content area */}
        <div className="flex-1 overflow-y-auto pr-2 -mr-2">
          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin" size={24} />
              <span className="ml-2">Loading settings...</span>
            </div>
          )}

          {/* Error State */}
          {isError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Failed to load settings
                <Button
                  variant="link"
                  onClick={() => refetch()}
                  className="ml-2 p-0 h-auto"
                >
                  Retry
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Settings Content */}
          {settings && !isLoading && (
            <div className="space-y-6 pt-4">
              {/* Theme Selection */}
              <div className="space-y-3">
                <Label className="font-medium">Theme</Label>
                <div className="grid gap-2">
                  {THEMES.map((themeOption) => (
                    <button
                      key={themeOption.id}
                      onClick={() => setTheme(themeOption.id)}
                      className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-colors text-left ${
                        theme === themeOption.id
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-primary/50 hover:bg-muted/50'
                      }`}
                    >
                      {/* Color swatches */}
                      <div className="flex gap-0.5 shrink-0">
                        <div
                          className="w-5 h-5 rounded-sm border border-border/50"
                          style={{ backgroundColor: themeOption.previewColors.background }}
                        />
                        <div
                          className="w-5 h-5 rounded-sm border border-border/50"
                          style={{ backgroundColor: themeOption.previewColors.primary }}
                        />
                        <div
                          className="w-5 h-5 rounded-sm border border-border/50"
                          style={{ backgroundColor: themeOption.previewColors.accent }}
                        />
                      </div>

                      {/* Theme info */}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm">{themeOption.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {themeOption.description}
                        </div>
                      </div>

                      {/* Checkmark */}
                      {theme === themeOption.id && (
                        <Check size={18} className="text-primary shrink-0" />
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Dark Mode Toggle */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="dark-mode" className="font-medium">
                    Dark Mode
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Switch between light and dark appearance
                  </p>
                </div>
                <Button
                  id="dark-mode"
                  variant="outline"
                  size="sm"
                  onClick={toggleDarkMode}
                  className="gap-2"
                >
                  {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                  {darkMode ? 'Light' : 'Dark'}
                </Button>
              </div>

              <hr className="border-border" />

              {/* YOLO Mode Toggle */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="yolo-mode" className="font-medium">
                    YOLO Mode
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Skip testing for rapid prototyping
                  </p>
                </div>
                <Switch
                  id="yolo-mode"
                  checked={settings.yolo_mode}
                  onCheckedChange={handleYoloToggle}
                  disabled={isSaving}
                />
              </div>

              {/* Per-Agent Model Selection */}
              <div className="space-y-4">
                <Label className="font-medium">Models by Agent Type</Label>

                {/* Coder Model */}
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Coding Agents</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => handleCoderModelChange(model.id)}
                        disabled={isSaving}
                        className={`py-1.5 px-2 text-xs font-medium transition-colors rounded-md border ${
                          settings.coder_model === model.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-background text-foreground border-border hover:bg-muted hover:border-primary/50'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Tester Model */}
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Testing Agents</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => handleTesterModelChange(model.id)}
                        disabled={isSaving}
                        className={`py-1.5 px-2 text-xs font-medium transition-colors rounded-md border ${
                          settings.tester_model === model.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-background text-foreground border-border hover:bg-muted hover:border-primary/50'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Initializer Model */}
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Initializer Agent</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => handleInitializerModelChange(model.id)}
                        disabled={isSaving}
                        className={`py-1.5 px-2 text-xs font-medium transition-colors rounded-md border ${
                          settings.initializer_model === model.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-background text-foreground border-border hover:bg-muted hover:border-primary/50'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Regression Agents */}
              <div className="space-y-2">
                <Label className="font-medium">Regression Agents</Label>
                <p className="text-sm text-muted-foreground">
                  Number of regression testing agents (0 = disabled)
                </p>
                <div className="flex rounded-lg border overflow-hidden">
                  {[0, 1, 2, 3].map((ratio) => (
                    <button
                      key={ratio}
                      onClick={() => handleTestingRatioChange(ratio)}
                      disabled={isSaving}
                      className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                        settings.testing_agent_ratio === ratio
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-background text-foreground hover:bg-muted'
                      } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      {ratio}
                    </button>
                  ))}
                </div>
              </div>

              {/* Update Error */}
              {updateSettings.isError && (
                <Alert variant="destructive">
                  <AlertDescription>
                    Failed to save settings. Please try again.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
