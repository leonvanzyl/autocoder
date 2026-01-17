/**
 * API Client for the Autonomous Coding UI
 */

import type {
  ProjectSummary,
  ProjectDetail,
  ProjectPrompts,
  FeatureListResponse,
  Feature,
  FeatureCreate,
  AgentStatusResponse,
  AgentActionResponse,
  AgentStartRequest,
  SetupStatus,
  DirectoryListResponse,
  PathValidationResponse,
  AssistantConversation,
  AssistantConversationDetail,
  WorkerLogsListResponse,
  WorkerLogTailResponse,
  PruneWorkerLogsRequest,
  PruneWorkerLogsResponse,
  AdvancedSettings,
  DevServerStatusResponse,
  DevServerStartRequest,
  DevServerActionResponse,
  TerminalInfo,
} from './types'

const API_BASE = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// ============================================================================
// Projects API
// ============================================================================

export async function listProjects(): Promise<ProjectSummary[]> {
  return fetchJSON('/projects')
}

export async function createProject(
  name: string,
  path: string,
  specMethod: 'claude' | 'manual' = 'manual'
): Promise<ProjectSummary> {
  return fetchJSON('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, path, spec_method: specMethod }),
  })
}

export async function getProject(name: string): Promise<ProjectDetail> {
  return fetchJSON(`/projects/${encodeURIComponent(name)}`)
}

export async function deleteProject(name: string): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}

export async function getProjectPrompts(name: string): Promise<ProjectPrompts> {
  return fetchJSON(`/projects/${encodeURIComponent(name)}/prompts`)
}

export async function updateProjectPrompts(
  name: string,
  prompts: Partial<ProjectPrompts>
): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(name)}/prompts`, {
    method: 'PUT',
    body: JSON.stringify(prompts),
  })
}

// ============================================================================
// Features API
// ============================================================================

export async function listFeatures(projectName: string): Promise<FeatureListResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features`)
}

export async function createFeature(projectName: string, feature: FeatureCreate): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features`, {
    method: 'POST',
    body: JSON.stringify(feature),
  })
}

export async function getFeature(projectName: string, featureId: number): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}`)
}

export async function deleteFeature(projectName: string, featureId: number): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}`, {
    method: 'DELETE',
  })
}

export async function skipFeature(projectName: string, featureId: number): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}/skip`, {
    method: 'PATCH',
  })
}

export async function updateFeature(
  projectName: string,
  featureId: number,
  update: Partial<FeatureCreate>
): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}`, {
    method: 'PATCH',
    body: JSON.stringify(update),
  })
}

export async function enqueueFeature(projectName: string, featureId: number): Promise<Feature> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/${featureId}/enqueue`, {
    method: 'PATCH',
  })
}

export interface EnqueueFeaturesResponse {
  requested: number
  enabled: number
}

export async function enqueueFeatures(projectName: string, count: number): Promise<EnqueueFeaturesResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/features/enqueue`, {
    method: 'POST',
    body: JSON.stringify({ count }),
  })
}

// ============================================================================
// Agent API
// ============================================================================

export async function getAgentStatus(projectName: string): Promise<AgentStatusResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/status`)
}

export async function startAgent(
  projectName: string,
  options: AgentStartRequest = {}
): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/start`, {
    method: 'POST',
    body: JSON.stringify({
      yolo_mode: options.yolo_mode || false,
      parallel_mode: options.parallel_mode || false,
      parallel_count: options.parallel_count || 3,
      model_preset: options.model_preset || 'balanced',
    }),
  })
}

export async function stopAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/stop`, {
    method: 'POST',
  })
}

export async function pauseAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/pause`, {
    method: 'POST',
  })
}

export async function resumeAgent(projectName: string): Promise<AgentActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/agent/resume`, {
    method: 'POST',
  })
}

// ============================================================================
// Worker Logs API
// ============================================================================

export async function listWorkerLogs(projectName: string): Promise<WorkerLogsListResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/logs/worker`)
}

export async function getWorkerLogTail(
  projectName: string,
  filename: string,
  tail: number = 400
): Promise<WorkerLogTailResponse> {
  const params = new URLSearchParams({ tail: String(tail) })
  return fetchJSON(
    `/projects/${encodeURIComponent(projectName)}/logs/worker/${encodeURIComponent(filename)}?${params}`
  )
}

export async function pruneWorkerLogs(
  projectName: string,
  req: PruneWorkerLogsRequest
): Promise<PruneWorkerLogsResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/logs/worker/prune`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function deleteWorkerLog(projectName: string, filename: string): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/logs/worker/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Advanced Settings API
// ============================================================================

export async function getAdvancedSettings(): Promise<AdvancedSettings> {
  return fetchJSON('/settings/advanced')
}

export async function updateAdvancedSettings(settings: AdvancedSettings): Promise<AdvancedSettings> {
  return fetchJSON('/settings/advanced', {
    method: 'PUT',
    body: JSON.stringify(settings),
  })
}

// ============================================================================
// Dev Server API
// ============================================================================

export async function getDevServerStatus(projectName: string): Promise<DevServerStatusResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/devserver/status`)
}

export async function startDevServer(
  projectName: string,
  req: DevServerStartRequest = {}
): Promise<DevServerActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/devserver/start`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function stopDevServer(projectName: string): Promise<DevServerActionResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/devserver/stop`, {
    method: 'POST',
  })
}

// ============================================================================
// Terminal API
// ============================================================================

export async function listTerminals(projectName: string): Promise<TerminalInfo[]> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/terminal`)
}

export async function createTerminal(projectName: string, name?: string): Promise<TerminalInfo> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/terminal`, {
    method: 'POST',
    body: JSON.stringify({ name: name ?? null }),
  })
}

export async function renameTerminal(projectName: string, terminalId: string, name: string): Promise<TerminalInfo> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/terminal/${encodeURIComponent(terminalId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export async function deleteTerminal(projectName: string, terminalId: string): Promise<void> {
  await fetchJSON(`/projects/${encodeURIComponent(projectName)}/terminal/${encodeURIComponent(terminalId)}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Diagnostics API
// ============================================================================

export interface DiagnosticsFixturesDirResponse {
  default_dir: string
  configured_dir: string
  effective_dir: string
}

export async function getDiagnosticsFixturesDir(): Promise<DiagnosticsFixturesDirResponse> {
  return fetchJSON('/diagnostics/fixtures-dir')
}

export interface RunQAProviderE2ERequest {
  fixture: 'node' | 'python'
  provider: 'claude' | 'codex_cli' | 'gemini_cli' | 'multi_cli'
  timeout_s?: number
}

export interface RunQAProviderE2EResponse {
  success: boolean
  exit_code: number
  out_dir: string
  log_path: string
  output_tail: string
}

export async function runQAProviderE2E(req: RunQAProviderE2ERequest): Promise<RunQAProviderE2EResponse> {
  return fetchJSON('/diagnostics/e2e/qa-provider/run', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export interface RunParallelMiniE2ERequest {
  parallel?: number
  preset?: string
  timeout_s?: number
}

export interface RunParallelMiniE2EResponse {
  success: boolean
  exit_code: number
  out_dir: string
  log_path: string
  output_tail: string
}

export async function runParallelMiniE2E(req: RunParallelMiniE2ERequest): Promise<RunParallelMiniE2EResponse> {
  return fetchJSON('/diagnostics/e2e/parallel-mini/run', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export interface DiagnosticsRun {
  name: string
  path: string
  size_bytes: number
  modified_at: string
}

export async function listDiagnosticsRuns(limit: number = 25): Promise<DiagnosticsRun[]> {
  const n = Math.max(1, Math.min(200, Number(limit || 25)))
  return fetchJSON(`/diagnostics/runs?limit=${encodeURIComponent(String(n))}`)
}

export interface DiagnosticsRunTailResponse {
  name: string
  path: string
  size_bytes: number
  modified_at: string
  tail: string
}

export async function tailDiagnosticsRun(
  name: string,
  maxChars: number = 8000
): Promise<DiagnosticsRunTailResponse> {
  const n = Math.max(200, Math.min(200000, Number(maxChars || 8000)))
  return fetchJSON(
    `/diagnostics/runs/${encodeURIComponent(name)}/tail?max_chars=${encodeURIComponent(String(n))}`
  )
}

// ============================================================================
// Worktrees / Cleanup Queue (per project)
// ============================================================================

export interface CleanupQueueItem {
  path: string
  attempts: number
  next_try_at: number
  added_at: number
  reason: string
}

export interface CleanupQueueResponse {
  queue_path: string
  items: CleanupQueueItem[]
}

export async function getCleanupQueue(projectName: string): Promise<CleanupQueueResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/worktrees/cleanup-queue`)
}

export interface ProcessCleanupQueueRequest {
  max_items?: number
}

export interface ProcessCleanupQueueResponse {
  processed: number
  remaining: number
  queue_path: string
}

export async function processCleanupQueue(
  projectName: string,
  req: ProcessCleanupQueueRequest = {}
): Promise<ProcessCleanupQueueResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/worktrees/cleanup-queue/process`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function clearCleanupQueue(projectName: string): Promise<{ success: boolean; queue_path: string }> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/worktrees/cleanup-queue/clear`, {
    method: 'POST',
    body: JSON.stringify({ confirm: true }),
  })
}

// ============================================================================
// Multi-Model Generate API
// ============================================================================

export interface GenerateArtifactRequest {
  kind: 'spec' | 'plan'
  prompt: string
  agents?: string
  synthesizer?: '' | 'none' | 'claude' | 'codex' | 'gemini'
  no_synthesize?: boolean
  timeout_s?: number
  out?: string
}

export interface GenerateArtifactResponse {
  output_path: string
  drafts_dir: string
}

export async function generateArtifact(
  projectName: string,
  req: GenerateArtifactRequest
): Promise<GenerateArtifactResponse> {
  return fetchJSON(`/generate/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export interface GsdStatusResponse {
  exists: boolean
  codebase_dir: string
  present: string[]
  missing: string[]
}

export interface GsdToSpecRequest {
  agents?: string
  synthesizer?: '' | 'none' | 'claude' | 'codex' | 'gemini'
  no_synthesize?: boolean
  timeout_s?: number
  out?: string
}

export async function getGsdStatus(projectName: string): Promise<GsdStatusResponse> {
  return fetchJSON(`/generate/${encodeURIComponent(projectName)}/gsd/status`)
}

export async function gsdToSpec(projectName: string, req: GsdToSpecRequest): Promise<GenerateArtifactResponse> {
  return fetchJSON(`/generate/${encodeURIComponent(projectName)}/gsd/to-spec`, {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ============================================================================
// Project Config (autocoder.yaml)
// ============================================================================

export interface AutocoderYamlResponse {
  exists: boolean
  path: string
  content: string
  inferred_preset?: string | null
  resolved_commands?: string[]
  resolved_worker_provider?: string | null
  resolved_worker_patch_max_iterations?: number | null
  resolved_initializer_provider?: string | null
  resolved_initializer_agents?: string[] | null
  resolved_initializer_synthesizer?: string | null
  resolved_initializer_timeout_s?: number | null
  resolved_initializer_stage_threshold?: number | null
  resolved_initializer_enqueue_count?: number | null
}

export async function getAutocoderYaml(projectName: string): Promise<AutocoderYamlResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/config/autocoder`)
}

export async function updateAutocoderYaml(
  projectName: string,
  content: string
): Promise<AutocoderYamlResponse> {
  return fetchJSON(`/projects/${encodeURIComponent(projectName)}/config/autocoder`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  })
}

// ============================================================================
// Spec Creation API
// ============================================================================

export interface SpecFileStatus {
  exists: boolean
  status: 'complete' | 'in_progress' | 'not_started' | 'error' | 'unknown'
  feature_count: number | null
  timestamp: string | null
  files_written: string[]
}

export async function getSpecStatus(projectName: string): Promise<SpecFileStatus> {
  return fetchJSON(`/spec/status/${encodeURIComponent(projectName)}`)
}

// ============================================================================
// Setup API
// ============================================================================

export async function getSetupStatus(): Promise<SetupStatus> {
  return fetchJSON('/setup/status')
}

export async function healthCheck(): Promise<{ status: string }> {
  return fetchJSON('/health')
}

// ============================================================================
// Filesystem API
// ============================================================================

export async function listDirectory(path?: string): Promise<DirectoryListResponse> {
  const params = path ? `?path=${encodeURIComponent(path)}` : ''
  return fetchJSON(`/filesystem/list${params}`)
}

export async function createDirectory(fullPath: string): Promise<{ success: boolean; path: string }> {
  // Backend expects { parent_path, name }, not { path }
  // Split the full path into parent directory and folder name

  // Remove trailing slash if present
  const normalizedPath = fullPath.endsWith('/') ? fullPath.slice(0, -1) : fullPath

  // Find the last path separator
  const lastSlash = normalizedPath.lastIndexOf('/')

  let parentPath: string
  let name: string

  // Handle Windows drive root (e.g., "C:/newfolder")
  if (lastSlash === 2 && /^[A-Za-z]:/.test(normalizedPath)) {
    // Path like "C:/newfolder" - parent is "C:/"
    parentPath = normalizedPath.substring(0, 3) // "C:/"
    name = normalizedPath.substring(3)
  } else if (lastSlash > 0) {
    parentPath = normalizedPath.substring(0, lastSlash)
    name = normalizedPath.substring(lastSlash + 1)
  } else if (lastSlash === 0) {
    // Unix root path like "/newfolder"
    parentPath = '/'
    name = normalizedPath.substring(1)
  } else {
    // No slash - invalid path
    throw new Error('Invalid path: must be an absolute path')
  }

  if (!name) {
    throw new Error('Invalid path: directory name is empty')
  }

  return fetchJSON('/filesystem/create-directory', {
    method: 'POST',
    body: JSON.stringify({ parent_path: parentPath, name }),
  })
}

export async function validatePath(path: string): Promise<PathValidationResponse> {
  return fetchJSON('/filesystem/validate', {
    method: 'POST',
    body: JSON.stringify({ path }),
  })
}

// ============================================================================
// Assistant Chat API
// ============================================================================

export async function listAssistantConversations(
  projectName: string
): Promise<AssistantConversation[]> {
  return fetchJSON(`/assistant/conversations/${encodeURIComponent(projectName)}`)
}

export async function getAssistantConversation(
  projectName: string,
  conversationId: number
): Promise<AssistantConversationDetail> {
  return fetchJSON(
    `/assistant/conversations/${encodeURIComponent(projectName)}/${conversationId}`
  )
}

export async function createAssistantConversation(
  projectName: string
): Promise<AssistantConversation> {
  return fetchJSON(`/assistant/conversations/${encodeURIComponent(projectName)}`, {
    method: 'POST',
  })
}

export async function deleteAssistantConversation(
  projectName: string,
  conversationId: number
): Promise<void> {
  await fetchJSON(
    `/assistant/conversations/${encodeURIComponent(projectName)}/${conversationId}`,
    { method: 'DELETE' }
  )
}
