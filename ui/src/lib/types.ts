/**
 * TypeScript types for the Autonomous Coding UI
 */

// Project types
export interface ProjectStats {
  passing: number
  in_progress: number
  total: number
  percentage: number
}

export interface ProjectSummary {
  name: string
  path: string
  has_spec: boolean
  stats: ProjectStats
  default_concurrency: number
}

export interface ProjectDetail extends ProjectSummary {
  prompts_dir: string
}

// Filesystem types
export interface DriveInfo {
  letter: string
  label: string
  available?: boolean
}

export interface DirectoryEntry {
  name: string
  path: string
  is_directory: boolean
  has_children: boolean
}

export interface DirectoryListResponse {
  current_path: string
  parent_path: string | null
  entries: DirectoryEntry[]
  drives: DriveInfo[] | null
}

export interface PathValidationResponse {
  valid: boolean
  exists: boolean
  is_directory: boolean
  can_write: boolean
  message: string
}

export interface ProjectPrompts {
  app_spec: string
  initializer_prompt: string
  coding_prompt: string
}

// Human input types
export interface HumanInputField {
  id: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'boolean'
  required: boolean
  placeholder?: string
  options?: { value: string; label: string }[]
}

export interface HumanInputRequest {
  prompt: string
  fields: HumanInputField[]
}

export interface HumanInputResponseData {
  fields: Record<string, string | boolean | string[]>
  responded_at?: string
}

// Feature types
export interface Feature {
  id: number
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
  dependencies?: number[]           // Optional for backwards compat
  blocked?: boolean                 // Computed by API
  blocking_dependencies?: number[]  // Computed by API
  needs_human_input?: boolean
  human_input_request?: HumanInputRequest | null
  human_input_response?: HumanInputResponseData | null
}

// Status type for graph nodes
export type FeatureStatus = 'pending' | 'in_progress' | 'done' | 'blocked' | 'needs_human_input'

// Graph visualization types
export interface GraphNode {
  id: number
  name: string
  category: string
  status: FeatureStatus
  priority: number
  dependencies: number[]
}

export interface GraphEdge {
  source: number
  target: number
}

export interface DependencyGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface FeatureListResponse {
  pending: Feature[]
  in_progress: Feature[]
  done: Feature[]
  needs_human_input: Feature[]
}

export interface FeatureCreate {
  category: string
  name: string
  description: string
  steps: string[]
  priority?: number
  dependencies?: number[]
}

export interface FeatureUpdate {
  category?: string
  name?: string
  description?: string
  steps?: string[]
  priority?: number
  dependencies?: number[]
}

// Agent types
export type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed' | 'loading' | 'pausing' | 'paused_graceful'

export interface AgentStatusResponse {
  status: AgentStatus
  pid: number | null
  started_at: string | null
  yolo_mode: boolean
  model: string | null  // Model being used by running agent
  parallel_mode: boolean  // DEPRECATED: Always true now (unified orchestrator)
  max_concurrency: number | null
  testing_agent_ratio: number  // Regression testing agents (0-3)
}

export interface AgentActionResponse {
  success: boolean
  status: AgentStatus
  message: string
}

// Setup types
export interface SetupStatus {
  claude_cli: boolean
  credentials: boolean
  node: boolean
  npm: boolean
}

// Dev Server types
export type DevServerStatus = 'stopped' | 'running' | 'crashed'

export interface DevServerStatusResponse {
  status: DevServerStatus
  pid: number | null
  url: string | null
  command: string | null
  started_at: string | null
}

export interface DevServerConfig {
  detected_type: string | null
  detected_command: string | null
  custom_command: string | null
  effective_command: string | null
}

// Terminal types
export interface TerminalInfo {
  id: string
  name: string
  created_at: string
}

// Agent mascot names for multi-agent UI
export const AGENT_MASCOTS = [
  'Spark', 'Fizz', 'Octo', 'Hoot', 'Buzz',    // Original 5
  'Pixel', 'Byte', 'Nova', 'Chip', 'Bolt',    // Tech-inspired
  'Dash', 'Zap', 'Gizmo', 'Turbo', 'Blip',    // Energetic
  'Neon', 'Widget', 'Zippy', 'Quirk', 'Flux', // Playful
] as const
export type AgentMascot = typeof AGENT_MASCOTS[number]

// Agent state for Mission Control
export type AgentState = 'idle' | 'thinking' | 'working' | 'testing' | 'success' | 'error' | 'struggling'

// Agent type (coding vs testing)
export type AgentType = 'coding' | 'testing'

// Individual log entry for an agent
export interface AgentLogEntry {
  line: string
  timestamp: string
  type: 'output' | 'state_change' | 'error'
}

// Agent update from backend
export interface ActiveAgent {
  agentIndex: number  // -1 for synthetic completions
  agentName: AgentMascot | 'Unknown'
  agentType: AgentType  // "coding" or "testing"
  featureId: number        // Current/primary feature (backward compat)
  featureIds: number[]     // All features in batch
  featureName: string
  state: AgentState
  thought?: string
  timestamp: string
  logs?: AgentLogEntry[]  // Per-agent log history
}

// Orchestrator state for Mission Control
export type OrchestratorState =
  | 'idle'
  | 'initializing'
  | 'scheduling'
  | 'spawning'
  | 'monitoring'
  | 'complete'
  | 'draining'
  | 'paused'

// Orchestrator event for recent activity
export interface OrchestratorEvent {
  eventType: string
  message: string
  timestamp: string
  featureId?: number
  featureName?: string
}

// Orchestrator status for Mission Control
export interface OrchestratorStatus {
  state: OrchestratorState
  message: string
  codingAgents: number
  testingAgents: number
  maxConcurrency: number
  readyCount: number
  blockedCount: number
  timestamp: string
  recentEvents: OrchestratorEvent[]
}

// WebSocket message types
export type WSMessageType = 'progress' | 'feature_update' | 'log' | 'agent_status' | 'pong' | 'dev_log' | 'dev_server_status' | 'agent_update' | 'orchestrator_update'

export interface WSProgressMessage {
  type: 'progress'
  passing: number
  in_progress: number
  total: number
  percentage: number
  needs_human_input?: number
}

export interface WSFeatureUpdateMessage {
  type: 'feature_update'
  feature_id: number
  passes: boolean
}

export interface WSLogMessage {
  type: 'log'
  line: string
  timestamp: string
  featureId?: number
  agentIndex?: number
  agentName?: AgentMascot
}

export interface WSAgentUpdateMessage {
  type: 'agent_update'
  agentIndex: number  // -1 for synthetic completions (untracked agents)
  agentName: AgentMascot | 'Unknown'
  agentType: AgentType  // "coding" or "testing"
  featureId: number
  featureIds?: number[]  // All features in batch (may be absent for backward compat)
  featureName: string
  state: AgentState
  thought?: string
  timestamp: string
  synthetic?: boolean  // True for synthetic completions from untracked agents
}

export interface WSAgentStatusMessage {
  type: 'agent_status'
  status: AgentStatus
}

export interface WSPongMessage {
  type: 'pong'
}

export interface WSDevLogMessage {
  type: 'dev_log'
  line: string
  timestamp: string
}

export interface WSDevServerStatusMessage {
  type: 'dev_server_status'
  status: DevServerStatus
  url: string | null
}

export interface WSOrchestratorUpdateMessage {
  type: 'orchestrator_update'
  eventType: string
  state: OrchestratorState
  message: string
  timestamp: string
  codingAgents?: number
  testingAgents?: number
  maxConcurrency?: number
  readyCount?: number
  blockedCount?: number
  featureId?: number
  featureName?: string
}

export type WSMessage =
  | WSProgressMessage
  | WSFeatureUpdateMessage
  | WSLogMessage
  | WSAgentStatusMessage
  | WSAgentUpdateMessage
  | WSPongMessage
  | WSDevLogMessage
  | WSDevServerStatusMessage
  | WSOrchestratorUpdateMessage

// ============================================================================
// Spec Chat Types
// ============================================================================

export interface SpecQuestionOption {
  label: string
  description: string
}

export interface SpecQuestion {
  question: string
  header: string
  options: SpecQuestionOption[]
  multiSelect: boolean
}

export interface SpecChatTextMessage {
  type: 'text'
  content: string
}

export interface SpecChatQuestionMessage {
  type: 'question'
  questions: SpecQuestion[]
  tool_id?: string
}

export interface SpecChatCompleteMessage {
  type: 'spec_complete'
  path: string
}

export interface SpecChatFileWrittenMessage {
  type: 'file_written'
  path: string
}

export interface SpecChatSessionCompleteMessage {
  type: 'complete'
}

export interface SpecChatErrorMessage {
  type: 'error'
  content: string
}

export interface SpecChatPongMessage {
  type: 'pong'
}

export interface SpecChatResponseDoneMessage {
  type: 'response_done'
}

export type SpecChatServerMessage =
  | SpecChatTextMessage
  | SpecChatQuestionMessage
  | SpecChatCompleteMessage
  | SpecChatFileWrittenMessage
  | SpecChatSessionCompleteMessage
  | SpecChatErrorMessage
  | SpecChatPongMessage
  | SpecChatResponseDoneMessage

// Image attachment for chat messages
export interface ImageAttachment {
  id: string
  filename: string
  mimeType: 'image/jpeg' | 'image/png'
  base64Data: string    // Raw base64 (without data: prefix)
  previewUrl: string    // data: URL for display
  size: number          // File size in bytes
}

// UI chat message for display
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  attachments?: ImageAttachment[]
  timestamp: Date
  questions?: SpecQuestion[]
  isStreaming?: boolean
}

// ============================================================================
// Assistant Chat Types
// ============================================================================

export interface AssistantConversation {
  id: number
  project_name: string
  title: string | null
  created_at: string | null
  updated_at: string | null
  message_count: number
}

export interface AssistantMessage {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string | null
}

export interface AssistantConversationDetail {
  id: number
  project_name: string
  title: string | null
  created_at: string | null
  updated_at: string | null
  messages: AssistantMessage[]
}

export interface AssistantChatTextMessage {
  type: 'text'
  content: string
}

export interface AssistantChatToolCallMessage {
  type: 'tool_call'
  tool: string
  input: Record<string, unknown>
}

export interface AssistantChatResponseDoneMessage {
  type: 'response_done'
}

export interface AssistantChatErrorMessage {
  type: 'error'
  content: string
}

export interface AssistantChatConversationCreatedMessage {
  type: 'conversation_created'
  conversation_id: number
}

export interface AssistantChatQuestionMessage {
  type: 'question'
  questions: SpecQuestion[]
}

export interface AssistantChatPongMessage {
  type: 'pong'
}

export type AssistantChatServerMessage =
  | AssistantChatTextMessage
  | AssistantChatToolCallMessage
  | AssistantChatQuestionMessage
  | AssistantChatResponseDoneMessage
  | AssistantChatErrorMessage
  | AssistantChatConversationCreatedMessage
  | AssistantChatPongMessage

// ============================================================================
// Expand Chat Types
// ============================================================================

export interface ExpandChatFeaturesCreatedMessage {
  type: 'features_created'
  count: number
  features: { id: number; name: string; category: string }[]
}

export interface ExpandChatCompleteMessage {
  type: 'expansion_complete'
  total_added: number
}

export type ExpandChatServerMessage =
  | SpecChatTextMessage        // Reuse text message type
  | ExpandChatFeaturesCreatedMessage
  | ExpandChatCompleteMessage
  | SpecChatErrorMessage       // Reuse error message type
  | SpecChatPongMessage        // Reuse pong message type
  | SpecChatResponseDoneMessage // Reuse response_done type

// Bulk feature creation
export interface FeatureBulkCreate {
  features: FeatureCreate[]
  starting_priority?: number
}

export interface FeatureBulkCreateResponse {
  created: number
  features: Feature[]
}

// ============================================================================
// Settings Types
// ============================================================================

export interface ModelInfo {
  id: string
  name: string
}

export interface ModelsResponse {
  models: ModelInfo[]
  default: string
}

export interface ProviderInfo {
  id: string
  name: string
  base_url: string | null
  models: ModelInfo[]
  default_model: string
  requires_auth: boolean
}

export interface ProvidersResponse {
  providers: ProviderInfo[]
  current: string
}

export interface Settings {
  yolo_mode: boolean
  model: string
  glm_mode: boolean
  ollama_mode: boolean
  testing_agent_ratio: number  // Regression testing agents (0-3)
  playwright_headless: boolean
  batch_size: number  // Features per coding agent batch (1-3)
  agent_session_logging: boolean  // Persist agent output to SQLite
  api_provider: string
  api_base_url: string | null
  api_has_auth_token: boolean
  api_model: string | null
}

export interface SettingsUpdate {
  yolo_mode?: boolean
  model?: string
  testing_agent_ratio?: number
  playwright_headless?: boolean
  batch_size?: number
  agent_session_logging?: boolean
  api_provider?: string
  api_base_url?: string
  api_auth_token?: string
  api_model?: string
}

export interface ProjectSettingsUpdate {
  default_concurrency?: number
}

// ============================================================================
// Schedule Types
// ============================================================================

export interface Schedule {
  id: number
  project_name: string
  start_time: string      // "HH:MM" in UTC
  duration_minutes: number
  days_of_week: number    // Bitfield: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64
  enabled: boolean
  yolo_mode: boolean
  model: string | null
  max_concurrency: number // 1-5 concurrent agents
  crash_count: number
  created_at: string
}

export interface ScheduleCreate {
  start_time: string      // "HH:MM" format (local time, will be stored as UTC)
  duration_minutes: number
  days_of_week: number
  enabled: boolean
  yolo_mode: boolean
  model: string | null
  max_concurrency: number // 1-5 concurrent agents
}

export interface ScheduleUpdate {
  start_time?: string
  duration_minutes?: number
  days_of_week?: number
  enabled?: boolean
  yolo_mode?: boolean
  model?: string | null
  max_concurrency?: number
}

export interface ScheduleListResponse {
  schedules: Schedule[]
}

export interface NextRunResponse {
  has_schedules: boolean
  next_start: string | null  // ISO datetime in UTC
  next_end: string | null    // ISO datetime in UTC (latest end if overlapping)
  is_currently_running: boolean
  active_schedule_count: number
}
