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
  setup_required?: boolean
  stats: ProjectStats
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

// Knowledge files
export interface KnowledgeFileSummary {
  name: string
  size_bytes: number
  modified_at: string
}

export interface KnowledgeFilesResponse {
  directory: string
  files: KnowledgeFileSummary[]
}

export interface KnowledgeFile {
  name: string
  content: string
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
  status?: string
  enabled?: boolean
  staged?: boolean
  attempts?: number
  last_error?: string | null
  last_artifact_path?: string | null
  depends_on?: number[]
  ready?: boolean
  waiting_on?: number[]
}

export interface FeatureListResponse {
  staged: Feature[]
  pending: Feature[]
  in_progress: Feature[]
  done: Feature[]
}

export interface FeatureCreate {
  category: string
  name: string
  description: string
  steps: string[]
  priority?: number
}

// Agent types
export type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed'

export interface AgentStatusResponse {
  status: AgentStatus
  pid: number | null
  started_at: string | null
  yolo_mode: boolean
  parallel_mode: boolean
  parallel_count: number | null
  model_preset: string | null
}

export interface AgentActionResponse {
  success: boolean
  status: AgentStatus
  message: string
}

export interface AgentStartRequest {
  yolo_mode?: boolean
  parallel_mode?: boolean
  parallel_count?: number
  model_preset?: 'quality' | 'balanced' | 'economy' | 'cheap' | 'experimental' | 'custom'
}

// Setup types
export interface SetupStatus {
  claude_cli: boolean
  credentials: boolean
  node: boolean
  npm: boolean
  codex_cli?: boolean
  gemini_cli?: boolean
  env_auth?: boolean
  custom_api?: boolean
  glm_mode?: boolean
}

// Worker logs (parallel agents)
export interface WorkerLogFile {
  name: string
  size_bytes: number
  modified_at: string
}

export interface WorkerLogsListResponse {
  directory: string
  files: WorkerLogFile[]
}

export interface WorkerLogTailResponse {
  name: string
  size_bytes: number
  modified_at: string
  lines: string[]
}

export interface PruneWorkerLogsRequest {
  keep_days: number
  keep_files: number
  max_mb: number
  dry_run: boolean
  include_artifacts?: boolean
}

export interface PruneWorkerLogsResponse {
  deleted_files: number
  deleted_bytes: number
  kept_files: number
  kept_bytes: number
}

// Advanced settings (UI server)
export type ReviewMode = 'off' | 'advisory' | 'gate'
export type ReviewType = 'none' | 'command' | 'claude' | 'multi_cli'
export type WorkerProvider = 'claude' | 'codex_cli' | 'gemini_cli' | 'multi_cli'
export type PlannerSynthesizer = 'none' | 'claude' | 'codex' | 'gemini'
export type ReviewConsensus = 'any' | 'majority' | 'all'
export type CodexReasoningEffort = 'low' | 'medium' | 'high'
export type InitializerProvider = 'claude' | 'codex_cli' | 'gemini_cli' | 'multi_cli'
export type InitializerSynthesizer = 'none' | 'claude' | 'codex' | 'gemini'

export interface AdvancedSettings {
  review_enabled: boolean
  review_mode: ReviewMode
  review_type: ReviewType
  review_command: string
  review_timeout_s: number
  review_model: string
  review_agents: string
  review_consensus: string
  codex_model: string
  codex_reasoning_effort: string
  gemini_model: string

  locks_enabled: boolean
  worker_verify: boolean
  worker_provider: WorkerProvider
  worker_patch_max_iterations: number
  worker_patch_agents: string

  qa_fix_enabled: boolean
  qa_model: string
  qa_max_sessions: number
  qa_subagent_enabled: boolean
  qa_subagent_max_iterations: number
  qa_subagent_provider: WorkerProvider
  qa_subagent_agents: string

  controller_enabled: boolean
  controller_model: string
  controller_max_sessions: number

  planner_enabled: boolean
  planner_model: string
  planner_agents: string
  planner_synthesizer: PlannerSynthesizer
  planner_timeout_s: number

  initializer_provider: InitializerProvider
  initializer_agents: string
  initializer_synthesizer: InitializerSynthesizer
  initializer_timeout_s: number
  initializer_stage_threshold: number
  initializer_enqueue_count: number

  logs_keep_days: number
  logs_keep_files: number
  logs_max_total_mb: number
  logs_prune_artifacts: boolean

  diagnostics_fixtures_dir: string

  sdk_max_attempts: number
  sdk_initial_delay_s: number
  sdk_rate_limit_initial_delay_s: number
  sdk_max_delay_s: number
  sdk_exponential_base: number
  sdk_jitter: boolean

  require_gatekeeper: boolean
  allow_no_tests: boolean

  api_port_range_start: number
  api_port_range_end: number
  web_port_range_start: number
  web_port_range_end: number
  skip_port_check: boolean
}

// ============================================================================
// Dev Server Types
// ============================================================================

export type DevServerStatus = 'stopped' | 'running' | 'crashed'

export interface DevServerStatusResponse {
  status: DevServerStatus
  pid: number | null
  started_at: string | null
  command: string | null
  url: string | null
  api_port: number | null
  web_port: number | null
}

export interface DevServerStartRequest {
  command?: string | null
  api_port?: number | null
  web_port?: number | null
}

export interface DevServerActionResponse {
  success: boolean
  status: DevServerStatus
  message: string
  url?: string | null
}

export interface DevServerWSStatusMessage {
  type: 'devserver_status'
  status: DevServerStatus
  pid: number | null
  started_at: string | null
  command: string | null
  url: string | null
  api_port: number | null
  web_port: number | null
}

export interface DevServerWSLogMessage {
  type: 'devserver_log'
  line: string
  timestamp: string
}

export type DevServerWSMessage = DevServerWSStatusMessage | DevServerWSLogMessage

// ============================================================================
// Terminal Types
// ============================================================================

export interface TerminalInfo {
  id: string
  name: string
  created_at: string
}

// WebSocket message types
export type WSMessageType = 'progress' | 'feature_update' | 'log' | 'agent_status' | 'pong'

export interface WSProgressMessage {
  type: 'progress'
  passing: number
  in_progress: number
  total: number
  percentage: number
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
}

export interface WSAgentStatusMessage {
  type: 'agent_status'
  status: AgentStatus
}

export interface WSPongMessage {
  type: 'pong'
}

export type WSMessage =
  | WSProgressMessage
  | WSFeatureUpdateMessage
  | WSLogMessage
  | WSAgentStatusMessage
  | WSPongMessage

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

// ============================================================================
// Expand Project Chat Types
// ============================================================================

export interface ExpandChatTextMessage {
  type: 'text'
  content: string
}

export interface ExpandChatCreatedFeature {
  id: number
  name: string
  category: string
}

export interface ExpandChatFeaturesCreatedMessage {
  type: 'features_created'
  count: number
  features: ExpandChatCreatedFeature[]
}

export interface ExpandChatCompleteMessage {
  type: 'expansion_complete'
  total_added: number
}

export interface ExpandChatErrorMessage {
  type: 'error'
  content: string
}

export interface ExpandChatPongMessage {
  type: 'pong'
}

export interface ExpandChatResponseDoneMessage {
  type: 'response_done'
}

export type ExpandChatServerMessage =
  | ExpandChatTextMessage
  | ExpandChatFeaturesCreatedMessage
  | ExpandChatCompleteMessage
  | ExpandChatErrorMessage
  | ExpandChatPongMessage
  | ExpandChatResponseDoneMessage

export interface ExpandChatStartMessage {
  type: 'start'
}

export interface ExpandChatUserMessage {
  type: 'message'
  content: string
  attachments?: ImageAttachment[]
}

export interface ExpandChatDoneMessage {
  type: 'done'
}

export interface ExpandChatPingMessage {
  type: 'ping'
}

export type ExpandChatClientMessage =
  | ExpandChatStartMessage
  | ExpandChatUserMessage
  | ExpandChatDoneMessage
  | ExpandChatPingMessage

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

export interface AssistantChatPongMessage {
  type: 'pong'
}

export type AssistantChatServerMessage =
  | AssistantChatTextMessage
  | AssistantChatToolCallMessage
  | AssistantChatResponseDoneMessage
  | AssistantChatErrorMessage
  | AssistantChatConversationCreatedMessage
  | AssistantChatPongMessage

// Client message types (sent to server)
export interface AssistantChatStartMessage {
  type: 'start'
  conversation_id?: number
}

export interface AssistantChatUserMessage {
  type: 'message'
  content: string
  attachments?: ImageAttachment[]
}

export interface AssistantChatPingMessage {
  type: 'ping'
}

export type AssistantChatClientMessage =
  | AssistantChatStartMessage
  | AssistantChatUserMessage
  | AssistantChatPingMessage
