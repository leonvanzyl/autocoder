# Custom Updates - AutoCoder

This document tracks all customizations made to AutoCoder that deviate from the upstream repository. Reference this file before any updates to preserve these changes.

---

## Table of Contents

1. [UI Theme Customization](#1-ui-theme-customization)
2. [Playwright Browser Configuration](#2-playwright-browser-configuration)
3. [SQLite Robust Connection Handling](#3-sqlite-robust-connection-handling)
4. [Update Checklist](#update-checklist)

---

## 1. UI Theme Customization

### Overview

The UI has been customized from the default **neobrutalism** style to a clean **Twitter/Supabase-style** design.

**Design Changes:**
- No shadows
- Thin borders (1px)
- Rounded corners (1.3rem base)
- Blue accent color (Twitter blue)
- Clean typography (Open Sans)

### Modified Files

#### `ui/src/styles/custom-theme.css`

**Purpose:** Main theme override file that replaces neo design with clean Twitter style.

**Key Changes:**
- All `--shadow-neo-*` variables set to `none`
- All status colors (`pending`, `progress`, `done`) use Twitter blue
- Rounded corners: `--radius-neo-lg: 1.3rem`
- Font: Open Sans
- Removed all transform effects on hover
- Dark mode with proper contrast

**CSS Variables (Light Mode):**
```css
--color-neo-accent: oklch(0.6723 0.1606 244.9955);  /* Twitter blue */
--color-neo-pending: oklch(0.6723 0.1606 244.9955);
--color-neo-progress: oklch(0.6723 0.1606 244.9955);
--color-neo-done: oklch(0.6723 0.1606 244.9955);
```

**CSS Variables (Dark Mode):**
```css
--color-neo-bg: oklch(0.08 0 0);
--color-neo-card: oklch(0.16 0.005 250);
--color-neo-border: oklch(0.30 0 0);
```

**How to preserve:** This file should NOT be overwritten. It loads after `globals.css` and overrides it.

---

#### `ui/src/components/KanbanColumn.tsx`

**Purpose:** Modified to support themeable kanban columns without inline styles.

**Changes:**

1. **colorMap changed from inline colors to CSS classes:**
```tsx
// BEFORE (original):
const colorMap = {
  pending: 'var(--color-neo-pending)',
  progress: 'var(--color-neo-progress)',
  done: 'var(--color-neo-done)',
}

// AFTER (customized):
const colorMap = {
  pending: 'kanban-header-pending',
  progress: 'kanban-header-progress',
  done: 'kanban-header-done',
}
```

2. **Column div uses CSS class instead of inline style:**
```tsx
// BEFORE:
<div className="neo-card overflow-hidden" style={{ borderColor: colorMap[color] }}>

// AFTER:
<div className={`neo-card overflow-hidden kanban-column ${colorMap[color]}`}>
```

3. **Header div simplified (removed duplicate color class):**
```tsx
// BEFORE:
<div className={`... ${colorMap[color]}`} style={{ backgroundColor: colorMap[color] }}>

// AFTER:
<div className="kanban-header px-4 py-3 border-b border-[var(--color-neo-border)]">
```

4. **Title text color:**
```tsx
// BEFORE:
text-[var(--color-neo-text-on-bright)]

// AFTER:
text-[var(--color-neo-text)]
```

---

## 2. Playwright Browser Configuration

### Overview

Changed default Playwright settings for better performance:
- **Default browser:** Firefox (lower CPU usage)
- **Default mode:** Headless (saves resources)

### Modified Files

#### `client.py`

**Changes:**

```python
# BEFORE:
DEFAULT_PLAYWRIGHT_HEADLESS = False

# AFTER:
DEFAULT_PLAYWRIGHT_HEADLESS = True
DEFAULT_PLAYWRIGHT_BROWSER = "firefox"
```

**New function added:**
```python
def get_playwright_browser() -> str:
    """
    Get the browser to use for Playwright.
    Options: chrome, firefox, webkit, msedge
    Firefox is recommended for lower CPU usage.
    """
    return os.getenv("PLAYWRIGHT_BROWSER", DEFAULT_PLAYWRIGHT_BROWSER).lower()
```

**Playwright args updated:**
```python
playwright_args = [
    "@playwright/mcp@latest",
    "--viewport-size", "1280x720",
    "--browser", browser,  # NEW: configurable browser
]
```

---

#### `.env.example`

**Updated documentation:**
```bash
# PLAYWRIGHT_BROWSER: Which browser to use for testing
# - firefox: Lower CPU usage, recommended (default)
# - chrome: Google Chrome
# - webkit: Safari engine
# - msedge: Microsoft Edge
# PLAYWRIGHT_BROWSER=firefox

# PLAYWRIGHT_HEADLESS: Run browser without visible window
# - true: Browser runs in background, saves CPU (default)
# - false: Browser opens a visible window (useful for debugging)
# PLAYWRIGHT_HEADLESS=true
```

---

## 3. SQLite Robust Connection Handling

### Overview

Added robust SQLite connection handling to prevent database corruption from concurrent access (MCP server, FastAPI server, progress tracking).

**Features Added:**
- WAL mode for better concurrency
- Busy timeout (30 seconds)
- Retry logic with exponential backoff
- Database health check endpoint

### Modified Files

#### `api/database.py`

**New functions added:**

```python
def get_robust_connection(db_path: str) -> sqlite3.Connection:
    """
    Create a SQLite connection with robust settings:
    - WAL mode for concurrent access
    - 30 second busy timeout
    - Foreign keys enabled
    """

@contextmanager
def robust_db_connection(db_path: str):
    """Context manager for robust database connections."""

def execute_with_retry(conn, sql, params=None, max_retries=3):
    """Execute SQL with exponential backoff retry for transient errors."""

def check_database_health(db_path: str) -> dict:
    """
    Check database integrity and return health status.
    Returns: {healthy: bool, message: str, details: dict}
    """
```

---

#### `progress.py`

**Changed from raw sqlite3 to robust connections:**

```python
# BEFORE:
conn = sqlite3.connect(db_path)

# AFTER:
from api.database import robust_db_connection, execute_with_retry

with robust_db_connection(db_path) as conn:
    execute_with_retry(conn, sql, params)
```

---

#### `server/routers/projects.py`

**New endpoint added:**

```python
@router.get("/{project_name}/db-health")
async def get_database_health(project_name: str) -> DatabaseHealth:
    """
    Check the health of the project's features database.
    Useful for diagnosing corruption issues.
    """
```

---

#### `server/schemas.py`

**New schema added:**

```python
class DatabaseHealth(BaseModel):
    healthy: bool
    message: str
    details: dict = {}
```

---

## Update Checklist

When updating AutoCoder from upstream, verify these items:

### UI Changes
- [ ] `ui/src/styles/custom-theme.css` is preserved
- [ ] `ui/src/components/KanbanColumn.tsx` changes are preserved
- [ ] Run `npm run build` in `ui/` directory
- [ ] Test both light and dark modes

### Backend Changes
- [ ] `client.py` - Playwright browser/headless defaults preserved
- [ ] `.env.example` - Documentation updates preserved
- [ ] `api/database.py` - Robust connection functions preserved
- [ ] `progress.py` - Uses robust_db_connection
- [ ] `server/routers/projects.py` - db-health endpoint preserved
- [ ] `server/schemas.py` - DatabaseHealth schema preserved

### General
- [ ] Test database operations under concurrent load
- [ ] Verify Playwright uses Firefox by default
- [ ] Check that browser runs headless by default

---

## Reverting to Defaults

### UI Only
```bash
rm ui/src/styles/custom-theme.css
git checkout ui/src/components/KanbanColumn.tsx
cd ui && npm run build
```

### Backend Only
```bash
git checkout client.py .env.example api/database.py progress.py
git checkout server/routers/projects.py server/schemas.py
```

---

## Files Summary

| File | Type | Change Description |
|------|------|-------------------|
| `ui/src/styles/custom-theme.css` | UI | Twitter-style theme |
| `ui/src/components/KanbanColumn.tsx` | UI | Themeable kanban columns |
| `client.py` | Backend | Firefox + headless defaults |
| `.env.example` | Config | Updated documentation |
| `api/database.py` | Backend | Robust SQLite connections |
| `progress.py` | Backend | Uses robust connections |
| `server/routers/projects.py` | Backend | db-health endpoint |
| `server/schemas.py` | Backend | DatabaseHealth schema |

---

## Last Updated

**Date:** January 2026
**Commits:**
- `1910b96` - SQLite robust connection handling
- `e014b04` - Custom theme override system
