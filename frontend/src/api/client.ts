import type {
  CandidateSummary,
  ChatResponse,
  FeedbackResponse,
  ImprovementEvent,
  LessonSummary,
  ProposalDetail,
  ProposalSummary,
  SessionResponse,
  SystemStatus,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function parseErrorMessage(text: string, status: number): string {
  try {
    const data = JSON.parse(text) as { detail?: string }
    if (data.detail) return data.detail
  } catch {
    // not JSON
  }
  if (status === 502) {
    return 'Backend is starting on port 8000. Retrying in a moment…'
  }
  return text || `Request failed: ${status}`
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 60_000): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      signal: controller.signal,
      ...init,
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(parseErrorMessage(text, response.status))
    }
    return response.json() as Promise<T>
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Request timed out — is the backend running? Try again in a few seconds.')
    }
    if (err instanceof TypeError && /fetch|network/i.test(err.message)) {
      throw new Error('Cannot reach backend on port 8000. Start it with backend/start.ps1')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export async function waitForBackendOnline(maxWaitMs = 60_000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < maxWaitMs) {
    try {
      const health = await getHealth()
      if (health.status === 'ok') return
    } catch {
      // keep polling
    }
    await sleep(1000)
  }
  throw new Error('Backend is not reachable on port 8000. Run backend/stop.ps1 then backend/start.ps1')
}

export async function waitForBackendReady(maxWaitMs = 120_000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < maxWaitMs) {
    try {
      const health = await getHealth()
      if (health.resources_ready) return
    } catch {
      // keep polling
    }
    await sleep(1500)
  }
  throw new Error('Backend did not finish starting. Run backend/stop.ps1 then backend/start.ps1')
}

export function createSession(username: string) {
  return request<SessionResponse>(
    '/api/chat/session',
    {
      method: 'POST',
      body: JSON.stringify({ username }),
    },
    15_000,
  )
}

export function sendMessage(payload: {
  username: string
  thread_id: string
  message: string
  run_id?: string
}) {
  return request<ChatResponse>('/api/chat/message', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchPlan(username: string, threadId: string) {
  const params = new URLSearchParams({ username, thread_id: threadId })
  return request<{ plan: Record<string, unknown> | null }>(`/api/chat/plan?${params}`)
}

export function submitFeedback(payload: {
  run_id: string
  score: number
  comment?: string
  user_query?: string
  destination?: string
}) {
  return request<FeedbackResponse>('/api/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getHealth() {
  return request<{ status: string; mcp_ready: boolean; resources_ready: boolean }>('/api/health', undefined, 5_000)
}

export function getStatus() {
  return request<SystemStatus>('/api/status')
}

export function adminRequest<T>(path: string, adminKey: string, init?: RequestInit) {
  // First admin call may trigger full backend init (graph, Postgres, lesson book).
  return request<T>(
    path,
    {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        'X-Admin-Key': adminKey,
      },
    },
    120_000,
  )
}

export function listProposals(adminKey: string) {
  return adminRequest<ProposalSummary[]>('/api/admin/proposals', adminKey)
}

export function getProposal(adminKey: string, id: string) {
  return adminRequest<ProposalDetail>(`/api/admin/proposals/${id}`, adminKey)
}

export function reviewProposal(
  adminKey: string,
  id: string,
  payload: { action: 'approve' | 'reject'; target_dataset?: string; reviewer_note?: string },
) {
  return adminRequest(`/api/admin/proposals/${id}/review`, adminKey, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listLessons(adminKey: string) {
  return adminRequest<LessonSummary[]>('/api/admin/lessons', adminKey)
}

export function listCandidates(adminKey: string) {
  return adminRequest<CandidateSummary[]>('/api/admin/candidates', adminKey)
}

export function listEvents(adminKey: string) {
  return adminRequest<ImprovementEvent[]>('/api/admin/events?limit=100', adminKey)
}

export function streamPlan(params: {
  username: string
  thread_id: string
  message: string
  run_id: string
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void
  signal?: AbortSignal
}) {
  const query = new URLSearchParams({
    username: params.username,
    thread_id: params.thread_id,
    message: params.message,
    run_id: params.run_id,
  })
  return fetch(`${API_BASE}/api/chat/stream?${query}`, { signal: params.signal }).then(async (response) => {
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(text || `Stream failed (${response.status})`)
    }
    if (!response.body) {
      throw new Error('Stream failed: empty response body')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let completed = false

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          let payload: { type: string; data: Record<string, unknown> }
          try {
            payload = JSON.parse(line.slice(5).trim()) as { type: string; data: Record<string, unknown> }
          } catch {
            continue
          }
          if (payload.type === 'error') {
            throw new Error(String(payload.data.message ?? 'Trip planning failed'))
          }
          if (payload.type === 'complete') {
            completed = true
          }
          params.onEvent(payload)
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new Error('Trip planning was cancelled')
      }
      throw err
    }

    if (!completed) {
      throw new Error(
        'Trip planning was interrupted before completion. If this keeps happening, restart the backend and try again.',
      )
    }
  })
}
