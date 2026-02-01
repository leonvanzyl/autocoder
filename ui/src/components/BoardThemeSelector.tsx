import { Check, Rocket, Sparkles } from 'lucide-react'
import { useBoardTheme } from '../contexts/ThemeContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

// Theme icons
const themeIcons: Record<string, typeof Rocket> = {
  default: Sparkles,
  starfleet_tos: Rocket,
}

export function BoardThemeSelector() {
  const { theme, themeId, setThemeId, availableThemes } = useBoardTheme()
  const CurrentIcon = themeIcons[themeId] || Sparkles

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <CurrentIcon size={16} />
          <span className="hidden sm:inline">{theme.name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
          Board Theme
        </div>
        {availableThemes.map((t) => {
          const Icon = themeIcons[t.id] || Sparkles
          return (
            <DropdownMenuItem
              key={t.id}
              onClick={() => setThemeId(t.id)}
              className="flex items-center gap-3 cursor-pointer"
            >
              <Icon size={18} className={t.id === themeId ? 'text-primary' : 'text-muted-foreground'} />
              <div className="flex-1">
                <div className="font-medium">{t.name}</div>
                <div className="text-xs text-muted-foreground">{t.description}</div>
              </div>
              {t.id === themeId && <Check size={16} className="text-primary" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
