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
}

// Status type for graph nodes
export type FeatureStatus = 'pending' | 'in_progress' | 'done' | 'blocked'

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
export type AgentStatus = 'stopped' | 'running' | 'paused' | 'crashed' | 'loading'

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
  featureId: number
  featureName: string
  state: AgentState
  thought?: string
  timestamp: string
  logs?: AgentLogEntry[]  // Per-agent log history
  model?: string  // Model ID, e.g., "claude-sonnet-4-5-20250514"
}

// Orchestrator state for Mission Control
export type OrchestratorState =
  | 'idle'
  | 'initializing'
  | 'scheduling'
  | 'spawning'
  | 'monitoring'
  | 'complete'

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

export interface Settings {
  yolo_mode: boolean
  model: string  // Default model (for backwards compat)
  coder_model: string  // Model for coding agents
  tester_model: string  // Model for testing agents
  initializer_model: string  // Model for initializer agent
  glm_mode: boolean
  ollama_mode: boolean
  testing_agent_ratio: number  // Regression testing agents (0-3)
}

export interface SettingsUpdate {
  yolo_mode?: boolean
  model?: string
  coder_model?: string
  tester_model?: string
  initializer_model?: string
  testing_agent_ratio?: number
}

export interface ProjectSettingsUpdate {
  default_concurrency?: number
}

// ============================================================================
// Multi-Model Configuration Types (Chance Edition)
// ============================================================================

export type ModelTier = 'opus' | 'sonnet' | 'haiku'

export interface ModelConfig {
  id: string
  name: string
  tier: ModelTier
  contextWindow: number
  maxOutputTokens: number
  supportsVision: boolean
  supportsExtendedThinking: boolean
  costPer1kInput: number
  costPer1kOutput: number
  description: string
}

export interface ModelProfile {
  name: string
  description: string
  initializerModel: string
  coderModel: string
  testerModel: string
  reviewerModel: string | null
  plannerModel: string | null
}

export interface ModelListResponse {
  models: ModelConfig[]
  tiers: Record<string, string[]>
  defaultModel: string
}

export interface ProfileListResponse {
  profiles: ModelProfile[]
  defaultProfile: string
}

// Project-level settings with multi-model support
export interface ProjectModelSettings {
  defaultModel?: string
  coderModel?: string
  testerModel?: string
  initializerModel?: string
  defaultProfile?: string
  maxConcurrency?: number
  yoloMode?: boolean
  testingDirectory?: string
  autoCommit?: boolean
}

// App-level settings
export interface AppModelSettings {
  defaultModel: string
  coderModel: string
  testerModel: string
  initializerModel: string
  defaultProfile: string
  maxConcurrency: number
  yoloMode: boolean
  autoResume: boolean
  pauseOnError: boolean
  theme: 'system' | 'light' | 'dark'
  showDebugPanel: boolean
  celebrateOnComplete: boolean
  autoCommit: boolean
  commitMessagePrefix: string
}

export interface EffectiveSettingsResponse {
  settings: Record<string, unknown>
  sources: Record<string, 'project' | 'app' | 'default'>
}

// Version information
export interface VersionInfo {
  version: string
  edition: string
  year: number
  major: number
  minor: number
  patch: number
  buildDate: string
  description: string
  fullVersion: string
  shortVersion: string
}

// Git error types
export type GitErrorType =
  | 'git_not_installed'
  | 'not_a_repo'
  | 'auth_failed'
  | 'timeout'
  | 'no_remote'
  | 'network'
  | 'unknown'

export interface GitError {
  error_type: GitErrorType
  message: string
  action: string  // Suggested remediation
}

// Git status types
export interface GitStatus {
  isRepo: boolean
  branch: string | null
  ahead: number
  behind: number
  modified: number
  staged: number
  untracked: number
  hasUncommittedChanges: boolean
  lastCommitMessage: string | null
  lastCommitDate: string | null
  error?: GitError | null  // Structured error information
}

// ============================================================================
// Usage Tracking Types (Chance Edition Phase 3)
// ============================================================================

export interface UsageRecord {
  id: number
  projectName: string
  modelId: string
  agentType: string
  featureId: number | null
  featureName: string | null
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  cacheWriteTokens: number
  estimatedCost: number
  timestamp: string
  durationMs: number | null
  metadata: Record<string, unknown> | null
}

export interface UsageTotals {
  calls: number
  inputTokens: number
  outputTokens: number
  cost: number
}

export interface UsageByModel {
  modelId: string
  calls: number
  inputTokens: number
  outputTokens: number
  cost: number
}

export interface UsageByAgentType {
  agentType: string
  calls: number
  cost: number
}

export interface FeatureStats {
  totalAttempts: number
  successful: number
  successRate: number
}

export interface UsageSummary {
  projectName: string
  periodDays: number
  totals: UsageTotals
  byModel: UsageByModel[]
  byAgentType: UsageByAgentType[]
  featureStats: FeatureStats
}

export interface DailyUsage {
  date: string
  calls: number
  inputTokens: number
  outputTokens: number
  cost: number
}

export interface FeatureAttempt {
  id: number
  projectName: string
  featureId: number
  featureName: string | null
  featureCategory: string | null
  attemptNumber: number
  modelId: string
  startedAt: string
  completedAt: string | null
  success: boolean
  failureReason: string | null
  totalInputTokens: number
  totalOutputTokens: number
  totalCost: number
  totalDurationMs: number
}

export interface CostEstimate {
  projectName: string
  periodDays: number
  totalCost: number
  avgDailyCost: number
  projectedMonthlyCost: number
  costByModel: UsageByModel[]
  costByAgentType: UsageByAgentType[]
  dailyTrend: DailyUsage[]
}

// Learning/Smart Orchestrator Types
export interface LearningInsight {
  id: number
  insightType: string
  category: string | null
  title: string
  description: string
  confidence: number
  data: Record<string, unknown> | null
  createdAt: string
  applied: boolean
}

export interface CategoryStats {
  id: number
  category: string
  totalAttempts: number
  successfulAttempts: number
  successRate: number
  avgAttemptsToSuccess: number
  bestModel: string | null
  modelSuccessRate: number
  avgInputTokens: number
  avgOutputTokens: number
  avgCost: number
  avgDurationMs: number
  estimatedDifficulty: number
  updatedAt: string | null
}

export interface ModelStats {
  id: number
  modelId: string
  category: string | null
  totalAttempts: number
  successfulAttempts: number
  successRate: number
  totalInputTokens: number
  totalOutputTokens: number
  totalCost: number
  costPerSuccess: number
  avgDurationMs: number
  updatedAt: string | null
}

// ============================================================================
// Pull Request Types (Chance Edition Phase 4)
// ============================================================================

export interface PullRequest {
  number: number
  title: string
  state: string
  url: string
  head_branch: string
  base_branch: string
  author: string | null
  created_at: string | null
  updated_at: string | null
  mergeable: boolean | null
  additions: number | null
  deletions: number | null
  changed_files: number | null
}

export interface PRStatus {
  hasPR: boolean
  authenticated: boolean
  currentBranch: string | null
  pr?: PullRequest
  message?: string
}

export interface PRCreateRequest {
  title: string
  body?: string
  base_branch?: string
  draft?: boolean
}

export interface PRCheck {
  name: string
  state: string
  conclusion: string | null
  startedAt: string | null
  completedAt: string | null
  detailsUrl: string | null
}

export interface PRChecksResponse {
  hasChecks: boolean
  checks: PRCheck[]
  summary?: {
    total: number
    passing: number
    failing: number
    pending: number
  }
  message?: string
}

export interface PRListResponse {
  prs: PullRequest[]
  state: string
}

// ============================================================================
// Deployment Types (Chance Edition Phase 4)
// ============================================================================

export type DeploymentStatus = 'pending' | 'in_progress' | 'success' | 'failed' | 'rolled_back' | 'cancelled'
export type DeploymentEnvironment = 'development' | 'staging' | 'production' | 'preview'
export type DeploymentStrategy = 'direct' | 'blue_green' | 'canary' | 'rolling'

export interface Deployment {
  id: number
  projectName: string
  environment: DeploymentEnvironment
  status: DeploymentStatus
  strategy: DeploymentStrategy
  branch: string | null
  commitSha: string | null
  commitMessage: string | null
  deployUrl: string | null
  logs: string | null
  errorMessage: string | null
  durationMs: number | null
  artifactCount: number | null
  metadata: Record<string, unknown> | null
  startedAt: string | null
  completedAt: string | null
  createdAt: string | null
}

export interface DeploymentCheck {
  id: number
  deploymentId: number
  checkType: 'pre' | 'post'
  name: string
  status: string
  output: string | null
  durationMs: number | null
  createdAt: string | null
}

export interface DeployRequest {
  environment: DeploymentEnvironment
  strategy?: DeploymentStrategy
  branch?: string
  commit_sha?: string
  deploy_command?: string
  pre_deploy_checks?: string[]
  post_deploy_checks?: string[]
  rollback_command?: string
  metadata?: Record<string, unknown>
}

export interface DeployResponse {
  success: boolean
  deployment_id: number | null
  message: string
  duration_ms: number
  logs: string[]
}

export interface DeploymentListResponse {
  deployments: Deployment[]
}

export interface EnvironmentStatus {
  environment: DeploymentEnvironment
  latestDeployment: Deployment | null
  status: string
}

export interface EnvironmentStatusResponse {
  [key: string]: EnvironmentStatus
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
