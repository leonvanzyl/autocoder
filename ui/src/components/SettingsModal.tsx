import { useState } from 'react'
import { Loader2, AlertCircle, Check, Moon, Sun, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useSettings, useUpdateSettings, useAvailableModels, useAvailableProviders } from '../hooks/useProjects'
import { useTheme, THEMES } from '../hooks/useTheme'
import type { ProviderInfo } from '../lib/types'
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

const PROVIDER_INFO_TEXT: Record<string, string> = {
  claude: 'Default provider. Uses your Claude CLI credentials.',
  kimi: 'Get an API key at kimi.com',
  glm: 'Get an API key at open.bigmodel.cn',
  ollama: 'Run models locally. Install from ollama.com',
  openrouter: 'Access 200+ models. Get an API key at openrouter.ai',
  custom: 'Connect to any OpenAI-compatible API endpoint.',
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { data: settings, isLoading, isError, refetch } = useSettings()
  const { data: modelsData } = useAvailableModels()
  const { data: providersData } = useAvailableProviders()
  const updateSettings = useUpdateSettings()
  const { theme, setTheme, darkMode, toggleDarkMode } = useTheme()

  const [showAuthToken, setShowAuthToken] = useState(false)
  const [authTokenInput, setAuthTokenInput] = useState('')
  const [customModelInput, setCustomModelInput] = useState('')
  const [customBaseUrlInput, setCustomBaseUrlInput] = useState('')

  const handleYoloToggle = () => {
    if (settings && !updateSettings.isPending) {
      updateSettings.mutate({ yolo_mode: !settings.yolo_mode })
    }
  }

  const handleModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ api_model: modelId })
    }
  }

  const handleTestingRatioChange = (ratio: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ testing_agent_ratio: ratio })
    }
  }

  const handleBatchSizeChange = (size: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ batch_size: size })
    }
  }

  const handleProviderChange = (providerId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ api_provider: providerId })
      // Reset local state
      setAuthTokenInput('')
      setShowAuthToken(false)
      setCustomModelInput('')
      setCustomBaseUrlInput('')
    }
  }

  const handleSaveAuthToken = () => {
    if (authTokenInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_auth_token: authTokenInput.trim() })
      setAuthTokenInput('')
      setShowAuthToken(false)
    }
  }

  const handleSaveCustomBaseUrl = () => {
    if (customBaseUrlInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_base_url: customBaseUrlInput.trim() })
    }
  }

  const handleSaveCustomModel = () => {
    if (customModelInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_model: customModelInput.trim() })
      setCustomModelInput('')
    }
  }

  const providers = providersData?.providers ?? []
  const models = modelsData?.models ?? []
  const isSaving = updateSettings.isPending
  const currentProvider = settings?.api_provider ?? 'claude'
  const currentProviderInfo: ProviderInfo | undefined = providers.find(p => p.id === currentProvider)
  const isAlternativeProvider = currentProvider !== 'claude'
  const showAuthField = isAlternativeProvider && currentProviderInfo?.requires_auth
  const showBaseUrlField = currentProvider === 'custom'
  const showCustomModelInput = currentProvider === 'custom' || currentProvider === 'ollama'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent aria-describedby={undefined} className="sm:max-w-sm max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Settings
            {isSaving && <Loader2 className="animate-spin" size={16} />}
          </DialogTitle>
        </DialogHeader>

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
          <div className="space-y-6">
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

            {/* API Provider Selection */}
            <div className="space-y-3">
              <Label className="font-medium">API Provider</Label>
              <div className="flex flex-wrap gap-1.5">
                {providers.map((provider) => (
                  <button
                    key={provider.id}
                    onClick={() => handleProviderChange(provider.id)}
                    disabled={isSaving}
                    className={`py-1.5 px-3 text-sm font-medium rounded-md border transition-colors ${
                      currentProvider === provider.id
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-background text-foreground border-border hover:bg-muted'
                    } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {provider.name.split(' (')[0]}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                {PROVIDER_INFO_TEXT[currentProvider] ?? ''}
              </p>

              {/* Auth Token Field */}
              {showAuthField && (
                <div className="space-y-2 pt-1">
                  <Label className="text-sm">API Key</Label>
                  {settings.api_has_auth_token && !authTokenInput && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <ShieldCheck size={14} className="text-green-500" />
                      <span>Configured</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-auto py-0.5 px-2 text-xs"
                        onClick={() => setAuthTokenInput(' ')}
                      >
                        Change
                      </Button>
                    </div>
                  )}
                  {(!settings.api_has_auth_token || authTokenInput) && (
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type={showAuthToken ? 'text' : 'password'}
                          value={authTokenInput.trim()}
                          onChange={(e) => setAuthTokenInput(e.target.value)}
                          placeholder="Enter API key..."
                          className="w-full py-1.5 px-3 pe-9 text-sm border rounded-md bg-background"
                        />
                        <button
                          type="button"
                          onClick={() => setShowAuthToken(!showAuthToken)}
                          className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          {showAuthToken ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                      <Button
                        size="sm"
                        onClick={handleSaveAuthToken}
                        disabled={!authTokenInput.trim() || isSaving}
                      >
                        Save
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* Custom Base URL Field */}
              {showBaseUrlField && (
                <div className="space-y-2 pt-1">
                  <Label className="text-sm">Base URL</Label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={customBaseUrlInput || settings.api_base_url || ''}
                      onChange={(e) => setCustomBaseUrlInput(e.target.value)}
                      placeholder="https://api.example.com/v1"
                      className="flex-1 py-1.5 px-3 text-sm border rounded-md bg-background"
                    />
                    <Button
                      size="sm"
                      onClick={handleSaveCustomBaseUrl}
                      disabled={!customBaseUrlInput.trim() || isSaving}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Model Selection */}
            <div className="space-y-2">
              <Label className="font-medium">Model</Label>
              {models.length > 0 && (
                <div className="flex rounded-lg border overflow-hidden">
                  {models.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => handleModelChange(model.id)}
                      disabled={isSaving}
                      className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                        (settings.api_model ?? settings.model) === model.id
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-background text-foreground hover:bg-muted'
                      } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <span className="block">{model.name}</span>
                      <span className="block text-xs opacity-60">{model.id}</span>
                    </button>
                  ))}
                </div>
              )}
              {/* Custom model input for Ollama/Custom */}
              {showCustomModelInput && (
                <div className="flex gap-2 pt-1">
                  <input
                    type="text"
                    value={customModelInput}
                    onChange={(e) => setCustomModelInput(e.target.value)}
                    placeholder="Custom model name..."
                    className="flex-1 py-1.5 px-3 text-sm border rounded-md bg-background"
                    onKeyDown={(e) => e.key === 'Enter' && handleSaveCustomModel()}
                  />
                  <Button
                    size="sm"
                    onClick={handleSaveCustomModel}
                    disabled={!customModelInput.trim() || isSaving}
                  >
                    Set
                  </Button>
                </div>
              )}
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

            {/* Headless Browser Toggle */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="playwright-headless" className="font-medium">
                  Headless Browser
                </Label>
                <p className="text-sm text-muted-foreground">
                  Run browser without visible window (saves CPU)
                </p>
              </div>
              <Switch
                id="playwright-headless"
                checked={settings.playwright_headless}
                onCheckedChange={() => updateSettings.mutate({ playwright_headless: !settings.playwright_headless })}
                disabled={isSaving}
              />
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

            {/* Features per Agent */}
            <div className="space-y-2">
              <Label className="font-medium">Features per Agent</Label>
              <p className="text-sm text-muted-foreground">
                Number of features assigned to each coding agent
              </p>
              <div className="flex rounded-lg border overflow-hidden">
                {[1, 2, 3].map((size) => (
                  <button
                    key={size}
                    onClick={() => handleBatchSizeChange(size)}
                    disabled={isSaving}
                    className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                      (settings.batch_size ?? 1) === size
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-background text-foreground hover:bg-muted'
                    } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {size}
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
      </DialogContent>
    </Dialog>
  )
}
