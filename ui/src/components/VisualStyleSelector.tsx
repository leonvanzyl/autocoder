/**
 * Visual Style Selector Component
 *
 * Allows users to select a visual style during project creation.
 * Shows color swatches and style previews.
 */

import { useState } from 'react'
import { Check, Paintbrush, Sparkles, Layers, Gamepad2, Settings2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export interface VisualStyle {
  id: string
  name: string
  description: string
  colors: string[]
  generatesTokens: boolean
  previewImage?: string
}

const VISUAL_STYLES: VisualStyle[] = [
  {
    id: 'default',
    name: 'Modern/Clean',
    description: 'Minimal, professional design following library defaults',
    colors: ['#3b82f6', '#64748b', '#ffffff'],
    generatesTokens: false,
  },
  {
    id: 'neobrutalism',
    name: 'Neobrutalism',
    description: 'Bold colors, hard shadows, no border-radius',
    colors: ['#ff6b6b', '#4ecdc4', '#000000'],
    generatesTokens: true,
  },
  {
    id: 'glassmorphism',
    name: 'Glassmorphism',
    description: 'Frosted glass effects, blur, transparency',
    colors: ['#8b5cf6', '#06b6d4', '#f472b6'],
    generatesTokens: true,
  },
  {
    id: 'retro',
    name: 'Retro/Arcade',
    description: 'Pixel-art inspired, vibrant neons, 8-bit aesthetic',
    colors: ['#ff00ff', '#00ffff', '#ffff00'],
    generatesTokens: true,
  },
  {
    id: 'custom',
    name: 'Custom',
    description: 'Define your own design tokens',
    colors: [],
    generatesTokens: true,
  },
]

interface VisualStyleSelectorProps {
  value: string
  onChange: (styleId: string) => void
  className?: string
}

export function VisualStyleSelector({
  value,
  onChange,
  className,
}: VisualStyleSelectorProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const getStyleIcon = (id: string) => {
    switch (id) {
      case 'default':
        return <Paintbrush className="h-5 w-5" />
      case 'neobrutalism':
        return <Sparkles className="h-5 w-5" />
      case 'glassmorphism':
        return <Layers className="h-5 w-5" />
      case 'retro':
        return <Gamepad2 className="h-5 w-5" />
      case 'custom':
        return <Settings2 className="h-5 w-5" />
      default:
        return <Paintbrush className="h-5 w-5" />
    }
  }

  const renderColorSwatches = (colors: string[]) => {
    if (colors.length === 0) return null

    return (
      <div className="flex gap-1 mt-2">
        {colors.map((color, index) => (
          <div
            key={index}
            className="h-6 w-6 rounded-full border border-border shadow-sm"
            style={{ backgroundColor: color }}
            aria-label={`Color swatch: ${color}`}
          />
        ))}
      </div>
    )
  }

  const renderStylePreview = (style: VisualStyle) => {
    switch (style.id) {
      case 'neobrutalism':
        return (
          <div className="mt-3 p-2 bg-muted/50 rounded">
            <div
              className="h-8 w-full rounded-none border-4 border-black flex items-center justify-center text-xs font-bold"
              style={{
                backgroundColor: '#ff6b6b',
                boxShadow: '4px 4px 0 0 black',
              }}
            >
              Button Preview
            </div>
          </div>
        )
      case 'glassmorphism':
        return (
          <div
            className="mt-3 p-2 rounded-xl"
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            }}
          >
            <div
              className="h-8 w-full rounded-lg flex items-center justify-center text-xs font-medium text-white"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                backdropFilter: 'blur(8px)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
              }}
            >
              Button Preview
            </div>
          </div>
        )
      case 'retro':
        return (
          <div className="mt-3 p-2 bg-black rounded">
            <div
              className="h-8 w-full flex items-center justify-center text-xs font-mono uppercase"
              style={{
                color: '#00ff00',
                textShadow: '0 0 5px #00ff00',
                border: '2px solid #00ffff',
                boxShadow: '0 0 10px #ff00ff, 0 0 20px #00ffff',
              }}
            >
              Button Preview
            </div>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div
      className={cn('grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3', className)}
      role="listbox"
      aria-label="Select visual style"
    >
      {VISUAL_STYLES.map((style) => {
        const selected = value === style.id
        // hoveredId is tracked for potential future hover preview effects
        const _hovered = hoveredId === style.id
        void _hovered // Suppress unused variable warning

        return (
          <Card
            key={style.id}
            className={cn(
              'relative cursor-pointer transition-all duration-200',
              'hover:border-primary/50 hover:shadow-md',
              selected && 'border-primary ring-2 ring-primary/20'
            )}
            onClick={() => onChange(style.id)}
            onMouseEnter={() => setHoveredId(style.id)}
            onMouseLeave={() => setHoveredId(null)}
            role="option"
            aria-selected={selected}
            aria-label={`Select ${style.name} visual style`}
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onChange(style.id)
              }
            }}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {getStyleIcon(style.id)}
                  <CardTitle className="text-base">{style.name}</CardTitle>
                </div>
                {selected && (
                  <div className="rounded-full bg-primary p-1">
                    <Check className="h-3 w-3 text-primary-foreground" />
                  </div>
                )}
              </div>
              {style.generatesTokens && style.id !== 'custom' && (
                <Badge variant="secondary" className="text-xs w-fit mt-1">
                  Generates design tokens
                </Badge>
              )}
              {style.id === 'default' && (
                <Badge variant="default" className="text-xs w-fit mt-1">
                  Recommended
                </Badge>
              )}
            </CardHeader>
            <CardContent className="pt-0">
              <CardDescription className="text-xs">
                {style.description}
              </CardDescription>
              {renderColorSwatches(style.colors)}
              {renderStylePreview(style)}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export { VISUAL_STYLES }
