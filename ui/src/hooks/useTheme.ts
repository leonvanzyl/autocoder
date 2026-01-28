import { useState, useEffect, useCallback } from "react";

export type ThemeId =
  | "twitter"
  | "claude"
  | "neo-brutalism"
  | "retro-arcade"
  | "aurora";

export interface ThemeOption {
  id: ThemeId;
  name: string;
  description: string;
  previewColors: {
    primary: string;
    background: string;
    accent: string;
  };
}

export const THEMES: ThemeOption[] = [
  {
    id: "twitter",
    name: "Twitter",
    description: "Clean and modern blue design",
    previewColors: {
      primary: "#4a9eff",
      background: "#ffffff",
      accent: "#e8f4ff",
    },
  },
  {
    id: "claude",
    name: "Claude",
    description: "Warm beige tones with orange accents",
    previewColors: {
      primary: "#c75b2a",
      background: "#faf6f0",
      accent: "#f5ede4",
    },
  },
  {
    id: "neo-brutalism",
    name: "Neo Brutalism",
    description: "Bold colors with hard shadows",
    previewColors: {
      primary: "#ff4d00",
      background: "#ffffff",
      accent: "#ffeb00",
    },
  },
  {
    id: "retro-arcade",
    name: "Retro Arcade",
    description: "Vibrant pink and teal pixel vibes",
    previewColors: {
      primary: "#e8457c",
      background: "#f0e6d3",
      accent: "#4eb8a5",
    },
  },
  {
    id: "aurora",
    name: "Aurora",
    description: "Deep violet and teal, like northern lights",
    previewColors: {
      primary: "#8b5cf6",
      background: "#faf8ff",
      accent: "#2dd4bf",
    },
  },
];

const THEME_STORAGE_KEY = "autocoder-theme";
const DARK_MODE_STORAGE_KEY = "autocoder-dark-mode";

function getThemeClass(themeId: ThemeId): string {
  switch (themeId) {
    case "twitter":
      return ""; // Default, no class needed
    case "claude":
      return "theme-claude";
    case "neo-brutalism":
      return "theme-neo-brutalism";
    case "retro-arcade":
      return "theme-retro-arcade";
    case "aurora":
      return "theme-aurora";
    default:
      return "";
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      if (
        stored === "twitter" ||
        stored === "claude" ||
        stored === "neo-brutalism" ||
        stored === "retro-arcade" ||
        stored === "aurora"
      ) {
        return stored;
      }
    } catch {
      // localStorage not available
    }
    return "twitter";
  });

  const [darkMode, setDarkModeState] = useState(() => {
    try {
      return localStorage.getItem(DARK_MODE_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  // Apply theme and dark mode classes to document
  useEffect(() => {
    const root = document.documentElement;

    // Remove all theme classes
    root.classList.remove(
      "theme-claude",
      "theme-neo-brutalism",
      "theme-retro-arcade",
      "theme-aurora",
    );

    // Add current theme class (if not twitter/default)
    const themeClass = getThemeClass(theme);
    if (themeClass) {
      root.classList.add(themeClass);
    }

    // Handle dark mode
    if (darkMode) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

    // Persist to localStorage
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
      localStorage.setItem(DARK_MODE_STORAGE_KEY, String(darkMode));
    } catch {
      // localStorage not available
    }
  }, [theme, darkMode]);

  const setTheme = useCallback((newTheme: ThemeId) => {
    setThemeState(newTheme);
  }, []);

  const setDarkMode = useCallback((enabled: boolean) => {
    setDarkModeState(enabled);
  }, []);

  const toggleDarkMode = useCallback(() => {
    setDarkModeState((prev) => !prev);
  }, []);

  return {
    theme,
    setTheme,
    darkMode,
    setDarkMode,
    toggleDarkMode,
    themes: THEMES,
    currentTheme: THEMES.find((t) => t.id === theme) ?? THEMES[0],
  };
}
