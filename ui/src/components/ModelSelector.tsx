import { useState, useRef, useEffect } from 'react'
import { Check, ChevronDown, Cpu, Zap, Sparkles } from 'lucide-react'
import type { ModelConfig, ModelTier } from '../lib/types'

interface ModelSelectorProps {
  models: ModelConfig[]
  selectedModelId: string | null
  onSelect: (modelId: string) => void
  label?: string
  disabled?: boolean
  className?: string
  showTierBadge?: boolean
}

const TIER_ICONS: Record<ModelTier, typeof Cpu> = {
  opus: Sparkles,
  sonnet: Zap,
  haiku: Cpu,
}

const TIER_COLORS: Record<ModelTier, string> = {
  opus: 'text-purple-500',
  sonnet: 'text-blue-500',
  haiku: 'text-green-500',
}

const TIER_BG_COLORS: Record<ModelTier, string> = {
  opus: 'bg-purple-500/10',
  sonnet: 'bg-blue-500/10',
  haiku: 'bg-green-500/10',
}

export function ModelSelector({
  models,
  selectedModelId,
  onSelect,
  label,
  disabled = false,
  className = '',
  showTierBadge = true,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedModel = models.find((m) => m.id === selectedModelId)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Group models by tier
  const modelsByTier = models.reduce(
    (acc, model) => {
      if (!acc[model.tier]) {
        acc[model.tier] = []
      }
      acc[model.tier].push(model)
      return acc
    },
    {} as Record<ModelTier, ModelConfig[]>
  )

  const tierOrder: ModelTier[] = ['opus', 'sonnet', 'haiku']

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-foreground mb-1.5">
          {label}
        </label>
      )}

      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          w-full flex items-center justify-between gap-2 px-3 py-2
          bg-background border-2 border-border rounded-lg
          text-left text-sm
          transition-colors
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary/50 cursor-pointer'}
          ${isOpen ? 'border-primary ring-2 ring-primary/20' : ''}
        `}
      >
        {selectedModel ? (
          <div className="flex items-center gap-2 min-w-0">
            {showTierBadge && (
              <TierBadge tier={selectedModel.tier} />
            )}
            <span className="truncate font-medium">{selectedModel.name}</span>
          </div>
        ) : (
          <span className="text-muted-foreground">Select a model...</span>
        )}
        <ChevronDown
          size={16}
          className={`shrink-0 text-muted-foreground transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-popover border-2 border-border rounded-lg shadow-lg overflow-hidden animate-slide-in-down">
          <div className="max-h-64 overflow-y-auto p-1">
            {tierOrder.map((tier) => {
              const tierModels = modelsByTier[tier]
              if (!tierModels?.length) return null

              return (
                <div key={tier} className="mb-1 last:mb-0">
                  {/* Tier Header */}
                  <div className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <TierBadge tier={tier} size="sm" />
                    {tier}
                  </div>

                  {/* Models in Tier */}
                  {tierModels.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => {
                        onSelect(model.id)
                        setIsOpen(false)
                      }}
                      className={`
                        w-full flex items-center gap-2 px-2 py-2 rounded-md
                        text-left text-sm transition-colors
                        ${selectedModelId === model.id
                          ? 'bg-primary/10 text-foreground'
                          : 'hover:bg-muted text-foreground'
                        }
                      `}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{model.name}</div>
                        {model.description && (
                          <div className="text-xs text-muted-foreground truncate">
                            {model.description}
                          </div>
                        )}
                      </div>
                      {selectedModelId === model.id && (
                        <Check size={16} className="shrink-0 text-primary" />
                      )}
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

interface TierBadgeProps {
  tier: ModelTier
  size?: 'sm' | 'md'
}

export function TierBadge({ tier, size = 'md' }: TierBadgeProps) {
  const Icon = TIER_ICONS[tier]
  const iconSize = size === 'sm' ? 12 : 14

  return (
    <span
      className={`
        inline-flex items-center justify-center rounded
        ${TIER_BG_COLORS[tier]} ${TIER_COLORS[tier]}
        ${size === 'sm' ? 'w-5 h-5' : 'w-6 h-6'}
      `}
      title={`${tier.charAt(0).toUpperCase() + tier.slice(1)} tier`}
    >
      <Icon size={iconSize} />
    </span>
  )
}

export default ModelSelector
