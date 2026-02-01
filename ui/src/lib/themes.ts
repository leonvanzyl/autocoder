/**
 * Theme Configuration for Autocoder
 *
 * Themes customize the look and feel of the Kanban board including:
 * - Agent names (crew members)
 * - Column titles
 * - Color palette
 * - Orchestrator name
 */

export interface Theme {
  id: string
  name: string
  description: string

  // Agent/crew names (index 0 = orchestrator in single-agent mode)
  orchestratorName: string
  agentNames: string[]

  // Kanban column titles
  columns: {
    pending: string
    inProgress: string
    testing: string
    complete: string
  }

  // Color palette (CSS custom properties)
  colors: {
    primary: string
    secondary: string
    accent: string
    success: string
    warning: string
    // Agent type colors
    commandColor: string    // For orchestrator/captain
    scienceColor: string    // For analysis agents
    engineeringColor: string // For coding agents
    // Background
    cardBg?: string
    headerBg?: string
  }

  // Optional flavor
  completionMessage?: string  // Shown when feature completes
  boardTitle?: string         // Optional board header
}

// Default theme - the original Autocoder mascots
export const defaultTheme: Theme = {
  id: 'default',
  name: 'Default',
  description: 'The original Autocoder mascots',

  orchestratorName: 'Orchestrator',
  agentNames: [
    'Spark', 'Fizz', 'Octo', 'Hoot', 'Buzz',
    'Pixel', 'Byte', 'Nova', 'Chip', 'Bolt',
    'Dash', 'Zap', 'Gizmo', 'Turbo', 'Blip',
    'Neon', 'Widget', 'Zippy', 'Quirk', 'Flux',
  ],

  columns: {
    pending: 'Pending',
    inProgress: 'In Progress',
    testing: 'Testing',
    complete: 'Complete',
  },

  colors: {
    primary: 'hsl(187 100% 42%)',      // Cyan
    secondary: 'hsl(210 40% 96%)',
    accent: 'hsl(187 100% 42%)',
    success: 'hsl(142 76% 36%)',
    warning: 'hsl(38 92% 50%)',
    commandColor: 'hsl(187 100% 42%)',
    scienceColor: 'hsl(210 100% 50%)',
    engineeringColor: 'hsl(0 84% 60%)',
  },

  completionMessage: 'Feature complete!',
}

// Star Trek: The Original Series theme
export const starfleetTOSTheme: Theme = {
  id: 'starfleet_tos',
  name: 'Starfleet TOS',
  description: 'Star Trek: The Original Series - USS Enterprise crew',

  orchestratorName: 'Captain Kirk',
  agentNames: [
    'Spock',      // Science Officer - logical, analytical
    'McCoy',      // Chief Medical Officer - diagnostics
    'Scotty',     // Chief Engineer - fixes everything
    'Sulu',       // Helmsman - navigation/direction
    'Uhura',      // Communications - interfaces
    'Chekov',     // Navigator - pathfinding
    'Chapel',     // Nurse - support
    'Riley',      // Lieutenant - general duty
    'Kyle',       // Transporter Chief - data transfer
    'Leslie',     // Security - validation
    'DeSalle',    // Assistant Engineer
    'Rand',       // Yeoman - documentation
  ],

  columns: {
    pending: 'Starbase',
    inProgress: 'Away Mission',
    testing: 'Scanning',
    complete: "Captain's Log",
  },

  colors: {
    primary: 'hsl(45 100% 50%)',       // Command Gold
    secondary: 'hsl(220 30% 20%)',     // Space dark blue
    accent: 'hsl(200 100% 50%)',       // Science Blue
    success: 'hsl(142 76% 36%)',       // Green (success)
    warning: 'hsl(0 84% 50%)',         // Red Alert
    commandColor: 'hsl(45 100% 50%)',  // Command Gold
    scienceColor: 'hsl(200 100% 50%)', // Science Blue
    engineeringColor: 'hsl(0 72% 51%)',// Engineering Red
  },

  completionMessage: "Captain's Log: Mission accomplished!",
  boardTitle: 'USS Enterprise Mission Control',
}

// All available themes
export const themes: Record<string, Theme> = {
  default: defaultTheme,
  starfleet_tos: starfleetTOSTheme,
}

// Helper to get theme by ID
export function getTheme(themeId: string): Theme {
  return themes[themeId] || defaultTheme
}

// Get agent name for a given index within a theme
export function getAgentName(theme: Theme, index: number): string {
  return theme.agentNames[index % theme.agentNames.length]
}

// Get column title for a status
export function getColumnTitle(
  theme: Theme,
  status: 'pending' | 'inProgress' | 'testing' | 'complete'
): string {
  return theme.columns[status]
}
