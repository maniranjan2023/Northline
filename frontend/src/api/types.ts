export interface SessionResponse {
  username: string
  thread_id: string
  has_plan: boolean
  welcome_message: string
}

export interface ChatResponse {
  intent: 'greeting' | 'follow_up' | 'new_plan' | 'clarify' | 'blocked'
  message: string
  run_id: string | null
  message_type: 'welcome' | 'text' | 'plan' | 'follow_up' | 'clarify' | 'blocked'
  agents?: AgentPayload | null
  guardrail_reason?: string | null
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
