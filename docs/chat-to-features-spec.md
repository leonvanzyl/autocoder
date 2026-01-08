# Chat-to-Features Sidebar Specification

## Overview

A conversational sidebar integrated into the Kanban UI that allows users to describe features in natural language and have Claude generate structured feature definitions automatically.

## Problem Statement

Currently, users must manually fill out the "Add Feature" form with:
- Category
- Priority
- Feature Name
- Description
- Test Steps

This is tedious and requires the user to think about structure rather than functionality.

## Solution

A chat interface where:
1. User describes what they want in natural language
2. Claude reads project context (app_spec, context files, existing features)
3. Claude generates structured feature suggestions
4. User approves/rejects each suggestion
5. Approved features are created in the database and appear in Kanban

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  User: "Voglio aggiungere autenticazione OAuth"                     │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │     WebSocket: chat_to_features.py      │                        │
│  │     Endpoint: /ws/chat/{project_name}   │                        │
│  └─────────────────────────────────────────┘                        │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │   ChatToFeaturesSession                 │                        │
│  │   - Loads project context               │                        │
│  │   - Streams Claude response             │                        │
│  │   - Parses feature suggestions          │                        │
│  └─────────────────────────────────────────┘                        │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │   Feature Suggestion Response           │                        │
│  │   {                                     │                        │
│  │     type: "feature_suggestion",         │                        │
│  │     feature: {                          │                        │
│  │       name: "OAuth Google Login",       │                        │
│  │       category: "Authentication",       │                        │
│  │       description: "...",               │                        │
│  │       steps: ["...", "..."],            │                        │
│  │       reasoning: "..."                  │                        │
│  │     }                                   │                        │
│  │   }                                     │                        │
│  └─────────────────────────────────────────┘                        │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │   Frontend: FeatureSuggestionCard       │                        │
│  │   [✓ Create Feature] [✗ Dismiss]        │                        │
│  └─────────────────────────────────────────┘                        │
│                           │                                          │
│                           ▼ (on accept)                              │
│  ┌─────────────────────────────────────────┐                        │
│  │   REST API: POST /projects/{name}/features                       │
│  │   → Feature saved to database           │                        │
│  │   → Appears in Kanban PENDING column    │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### File Structure

```
server/
├── routers/
│   └── chat_to_features.py          # WebSocket endpoint
├── services/
│   └── chat_to_features_session.py  # Session management with Claude SDK

ui/src/
├── hooks/
│   └── useChatToFeatures.ts         # WebSocket hook
├── components/
│   ├── ChatToFeaturesPanel.tsx      # Sidebar container
│   ├── ChatToFeaturesChat.tsx       # Chat UI
│   └── FeatureSuggestionCard.tsx    # Feature preview card
```

## Backend Implementation

### WebSocket Router: `chat_to_features.py`

**Endpoint:** `ws://localhost:8000/ws/chat/{project_name}`

**Message Protocol:**

Client → Server:
```json
{"type": "start"}
{"type": "message", "content": "User message here"}
{"type": "accept_feature", "feature_index": 0}
{"type": "reject_feature", "feature_index": 0}
{"type": "ping"}
```

Server → Client:
```json
{"type": "text", "content": "Streaming text..."}
{"type": "feature_suggestion", "index": 0, "feature": {...}}
{"type": "feature_created", "feature_id": 123, "feature": {...}}
{"type": "response_done"}
{"type": "error", "content": "Error message"}
{"type": "pong"}
```

**Dependencies:**
- `server/services/chat_to_features_session.py` - Session management
- `server/routers/features.py` - Feature creation API (reuse existing)
- `registry.py` - Project path resolution

### Session Service: `chat_to_features_session.py`

**Class:** `ChatToFeaturesSession`

**Responsibilities:**
1. Initialize Claude SDK client with appropriate system prompt
2. Load project context (app_spec.txt, context files, existing features)
3. Stream responses from Claude
4. Parse feature suggestions from Claude's output
5. Track conversation history

**Context Loading:**
```python
async def _load_context(self) -> str:
    context_parts = []

    # 1. Load app_spec.txt if exists
    spec_path = self.project_dir / "prompts" / "app_spec.txt"
    if spec_path.exists():
        context_parts.append(f"## App Specification\n{spec_path.read_text()}")

    # 2. Load context files from analyzer
    context_dir = self.project_dir / "prompts" / "context"
    if context_dir.exists():
        for md_file in sorted(context_dir.glob("*.md")):
            content = md_file.read_text()
            context_parts.append(f"## {md_file.stem}\n{content}")

    # 3. Load existing features summary
    features = self._get_existing_features()
    if features:
        context_parts.append(self._format_features_summary(features))

    return "\n\n".join(context_parts)
```

**System Prompt Template:**
```markdown
You are a feature suggestion assistant for a software project.

# Your Role
Help the user expand their project by suggesting well-designed features that fit the existing architecture.

# Project Context
{context}

# Current Features ({feature_count} total)
{features_by_category}

# How to Suggest Features
When you identify a good feature, output it in this EXACT format:

---FEATURE_START---
NAME: [Brief 5-10 word feature name]
CATEGORY: [Use existing category or create new one]
DESCRIPTION: [2-3 sentences explaining what this feature does and why it's valuable]
STEPS:
1. [Verification step 1]
2. [Verification step 2]
3. [Verification step 3]
REASONING: [Why this feature makes sense for this project]
---FEATURE_END---

# Guidelines
- Suggest features that complement existing functionality
- Break large requests into multiple focused features
- Use consistent category names
- Write clear, testable verification steps
- Explain your reasoning to help the user decide
```

**Feature Parsing:**
```python
FEATURE_PATTERN = re.compile(
    r'---FEATURE_START---\s*'
    r'NAME:\s*(.+?)\s*'
    r'CATEGORY:\s*(.+?)\s*'
    r'DESCRIPTION:\s*(.+?)\s*'
    r'STEPS:\s*(.+?)\s*'
    r'REASONING:\s*(.+?)\s*'
    r'---FEATURE_END---',
    re.DOTALL
)

def parse_feature_suggestions(self, text: str) -> list[dict]:
    """Extract feature suggestions from Claude's response."""
    features = []
    for match in FEATURE_PATTERN.finditer(text):
        steps = self._parse_numbered_list(match.group(4))
        features.append({
            "name": match.group(1).strip(),
            "category": match.group(2).strip(),
            "description": match.group(3).strip(),
            "steps": steps,
            "reasoning": match.group(5).strip()
        })
    return features
```

## Frontend Implementation

### Hook: `useChatToFeatures.ts`

**Interface:**
```typescript
interface FeatureSuggestion {
  index: number
  name: string
  category: string
  description: string
  steps: string[]
  reasoning: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  suggestions?: FeatureSuggestion[]
}

interface UseChatToFeaturesOptions {
  projectName: string
  onFeatureCreated?: (feature: Feature) => void
  onError?: (error: string) => void
}

interface UseChatToFeaturesReturn {
  // State
  messages: ChatMessage[]
  isLoading: boolean
  isConnected: boolean
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error'
  pendingSuggestions: FeatureSuggestion[]

  // Actions
  connect: () => void
  disconnect: () => void
  sendMessage: (content: string) => void
  acceptFeature: (index: number) => Promise<void>
  rejectFeature: (index: number) => void
  clearHistory: () => void
}
```

**Key Implementation Details:**
- WebSocket connection to `/ws/chat/{projectName}`
- Automatic reconnection with exponential backoff (max 3 attempts)
- Ping/pong keep-alive every 30 seconds
- Parse `feature_suggestion` messages into structured data
- Track pending suggestions separately from messages
- Call REST API to create features on accept

### Component: `ChatToFeaturesPanel.tsx`

**Props:**
```typescript
interface ChatToFeaturesPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
  onFeatureCreated?: (feature: Feature) => void
}
```

**Layout:**
- Slide-in panel from LEFT side (300-400px width)
- Fixed position, full height
- Header with title and close button
- Scrollable message area
- Fixed input area at bottom
- Backdrop overlay when open (optional, clickable to close)

**Styling:**
- Use neobrutalism design system
- Border: 3px solid black
- Shadow: 4px 4px 0px black
- Colors: `--color-neo-bg`, `--color-neo-border`

### Component: `ChatToFeaturesChat.tsx`

**Structure:**
```tsx
<div className="chat-container">
  {/* Messages */}
  <div className="messages-area">
    {messages.map(msg => (
      <ChatMessage key={msg.id} message={msg} />
    ))}
    {isLoading && <LoadingIndicator />}
  </div>

  {/* Pending Suggestions */}
  {pendingSuggestions.length > 0 && (
    <div className="suggestions-area">
      <h4>Suggested Features</h4>
      {pendingSuggestions.map(suggestion => (
        <FeatureSuggestionCard
          key={suggestion.index}
          suggestion={suggestion}
          onAccept={() => acceptFeature(suggestion.index)}
          onReject={() => rejectFeature(suggestion.index)}
        />
      ))}
    </div>
  )}

  {/* Input */}
  <div className="input-area">
    <textarea
      value={input}
      onChange={e => setInput(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="Describe the features you want..."
    />
    <button onClick={handleSend} disabled={isLoading}>
      Send
    </button>
  </div>
</div>
```

### Component: `FeatureSuggestionCard.tsx`

**Props:**
```typescript
interface FeatureSuggestionCardProps {
  suggestion: FeatureSuggestion
  onAccept: () => void
  onReject: () => void
  isCreating?: boolean
}
```

**Layout:**
```
┌─────────────────────────────────────┐
│ 🏷️ SUGGESTION          [Category]  │
├─────────────────────────────────────┤
│ Feature Name Here                   │
│                                     │
│ Description text that explains      │
│ what this feature does...           │
│                                     │
│ Steps:                              │
│ 1. First verification step          │
│ 2. Second verification step         │
│ 3. Third verification step          │
│                                     │
│ 💡 Reasoning: Why this makes sense  │
│                                     │
│ [✓ Create Feature] [✗ Dismiss]      │
└─────────────────────────────────────┘
```

**Styling:**
- Yellow/orange background for "suggestion" state
- Category badge with appropriate color
- Steps as numbered list
- Reasoning in italic or different style
- Buttons: primary green for Accept, secondary for Reject

## Integration

### App.tsx Changes

```tsx
// Add state
const [chatToFeaturesOpen, setChatToFeaturesOpen] = useState(false)

// Add keyboard shortcut in useEffect
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl/Cmd + F to toggle chat
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault()
      setChatToFeaturesOpen(prev => !prev)
    }
  }
  window.addEventListener('keydown', handleKeyDown)
  return () => window.removeEventListener('keydown', handleKeyDown)
}, [])

// Add toggle button in header
<button
  onClick={() => setChatToFeaturesOpen(!chatToFeaturesOpen)}
  className="neo-btn"
  title="Feature Suggestions (Ctrl+F)"
>
  💬 Suggest Features
</button>

// Render panel
<ChatToFeaturesPanel
  projectName={selectedProject}
  isOpen={chatToFeaturesOpen}
  onClose={() => setChatToFeaturesOpen(false)}
  onFeatureCreated={(feature) => {
    // Trigger Kanban refresh
    queryClient.invalidateQueries(['features', selectedProject])
  }}
/>
```

### server/main.py Changes

```python
from server.routers import chat_to_features

# Add router
app.include_router(
    chat_to_features.router,
    prefix="/api/projects",
    tags=["chat"]
)
```

## Error Handling

### Backend Errors
- Invalid project name → 404 WebSocket close
- Project not found in registry → Error message in WebSocket
- Claude SDK errors → Error message, offer retry
- Feature creation failure → Error message with details

### Frontend Errors
- WebSocket connection failure → Show reconnecting state, max 3 retries
- Message send failure → Show error, allow retry
- Feature creation failure → Show error on suggestion card

## Testing Scenarios

1. **Basic Flow**
   - Open sidebar
   - Type "Add user login"
   - Verify suggestion appears
   - Click accept
   - Verify feature in Kanban

2. **Multiple Suggestions**
   - Request "Add authentication system"
   - Verify multiple suggestions
   - Accept some, reject others
   - Verify correct features created

3. **Context Awareness**
   - Import project with existing features
   - Request related feature
   - Verify suggestion references existing architecture

4. **Error Recovery**
   - Disconnect network during chat
   - Verify reconnection
   - Verify message history preserved

## Future Enhancements

1. **Bulk Accept** - Accept all suggestions at once
2. **Edit Before Accept** - Modify suggestion before creating
3. **Feature Templates** - Common feature patterns
4. **Voice Input** - Speech-to-text for feature requests
5. **History Persistence** - Save chat history per project
