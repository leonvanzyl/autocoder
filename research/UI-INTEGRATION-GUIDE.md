# UI Integration Guide - Model Selection & Parallel Agents

## Overview

Complete UI implementation for AI model selection and parallel agent control with full API integration.

---

## 📁 Files Created

### Backend (Python)
1. `server/routers/model_settings.py` - Model settings REST API
2. `server/routers/parallel_agents.py` - Parallel agents REST API
3. `server/routers/__init__.py` - Updated with new routers
4. `server/main.py` - Registered new API routes
5. `mcp_server/feature_mcp.py` - Added atomic claiming tools

### Frontend (TypeScript/React)
1. `ui/src/hooks/useModelSettings.ts` - Model settings API hooks
2. `ui/src/hooks/useParallelAgents.ts` - Parallel agents API hooks
3. `ui/src/components/ModelSettingsPanel.tsx` - Model configuration UI
4. `ui/src/components/ParallelAgentsControl.tsx` - Parallel agent controls
5. `ui/src/components/AgentStatusGrid.tsx` - Real-time agent status display

---

## 🔌 Integration Steps

### Step 1: Import Components in App.tsx

```tsx
// ui/src/App.tsx
import { ModelSettingsPanel } from './components/ModelSettingsPanel';
import { ParallelAgentsControl } from './components/ParallelAgentsControl';
import { AgentStatusGrid } from './components/AgentStatusGrid';
```

### Step 2: Add State for Modals

```tsx
const [showModelSettings, setShowModelSettings] = useState(false);
const [showParallelControl, setShowParallelControl] = useState(false);
```

### Step 3: Add Control Buttons to UI

```tsx
// In your project view or control panel
<div className="controls">
  <button onClick={() => setShowModelSettings(true)}>
    🧠 Model Settings
  </button>

  <button onClick={() => setShowParallelControl(true)}>
    🚀 Parallel Agents
  </button>
</div>
```

### Step 4: Add Modals

```tsx
{/* Model Settings Modal */}
{showModelSettings && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div className="relative">
      <ModelSettingsPanel onClose={() => setShowModelSettings(false)} />
    </div>
  </div>
)}

{/* Parallel Agents Modal */}
{showParallelControl && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div className="relative">
      <ParallelAgentsControl
        projectDir={currentProject.path}
        onClose={() => setShowParallelControl(false)}
      />
    </div>
  </div>
)}
```

### Step 5: Add Agent Status Grid (Optional Auto-Display)

```tsx
{/* Show agent status when agents are running */}
{showParallelControl && (
  <AgentStatusGrid projectDir={currentProject.path} />
)}
```

---

## 🎨 Complete Example Integration

```tsx
// ui/src/App.tsx (simplified example)

import { useState } from 'react';
import { ModelSettingsPanel } from './components/ModelSettingsPanel';
import { ParallelAgentsControl } from './components/ParallelAgentsControl';
import { AgentStatusGrid } from './components/AgentStatusGrid';

function App() {
  const [currentProject, setCurrentProject] = useState(null);
  const [showModelSettings, setShowModelSettings] = useState(false);
  const [showParallelControl, setShowParallelControl] = useState(false);
  const [autoShowAgentStatus, setAutoShowAgentStatus] = useState(false);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header with Controls */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">🤖 Autonomous Coding</h1>

          <div className="flex gap-3">
            <button
              onClick={() => setShowModelSettings(true)}
              className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
            >
              🧠 Models
            </button>

            <button
              onClick={() => setShowParallelControl(true)}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
            >
              🚀 Parallel
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {currentProject && (
          <>
            {/* Agent Status (auto-show when running) */}
            <AgentStatusGrid projectDir={currentProject.path} />

            {/* Other project content */}
            {/* ... */}
          </>
        )}
      </main>

      {/* Modals */}
      {showModelSettings && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <ModelSettingsPanel onClose={() => setShowModelSettings(false)} />
        </div>
      )}

      {showParallelControl && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <ParallelAgentsControl
            projectDir={currentProject?.path || ''}
            onClose={() => setShowParallelControl(false)}
          />
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 Component Features

### ModelSettingsPanel
- **5 Presets**: quality, balanced, economy, cheap, experimental
- **Visual preset cards** with model badges
- **Category mapping display** (frontend → OPUS, testing → HAIKU, etc.)
- **Auto-detect toggle** for simple task detection
- **Real-time updates** via React Query

### ParallelAgentsControl
- **Agent count slider** (1-5)
- **Model preset display**
- **Start/Stop button** with status indication
- **Live status summary** (running, completed, failed)
- **Automatic polling** for status updates (every 2 seconds)

### AgentStatusGrid
- **Per-agent cards** showing:
  - Agent ID and feature being worked on
  - Status icon (🔄 running, ✅ completed, ❌ failed)
  - Model being used (OPUS/HAIKU/SONNET badge)
  - Progress bar for running agents
- **Summary statistics** (running, completed, failed counts)
- **Responsive grid** (1-3 columns based on screen size)

---

## 📊 API Endpoints

### Model Settings
```typescript
GET    /api/model-settings          // Get current settings
PUT    /api/model-settings          // Update settings
POST   /api/model-settings/preset   // Apply preset
GET    /api/model-settings/presets  // List all presets
POST   /api/model-settings/test     // Test model selection
```

### Parallel Agents
```typescript
POST   /api/parallel-agents/start           // Start agents
POST   /api/parallel-agents/stop            // Stop agents
GET    /api/parallel-agents/status          // Get status
PUT    /api/parallel-agents/config          // Update config
GET    /api/parallel-agents/presets         // List presets
```

---

## 🧪 Testing

### 1. Test Model Settings API
```bash
# Start server
python start_ui.py

# Test endpoints
curl http://localhost:8888/api/model-settings
curl http://localhost:8888/api/model-settings/presets
```

### 2. Test Parallel Agents API
```bash
# Start agents
curl -X POST http://localhost:8888/api/parallel-agents/start \
  -H "Content-Type: application/json" \
  -d '{"project_dir": "/path/to/project", "parallel_count": 3}'

# Check status
curl http://localhost:8888/api/parallel-agents/status?project_dir=/path/to/project

# Stop agents
curl -X POST http://localhost:8888/api/parallel-agents/stop?project_dir=/path/to/project
```

### 3. Test UI
```bash
# Start UI dev server
cd ui
npm run dev

# Open browser
http://localhost:5173

# Click "🧠 Models" button
# - Try different presets
# - Toggle auto-detect
# - See category mapping update

# Click "🚀 Parallel" button
# - Adjust agent count slider
# - Click "Start Agents"
# - Watch agent status grid update
```

---

## 🎨 Customization

### Change Slider Range
```tsx
// ParallelAgentsControl.tsx
<input
  type="range"
  min="1"
  max="10"  // Change from 5 to 10
  value={parallelCount}
  // ...
/>
```

### Add Custom Preset
```typescript
// model_settings.py
CUSTOM_PRESETS = {
  "ultra-fast": {
    "name": "Ultra Fast",
    "models": ["haiku"],
    "best_for": "Maximum speed, lower quality",
    "description": "Haiku only for fastest execution"
  }
}
```

### Modify Polling Interval
```typescript
// useParallelAgents.ts
refetchInterval: 1000, // Change from 2000ms to 1000ms (1 second)
```

### Add Custom Agent Card Fields
```tsx
// AgentStatusGrid.tsx - AgentCard component
<div className="text-xs text-gray-600">
  Started: {new Date(agent.started_at).toLocaleTimeString()}
</div>
```

---

## 🚀 Production Checklist

- [x] API endpoints created
- [x] React hooks created
- [x] UI components created
- [x] Server routers registered
- [ ] **Integrate components into App.tsx**
- [ ] **Test with real project**
- [ ] **Build UI (`npm run build`)**
- [ ] **Test production build (`start_ui.py`)**
- [ ] **Add WebSocket integration for real-time updates** (optional, currently polling)

---

## 🎉 Summary

**What's Complete**:
- ✅ Full REST API for model settings and parallel agents
- ✅ React Query hooks for data fetching
- ✅ Three production-ready UI components
- ✅ Server integration and router registration
- ✅ Type-safe TypeScript throughout

**Next Steps**:
1. Import components into `App.tsx`
2. Add buttons to open modals
3. Test with real project
4. Build UI and test production mode
5. Optional: Add WebSocket for real-time updates

**Estimated Integration Time**: 30 minutes to add to existing UI
