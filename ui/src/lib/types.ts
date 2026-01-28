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

// Feature types (legacy - now also used as Task in v2)
export interface Feature {
  id: number
  priority: number
  category: string
  name: string
  description: string
  steps: string[]
  passes: boolean
  in_progress: boolean
  // V2 dependency fields
  depends_on?: number[]
  blocks?: number[]
  is_blocked?: boolean
  blocked_reason?: string | null
  // V2 review fields
  reviewed?: boolean
  review_notes?: string | null
  review_score?: number | null
  // V2 additional fields
  feature_id?: number | null
  estimated_complexity?: number
  created_at?: string | null
  completed_at?: string | null
}

// Task type alias for clarity in v2 code
export type Task = Feature

// Dependency graph types
export interface DependencyNode {
  id: number
  name: string
  category: string
  status: 'pending' | 'in_progress' | 'blocked' | 'done'
  priority: number
  blocked_reason?: string | null
}

export interface DependencyEdge {
  from: number
  to: number
}

export interface DependencyGraph {
  nodes: DependencyNode[]
  edges: DependencyEdge[]
}

// Phase types (v2 hierarchical system)
export type PhaseStatus = 'pending' | 'in_progress' | 'awaiting_approval' | 'completed' | 'rejected'

export interface Phase {
  id: number
  project_name: string
  name: string
  description?: string | null
  order: number
  status: PhaseStatus
  created_at?: string | null
  completed_at?: string | null
}

export interface PhaseWithStats extends Phase {
  total_tasks: number
  passing_tasks: number
  in_progress_tasks: number
  blocked_tasks: number
  reviewed_tasks: number
  percentage: number
  average_review_score?: number | null
}

export interface PhasesOverview {
  project_name: string
  total_phases: number
  total_tasks: number
  total_passing: number
  overall_percentage: number
  phases: PhaseWithStats[]
}

// Feature group (v2 - contains tasks)
export interface FeatureGroup {
  id: number
  name: string
  description?: string | null
  phase_id: number
  order: number
  tasks: Feature[]
  total_tasks: number
  passing_tasks: number
  percentage: number
}

// YOLO mode types
export type YoloMode = 'standard' | 'yolo' | 'yolo_review' | 'yolo_parallel' | 'yolo_staged'

export interface YoloModeInfo {
  value: YoloMode
  label: string
  description: string
  icon: string
  skip_testing: boolean
  has_review: boolean
  parallel: boolean
}

export interface FeatureListResponse {
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

// Model configuration types
export interface ModelConfig {
  architect: string
  initializer: string
  coding: string
  reviewer: string
  testing: string
}

// Agent types
export type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed'

export interface AgentStatusResponse {
  status: AgentStatus
  pid: number | null
  started_at: string | null
  yolo_mode: boolean
  model_config: ModelConfig | null
}

// Git status types
export interface GitStatusResponse {
  has_git: boolean
  branch: string | null
  last_commit_hash: string | null
  last_commit_message: string | null
  last_commit_time: string | null
  is_dirty: boolean
  uncommitted_count: number
  total_commits: number
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
