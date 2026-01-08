# React Frontend - Context Documentation

## Overview

The React frontend is a **Neobrutalism-styled** dashboard built with:
- React 18 + TypeScript
- TanStack Query (React Query)
- Tailwind CSS v4
- WebSockets for real-time updates

---

## Component Tree

```
App.tsx (Root)
├── ProjectSelector
│   └── NewProjectModal
│       ├── Step 1: Name Input
│       ├── Step 2: FolderBrowser
│       ├── Step 3: Method Selection
│       ├── Step 4: SpecCreationChat
│       └── Step 5: Complete
├── AgentControl (Play/Pause/Stop)
├── ProgressDashboard
├── AgentThought
├── KanbanBoard
│   ├── KanbanColumn (Pending)
│   ├── KanbanColumn (In Progress)
│   └── KanbanColumn (Done)
│       └── FeatureCard[]
├── AddFeatureForm (Modal)
├── FeatureModal (Detail View)
├── DebugLogViewer (Bottom Panel)
├── AssistantFAB (Floating Button)
└── AssistantPanel
    └── AssistantChat
```

---

## Key Components

### App.tsx
**State:**
- `selectedProject`: Current project (localStorage)
- `showAddFeature`: Add feature modal
- `selectedFeature`: Feature detail modal
- `debugOpen`: Debug panel visibility
- `assistantOpen`: Assistant panel

**Keyboard Shortcuts:**
- `D`: Toggle debug panel
- `N`: New feature
- `A`: Toggle assistant
- `Esc`: Close modals

### NewProjectModal.tsx
**Steps:**
1. Name: Project name validation
2. Folder: FolderBrowser for location
3. Method: Claude AI vs Manual
4. Chat: SpecCreationChat (if Claude)
5. Complete: Success + agent start

**State:**
- `step`: 'name' | 'folder' | 'method' | 'chat' | 'complete'
- `projectName`, `projectPath`
- `initializerStatus`: 'idle' | 'starting' | 'error'
- `yoloModeSelected`: boolean

### KanbanBoard.tsx
Maps features to three columns:
- Pending: `passes=false, in_progress=false`
- In Progress: `in_progress=true`
- Done: `passes=true`

### AgentControl.tsx
**Controls by Status:**
- Stopped/Crashed: YOLO toggle + Play
- Running: Pause + Stop
- Paused: Resume + Stop

---

## React Hooks

### useProjects.ts (React Query)

**Queries:**
```typescript
useProjects()           // List all projects
useProject(name)        // Single project details
useFeatures(name)       // Features (refetch 5s)
useAgentStatus(name)    // Agent status (refetch 3s)
useSetupStatus()        // System requirements
useListDirectory(path)  // Filesystem listing
```

**Mutations:**
```typescript
useCreateProject()
useDeleteProject()
useCreateFeature(name)
useDeleteFeature()
useSkipFeature()
useStartAgent()
useStopAgent()
usePauseAgent()
useResumeAgent()
```

### useProjectWebSocket.ts

**Returns:**
```typescript
{
  progress: { passing, in_progress, total, percentage }
  agentStatus: AgentStatus
  logs: Array<{ line, timestamp }>
  isConnected: boolean
  clearLogs(): void
}
```

**Message Types:** progress, feature_update, log, agent_status

### useAssistantChat.ts

**Returns:**
```typescript
{
  messages: ChatMessage[]
  isLoading: boolean
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error'
  start: (conversationId?) => void
  sendMessage: (content) => void
  disconnect: () => void
}
```

### useSpecChat.ts

**Returns:**
```typescript
{
  messages: ChatMessage[]
  isLoading: boolean
  isComplete: boolean
  currentQuestions: SpecQuestion[] | null
  start: () => void
  sendMessage: (content, attachments?) => void
  sendAnswer: (answers) => void
}
```

---

## API Client (lib/api.ts)

```typescript
// Projects
listProjects(): Promise<ProjectSummary[]>
createProject(name, path, specMethod?): Promise<ProjectSummary>
getProject(name): Promise<ProjectDetail>
deleteProject(name): Promise<void>

// Features
listFeatures(projectName): Promise<FeatureListResponse>
createFeature(projectName, feature): Promise<Feature>
deleteFeature(projectName, featureId): Promise<void>
skipFeature(projectName, featureId): Promise<void>

// Agent
getAgentStatus(projectName): Promise<AgentStatusResponse>
startAgent(projectName, yoloMode?): Promise<AgentActionResponse>
stopAgent(projectName): Promise<AgentActionResponse>

// Filesystem
listDirectory(path?): Promise<DirectoryListResponse>
validatePath(path): Promise<PathValidationResponse>
createDirectory(fullPath): Promise<{ success, path }>
```

---

## TypeScript Types (lib/types.ts)

```typescript
interface Feature {
  id: number
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
}

interface FeatureListResponse {
  pending: Feature[]
  in_progress: Feature[]
  done: Feature[]
}

type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  attachments?: ImageAttachment[]
  timestamp: Date
  isStreaming?: boolean
}
```

---

## Design System (globals.css)

### Colors
```css
--color-neo-bg: #fffef5;        /* Off-white background */
--color-neo-pending: #ffd60a;   /* Yellow */
--color-neo-progress: #00b4d8;  /* Cyan */
--color-neo-done: #70e000;      /* Green */
--color-neo-accent: #ff006e;    /* Magenta */
--color-neo-danger: #ff5400;    /* Orange-red */
--color-neo-border: #1a1a1a;    /* Black */
```

### Typography
```css
--font-neo-display: 'Space Grotesk';  /* Bold titles */
--font-neo-sans: 'DM Sans';           /* Body text */
--font-neo-mono: 'JetBrains Mono';    /* Code */
```

### Shadows (Hard Offset)
```css
--shadow-neo-sm: 2px 2px 0px rgba(0,0,0,1);
--shadow-neo-md: 4px 4px 0px rgba(0,0,0,1);
--shadow-neo-lg: 6px 6px 0px rgba(0,0,0,1);
```

### Component Classes
```css
.neo-card      /* Cards with borders and hover */
.neo-btn       /* Base button */
.neo-btn-primary, .neo-btn-success, .neo-btn-warning, .neo-btn-danger
.neo-input     /* Form inputs */
.neo-badge     /* Status badges */
.neo-modal     /* Modal dialogs */
```

### Animations
```css
@keyframes popIn { /* Scale pop */ }
@keyframes slideIn { /* Left slide */ }
@keyframes neoPulse { /* Cyan pulse */ }
@keyframes shimmer { /* Text shimmer */ }
```

---

## Adding New Features

### New Component
```typescript
interface MyComponentProps {
  data: SomeType
  onAction: () => void
}

export function MyComponent({ data, onAction }: MyComponentProps) {
  return (
    <div className="neo-card p-4">
      <button onClick={onAction} className="neo-btn neo-btn-primary">
        Action
      </button>
    </div>
  )
}
```

### New Hook (React Query)
```typescript
export function useMyData(id: string) {
  return useQuery({
    queryKey: ['mydata', id],
    queryFn: () => api.getMyData(id),
    enabled: !!id,
  })
}

export function useMyMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.updateMyData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mydata'] })
    },
  })
}
```

---

## Integration Point: Import Existing Project

To add "Import Existing" option in NewProjectModal:

1. Add new step type: `'import'`
2. Add button in method selection step
3. Create validation for existing project structure
4. Call new `importProject()` API function
5. Navigate to project on success
