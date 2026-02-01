import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { Theme, themes, getTheme } from '../lib/themes'

interface ThemeContextType {
  theme: Theme
  themeId: string
  setThemeId: (id: string) => void
  availableThemes: { id: string; name: string; description: string }[]
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const THEME_STORAGE_KEY = 'autocoder-theme'

export function BoardThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState<string>(() => {
    // Load from localStorage on mount
    if (typeof window !== 'undefined') {
      return localStorage.getItem(THEME_STORAGE_KEY) || 'default'
    }
    return 'default'
  })

  const theme = getTheme(themeId)

  const setThemeId = (id: string) => {
    setThemeIdState(id)
    localStorage.setItem(THEME_STORAGE_KEY, id)

    // Apply theme colors as CSS custom properties
    applyThemeColors(getTheme(id))
  }

  // Apply theme colors on mount and theme change
  useEffect(() => {
    applyThemeColors(theme)
  }, [theme])

  const availableThemes = Object.values(themes).map(t => ({
    id: t.id,
    name: t.name,
    description: t.description,
  }))

  return (
    <ThemeContext.Provider value={{ theme, themeId, setThemeId, availableThemes }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useBoardTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useBoardTheme must be used within a BoardThemeProvider')
  }
  return context
}

// Apply theme colors as CSS custom properties on :root
function applyThemeColors(theme: Theme) {
  const root = document.documentElement

  // Only apply custom theme colors for non-default themes
  if (theme.id !== 'default') {
    root.style.setProperty('--theme-primary', theme.colors.primary)
    root.style.setProperty('--theme-accent', theme.colors.accent)
    root.style.setProperty('--theme-command', theme.colors.commandColor)
    root.style.setProperty('--theme-science', theme.colors.scienceColor)
    root.style.setProperty('--theme-engineering', theme.colors.engineeringColor)
    root.classList.add(`theme-${theme.id}`)
  } else {
    // Remove custom properties for default theme
    root.style.removeProperty('--theme-primary')
    root.style.removeProperty('--theme-accent')
    root.style.removeProperty('--theme-command')
    root.style.removeProperty('--theme-science')
    root.style.removeProperty('--theme-engineering')

    // Remove any theme classes
    Object.keys(themes).forEach(id => {
      root.classList.remove(`theme-${id}`)
    })
  }
}
