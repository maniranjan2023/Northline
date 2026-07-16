export interface SessionResponse {
  username: string
  thread_id: string
  has_plan: boolean
  welcome_message: string
}

export interface MemoryUpdateInfo {
  action: 'added' | 'updated'
  attribute_key: string
  attribute_label: string
  previous_value?: string
  new_value: string
  source?: string
}

export interface ChatResponse {
  intent:
    | 'greeting'
    | 'follow_up'
    | 'new_plan'
    | 'clarify'
    | 'blocked'
    | 'preference_statement'
    | 'preference_correction'
    | 'preference_query'
  message: string
  run_id: string | null
  message_type: 'welcome' | 'text' | 'plan' | 'follow_up' | 'clarify' | 'blocked'
  agents?: AgentPayload | null
  guardrail_reason?: string | null
  memory_update?: MemoryUpdateInfo | null
}

export interface AgentPayload {
  user_query?: string
  destination?: string
  planner_output?: string
  research_output?: string
  hotel_results?: string
  flight_results?: string
  activity_results?: string
  itinerary?: string
  lessons_loaded?: LessonLoaded[]
  review_summary?: ReviewSummary
  quality_passed?: boolean
  quality_issues?: string[]
}

export interface LessonLoaded {
  lesson_id: string
  lesson: string
  category: string
  confidence: number
}

export interface ReviewSummary {
  problems_found?: number
  lessons_created?: string[]
  lessons_updated?: string[]
  findings?: Array<{ problem: string; suggested_lesson: string; reason?: string }>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  message_type: string
  run_id?: string
  user_query?: string
  agents?: AgentPayload
  feedback?: FeedbackState | null
  memory_update?: MemoryUpdateInfo | null
}

export interface FeedbackState {
  score: number
  comment?: string
  diagnosis?: string
  proposal_path?: string
  proposal_pending?: boolean
  promoted_lesson_id?: string
}

export interface FeedbackResponse {
  submitted: boolean
  score: number
  comment?: string
  diagnosis?: string | null
  proposal_path?: string | null
  proposal_pending?: boolean
  candidate_id?: string | null
  promoted_lesson_id?: string | null
  error?: string | null
}

export interface ProposalSummary {
  id: string
  filename: string
  run_id: string
  component: string
  target_dataset: string
  feedback_comment: string
  review_status: 'pending' | 'approved' | 'rejected'
  created_at?: string | null
}

export interface ProposalDetail extends ProposalSummary {
  proposal: Record<string, unknown>
}

export interface LessonSummary {
  lesson_id: string
  lesson: string
  category: string
  confidence: number
  times_seen: number
  status: string
  destination?: string | null
}

export interface CandidateSummary {
  candidate_id: string
  suggested_lesson: string
  category: string
  problem: string
  times_seen: number
  confidence: number
  status: string
}

export interface ImprovementEvent {
  event_id?: string
  event_type: string
  run_id?: string | null
  thread_id?: string | null
  user_id?: string | null
  payload: Record<string, unknown>
  created_at?: string | null
}

export interface SystemStatus {
  guardrails_enabled: boolean
  mem0_enabled: boolean
  langsmith: Record<string, unknown>
  mcp_ready?: boolean
}

export type EvalSuiteRequest = 'all' | 'ci' | 'single_turn' | 'multi_turn'
export type EvalSuiteKey = 'ci' | 'single_turn' | 'multi_turn'
export type SuiteRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped'
export type EvalJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface EvalMetricSummary {
  metric_name: string
  passed: number
  total: number
  pass_rate: number
}

export interface EvalResultRow {
  metric_name: string
  case_id: string
  passed: boolean
  score: number | null
  threshold: number | null
  reason: string
  input_preview: string
}

export interface EvalSuiteResults {
  suite: string
  suite_label: string
  run_at?: string | null
  passed: number
  total: number
  metrics_summary: EvalMetricSummary[]
  rows: EvalResultRow[]
}

export interface EvalResultsResponse {
  ci: EvalSuiteResults | null
  single_turn: EvalSuiteResults | null
  multi_turn: EvalSuiteResults | null
  eval_deps_installed: boolean
  inngest_configured?: boolean
  worker_mode?: string
  active_job_id?: string | null
  schedules?: Record<string, { cron: string; label: string; timezone: string }>
}

export interface EvalSuiteProgress {
  status: SuiteRunStatus
  passed?: number | null
  failed?: number | null
  total?: number | null
  exit_code?: number | null
  duration_seconds?: number | null
  error?: string | null
}

export interface EvalJobResponse {
  job_id: string
  suite: EvalSuiteRequest
  status: EvalJobStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  progress: Record<EvalSuiteKey, EvalSuiteProgress>
  error?: string | null
  log_tail?: string
}

export interface EvalRunStartResponse {
  job_id: string
  suite: EvalSuiteRequest
  status: EvalJobStatus
  message: string
}

export interface EvalCapabilities {
  eval_deps_installed: boolean
  deepeval_available: boolean
  pytest_available: boolean
  inngest_configured?: boolean
  worker_mode?: string
  active_job_id?: string | null
  schedules?: Record<string, { cron: string; label: string; timezone: string }>
  suites: Record<
    EvalSuiteKey,
    {
      label: string
      metric_count: number
      requires_live: boolean
      schedule?: { cron: string; label: string; timezone: string }
    }
  >
}

export interface AgentMeta {
  id: string
  icon: string
  title: string
  field: string
}

export const AGENTS: AgentMeta[] = [
  { id: 'planner_agent', icon: '🧭', title: 'Planner Agent', field: 'planner_output' },
  { id: 'research_agent', icon: '🔍', title: 'Research Agent', field: 'research_output' },
  { id: 'hotel_agent', icon: '🏨', title: 'Hotel Agent', field: 'hotel_results' },
  { id: 'flight_agent', icon: '✈️', title: 'Flight Agent', field: 'flight_results' },
  { id: 'activity_agent', icon: '🎯', title: 'Activity Agent', field: 'activity_results' },
  { id: 'final_response_agent', icon: '🗓️', title: 'Itinerary Agent', field: 'itinerary' },
]
