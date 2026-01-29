import { useState, useRef, useEffect } from 'react'
import { Palette, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ThemeId, ThemeOption } from '../hooks/useTheme'

interface ThemeSelectorProps {
  themes: ThemeOption[]
  currentTheme: ThemeId
  onThemeChange: (theme: ThemeId) => void
}

export function ThemeSelector({ themes, currentTheme, onThemeChange }: ThemeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [previewTheme, setPreviewTheme] = useState<ThemeId | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setPreviewTheme(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Apply preview theme temporarily
  useEffect(() => {
    if (previewTheme) {
      const root = document.documentElement
      root.classList.remove('theme-claude', 'theme-neo-brutalism', 'theme-retro-arcade', 'theme-aurora', 'theme-business')
      if (previewTheme === 'claude') {
        root.classList.add('theme-claude')
      } else if (previewTheme === 'neo-brutalism') {
        root.classList.add('theme-neo-brutalism')
      } else if (previewTheme === 'retro-arcade') {
        root.classList.add('theme-retro-arcade')
      } else if (previewTheme === 'aurora') {
        root.classList.add('theme-aurora')
      } else if (previewTheme === 'business') {
        root.classList.add('theme-business')
      }
    }

    // Cleanup: restore current theme when preview ends
    return () => {
      if (previewTheme) {
        const root = document.documentElement
        root.classList.remove('theme-claude', 'theme-neo-brutalism', 'theme-retro-arcade', 'theme-aurora', 'theme-business')
        if (currentTheme === 'claude') {
          root.classList.add('theme-claude')
        } else if (currentTheme === 'neo-brutalism') {
          root.classList.add('theme-neo-brutalism')
        } else if (currentTheme === 'retro-arcade') {
          root.classList.add('theme-retro-arcade')
        } else if (currentTheme === 'aurora') {
          root.classList.add('theme-aurora')
        } else if (currentTheme === 'business') {
          root.classList.add('theme-business')
        }
      }
    }
  }, [previewTheme, currentTheme])

  const handleMouseEnter = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setIsOpen(true)
  }

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false)
      setPreviewTheme(null)
    }, 150)
  }

  const handleThemeHover = (themeId: ThemeId) => {
    setPreviewTheme(themeId)
  }

  const handleThemeClick = (themeId: ThemeId) => {
    onThemeChange(themeId)
    setPreviewTheme(null)
    setIsOpen(false)
  }

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Button
        variant="outline"
        size="sm"
        title="Theme"
        aria-label="Select theme"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <Palette size={18} />
      </Button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-56 bg-popover border-2 border-border rounded-lg shadow-lg z-50 animate-slide-in-down overflow-hidden"
          role="menu"
          aria-orientation="vertical"
        >
          <div className="p-2 space-y-1">
            {themes.map((theme) => (
              <button
                key={theme.id}
                onClick={() => handleThemeClick(theme.id)}
                onMouseEnter={() => handleThemeHover(theme.id)}
                onMouseLeave={() => setPreviewTheme(null)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${
                  currentTheme === theme.id
                    ? 'bg-primary/10 text-foreground'
                    : 'hover:bg-muted text-foreground'
                }`}
                role="menuitem"
              >
                {/* Color swatches */}
                <div className="flex gap-0.5 shrink-0">
                  <div
                    className="w-4 h-4 rounded-sm border border-border/50"
                    style={{ backgroundColor: theme.previewColors.background }}
                  />
                  <div
                    className="w-4 h-4 rounded-sm border border-border/50"
                    style={{ backgroundColor: theme.previewColors.primary }}
                  />
                  <div
                    className="w-4 h-4 rounded-sm border border-border/50"
                    style={{ backgroundColor: theme.previewColors.accent }}
                  />
                </div>

                {/* Theme name and description */}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm">{theme.name}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {theme.description}
                  </div>
                </div>

                {/* Checkmark for current theme */}
                {currentTheme === theme.id && (
                  <Check size={16} className="text-primary shrink-0" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
