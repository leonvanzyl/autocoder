/**
 * UI Library Selector Component
 *
 * Allows users to select a UI component library during project creation.
 * Shows preview images and MCP availability badges.
 */

import { useState } from 'react'
import { Check, Zap, Code2, Sparkles, Box } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export interface UILibrary {
  id: string
  name: string
  description: string
  frameworks: string[]
  hasMcp: boolean
  isRecommended?: boolean
  previewImage?: string
}

const UI_LIBRARIES: UILibrary[] = [
  {
    id: 'shadcn-ui',
    name: 'shadcn/ui',
    description: 'Beautiful, accessible React components with Radix primitives',
    frameworks: ['react'],
    hasMcp: true,
    isRecommended: true,
  },
  {
    id: 'ark-ui',
    name: 'Ark UI',
    description: 'Headless primitives for any framework',
    frameworks: ['react', 'vue', 'solid', 'svelte'],
    hasMcp: true,
  },
  {
    id: 'radix-ui',
    name: 'Radix UI',
    description: 'Low-level headless primitives',
    frameworks: ['react'],
    hasMcp: false,
  },
  {
    id: 'none',
    name: 'Custom/None',
    description: 'Build components from scratch',
    frameworks: ['react', 'vue', 'solid', 'svelte', 'vanilla'],
    hasMcp: false,
  },
]

interface UILibrarySelectorProps {
  value: string
  framework: string
  onChange: (libraryId: string) => void
  className?: string
}

export function UILibrarySelector({
  value,
  framework,
  onChange,
  className,
}: UILibrarySelectorProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const getLibraryIcon = (id: string) => {
    switch (id) {
      case 'shadcn-ui':
        return <Sparkles className="h-5 w-5" />
      case 'ark-ui':
        return <Box className="h-5 w-5" />
      case 'radix-ui':
        return <Code2 className="h-5 w-5" />
      case 'none':
        return <Code2 className="h-5 w-5" />
      default:
        return <Box className="h-5 w-5" />
    }
  }

  const isCompatible = (lib: UILibrary) => {
    return lib.frameworks.includes(framework) || lib.id === 'none'
  }

  return (
    <div className={cn('grid grid-cols-1 gap-3 sm:grid-cols-2', className)}>
      {UI_LIBRARIES.map((lib) => {
        const selected = value === lib.id
        const compatible = isCompatible(lib)
        // hoveredId is tracked for potential future hover preview effects
        const _hovered = hoveredId === lib.id
        void _hovered // Suppress unused variable warning

        return (
          <Card
            key={lib.id}
            className={cn(
              'relative cursor-pointer transition-all duration-200',
              'hover:border-primary/50 hover:shadow-md',
              selected && 'border-primary ring-2 ring-primary/20',
              !compatible && 'opacity-50 cursor-not-allowed'
            )}
            onClick={() => compatible && onChange(lib.id)}
            onMouseEnter={() => setHoveredId(lib.id)}
            onMouseLeave={() => setHoveredId(null)}
            role="option"
            aria-selected={selected}
            aria-disabled={!compatible}
            aria-label={`Select ${lib.name} component library`}
            tabIndex={compatible ? 0 : -1}
            onKeyDown={(e) => {
              if (compatible && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault()
                onChange(lib.id)
              }
            }}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {getLibraryIcon(lib.id)}
                  <CardTitle className="text-base">{lib.name}</CardTitle>
                </div>
                {selected && (
                  <div className="rounded-full bg-primary p-1">
                    <Check className="h-3 w-3 text-primary-foreground" />
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {lib.hasMcp && (
                  <Badge variant="secondary" className="text-xs gap-1">
                    <Zap className="h-3 w-3" />
                    MCP Enabled
                  </Badge>
                )}
                {lib.isRecommended && framework === 'react' && (
                  <Badge variant="default" className="text-xs">
                    Recommended
                  </Badge>
                )}
                {!compatible && (
                  <Badge variant="destructive" className="text-xs">
                    Not compatible with {framework}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <CardDescription className="text-xs">
                {lib.description}
              </CardDescription>
              {lib.frameworks.length > 0 && lib.id !== 'none' && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {lib.frameworks.map((fw) => (
                    <span
                      key={fw}
                      className={cn(
                        'text-[10px] px-1.5 py-0.5 rounded bg-muted',
                        fw === framework && 'bg-primary/10 text-primary font-medium'
                      )}
                    >
                      {fw}
                    </span>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export { UI_LIBRARIES }
