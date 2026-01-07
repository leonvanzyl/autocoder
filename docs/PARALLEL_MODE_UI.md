# Parallel Mode in UI - How to Use

## ✅ Integration Complete!

The parallel agent system is now fully integrated with your UI! You can control parallel agents directly from the web interface.

---

## 🎮 How to Use Parallel Mode

### Option 1: Web UI (Recommended)

1. **Start the UI**
   ```bash
   # Windows
   start_ui.bat

   # macOS/Linux
   ./start_ui.sh
   ```

2. **Select Your Project**
   - Choose your project from the dropdown

3. **Enable Parallel Mode**
   - Click the **Branch icon** (GitBranch) button
   - This toggles parallel mode on (mutually exclusive with YOLO mode)

4. **Configure Settings**
   - **Agent Count**: Select 1-5 agents (default: 3)
   - **Model Preset**: Choose from:
     - **Quality** - Opus only (best quality)
     - **Balanced** ⭐ - Opus + Haiku (recommended)
     - **Economy** - Opus + Sonnet + Haiku
     - **Cheap** - Sonnet + Haiku
     - **Experimental** - All models

5. **Start Agents**
   - Click the **Play button** to start
   - Status indicator shows "Running"
   - Parallel mode badge shows "3x balanced" (or your selection)

### Option 2: CLI

```bash
# Start 3 parallel agents with balanced preset
python orchestrator_demo.py \
  --project-dir ./my-app \
  --parallel 3 \
  --preset balanced

# Start 5 agents (maximum)
python orchestrator_demo.py \
  --project-dir ./my-app \
  --parallel 5 \
  --preset quality
```

---

## 🎨 UI Features

### Mode Indicators

When agents are running, you'll see mode indicators:

- **YOLO Mode** (yellow): Skip testing for rapid prototyping
- **Parallel Mode** (cyan): Shows "3x balanced" or similar

### Mode Toggles

When stopped, you can toggle:

- **⚡ YOLO** - Skip testing (faster, no verification)
- **🌿 Parallel** - Run multiple agents (3x faster)

**Note**: YOLO and Parallel modes are mutually exclusive (can't enable both)

### Agent Count Selector

When Parallel mode is enabled:
- Dropdown with 1-5 agents
- More agents = faster, but higher API costs
- Recommended: 3 agents for balance

### Model Preset Selector

When Parallel mode is enabled:
- **Quality (Opus)** - Best for complex features
- **Balanced ⭐** - Recommended for most projects
- **Economy** - Mix of Opus, Sonnet, Haiku
- **Cheap** - Only Sonnet and Haiku
- **Experimental** - Try all models

---

## ⚡ Performance

### Single Agent (Standard Mode)
```
Feature 1 → Feature 2 → Feature 3
Total: 40 minutes
```

### Parallel Agents (Parallel Mode)
```
Agent 1: Feature 1 (Opus)     ┐
Agent 2: Feature 2 (Haiku)    ├→ Total: 13 minutes
Agent 3: Feature 3 (Opus)     ┘
```

**Speedup: 3x faster!**

---

## 📊 What's Different?

### Standard Mode (autonomous_agent_demo.py)
- Sequential feature execution
- Single agent working on one feature at a time
- YOLO mode available (skip testing)

### Parallel Mode (orchestrator_demo.py)
- **3-5 agents working simultaneously**
- **Isolated worktrees** (no file conflicts)
- **Checkpoint/rollback** (easy recovery from mistakes)
- **Gatekeeper verification** (only merges if tests pass)
- **Knowledge base learning** (gets smarter over time)
- **Smart model selection** (Opus for complex, Haiku for simple)

---

## 🔧 Under the Hood

### Architecture

```
UI (React)
  ↓
API (FastAPI)
  ↓
Process Manager
  ↓
orchestrator_demo.py (NEW!)
  ↓
Orchestrator
  ├─ WorktreeManager (isolated workspaces)
  ├─ KnowledgeBase (learns from patterns)
  ├─ ModelSettings (smart model selection)
  ├─ Gatekeeper (verifies work)
  └─ Database (tracks progress)
```

### Files Modified

**Backend (Python):**
- `orchestrator_demo.py` - NEW! Entry point for parallel agents
- `server/schemas.py` - Added parallel mode fields
- `server/services/process_manager.py` - Added parallel mode support
- `server/routers/agent.py` - Updated API endpoints

**Frontend (React/TypeScript):**
- `ui/src/lib/types.ts` - Added parallel mode types
- `ui/src/lib/api.ts` - Updated startAgent function
- `ui/src/hooks/useProjects.ts` - Updated hook signatures
- `ui/src/components/AgentControl.tsx` - Added parallel controls
- `ui/src/App.tsx` - Pass parallel mode props
- `ui/src/styles/globals.css` - Added neo-btn-info style

---

## 🚀 Quick Start Example

1. **Launch UI**
   ```bash
   start_ui.bat
   ```

2. **Open Browser**
   - Navigate to `http://localhost:8000`

3. **Select Project**
   - Choose your project from dropdown

4. **Enable Parallel Mode**
   - Click the Branch button (🌿)
   - Select "3 Agents"
   - Select "Balanced" preset

5. **Start!**
   - Click Play button (▶️)
   - Watch 3 agents build your project 3x faster!

---

## 📝 Tips

- **First time?** Start with 3 agents and "Balanced" preset
- **Complex features?** Use "Quality" preset (Opus only)
- **Budget conscious?** Use "Economy" or "Cheap" presets
- **Maximum speed?** Use 5 agents with "Balanced" preset
- **Testing?** Use YOLO mode for rapid prototyping, switch to Parallel for production

---

## 🐛 Troubleshooting

**Q: Parallel button is disabled**
A: YOLO mode is enabled - they're mutually exclusive. Disable YOLO first.

**Q: Agents not starting**
A: Check that `orchestrator_demo.py` exists in root directory.

**Q: Only seeing 1x speedup**
A: Some features depend on others (soft scheduling). More features = better parallelization.

**Q: Want to see what agents are doing**
A: Check the Debug Log viewer - shows output from all agents.

---

**Status: ✅ Ready to use!**

Launch the UI and try parallel mode now! 🚀
