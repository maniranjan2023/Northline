import { useEffect, useRef, useState } from 'react'
import { Loader2, LogOut, MapPin, Send, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { createSession, fetchPlan, getHealth, getStatus, sendMessage, streamPlan, waitForBackendReady } from '@/api/client'
import type { AgentPayload, ChatMessage, FeedbackState, SystemStatus } from '@/api/types'
import { AGENTS } from '@/api/types'
import { AgentCards } from '@/components/AgentCards'
import { AgentPipeline } from '@/components/AgentPipeline'
import { ChatMessageRow } from '@/components/ChatMessageRow'
import { FeedbackPanel } from '@/components/FeedbackPanel'
import { LiveAgentResults } from '@/components/LiveAgentResults'
import { ThinkingIndicator } from '@/components/ThinkingIndicator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

const QUICK_PROMPTS = [
  'Plan a 7-day Japan trip under ₹2L',
  '5-day Paris romantic getaway',
  'Dubai weekend luxury trip',
]

function newId() {
  return crypto.randomUUID()
}

type ThinkingPhase = 'idle' | 'thinking' | 'planning' | 'responding'

export function ChatPage() {
  const [username, setUsername] = useState(localStorage.getItem('NORTHLINE_username') ?? '')
  const [threadId, setThreadId] = useState(localStorage.getItem('NORTHLINE_thread_id') ?? '')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [started, setStarted] = useState(Boolean(username && threadId))
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [backendReady, setBackendReady] = useState(false)
  const [agentStates, setAgentStates] = useState<Record<string, string>>({})
  const [liveAgents, setLiveAgents] = useState<AgentPayload>({})
  const [pipelineStatus, setPipelineStatus] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [thinkingPhase, setThinkingPhase] = useState<ThinkingPhase>('idle')
  const [lastPlan, setLastPlan] = useState<AgentPayload | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [planLoading, setPlanLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    let attempt = 0

    async function loadStatus() {
      while (!cancelled && attempt < 60) {
        try {
          const health = await getHealth()
          if (!cancelled) {
            setBackendOnline(true)
            if (health.resources_ready) {
              const next = await getStatus()
              setStatus(next)
              setBackendReady(true)
              return
            }
            setBackendReady(false)
          }
          attempt += 1
          await new Promise((resolve) => setTimeout(resolve, 1500))
        } catch {
          attempt += 1
          if (!cancelled) {
            setBackendOnline(false)
            setBackendReady(false)
          }
          await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * attempt, 3000)))
        }
      }
    }

    loadStatus()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!started || !username || !threadId || messages.length > 0 || !backendReady) return

    setMessages([
      {
        id: newId(),
        role: 'assistant',
        content: `Welcome back, **${username}**! Plan a new trip or ask a follow-up about your saved plan.`,
        message_type: 'welcome',
      },
    ])

    setPlanLoading(true)
    fetchPlan(username, threadId)
      .then((plan) => {
        if (plan.plan) setLastPlan(plan.plan as AgentPayload)
      })
      .catch(() => undefined)
      .finally(() => setPlanLoading(false))
  }, [started, username, threadId, messages.length, backendReady])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, agentStates, thinkingPhase, liveAgents])

  async function startSession() {
    const name = username.trim()
    if (!name || sessionLoading) return
    setSessionLoading(true)
    try {
      if (!backendReady) {
        await waitForBackendReady()
        if (!backendReady) setBackendReady(true)
      }
      const session = await createSession(name)
      localStorage.setItem('NORTHLINE_username', session.username)
      localStorage.setItem('NORTHLINE_thread_id', session.thread_id)
      setUsername(session.username)
      setThreadId(session.thread_id)
      setStarted(true)
      setMessages([
        {
          id: newId(),
          role: 'assistant',
          content: session.welcome_message,
          message_type: 'welcome',
        },
      ])

      setPlanLoading(true)
      fetchPlan(session.username, session.thread_id)
        .then((plan) => {
          if (plan.plan) setLastPlan(plan.plan as AgentPayload)
        })
        .catch(() => undefined)
        .finally(() => setPlanLoading(false))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start session')
    } finally {
      setSessionLoading(false)
    }
  }

  async function handleSend(text: string) {
    const trimmed = text.trim()
    if (!trimmed || !started || streaming || thinkingPhase !== 'idle') return
    if (!backendReady) {
      toast.message('Backend is still starting — please wait a moment')
      return
    }
    setInput('')
    setMessages((prev) => [...prev, { id: newId(), role: 'user', content: trimmed, message_type: 'text' }])
    setThinkingPhase('thinking')

    try {
      const initial = await sendMessage({ username, thread_id: threadId, message: trimmed })
      if (initial.intent !== 'new_plan') {
        setThinkingPhase('responding')
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            role: 'assistant',
            content: initial.message,
            message_type: initial.message_type,
            run_id: initial.run_id ?? undefined,
            user_query: trimmed,
          },
        ])
        return
      }

      const runId = initial.run_id ?? newId()
      setThinkingPhase('planning')
      setStreaming(true)
      setPipelineStatus('Preparing your trip…')
      const initialStates = Object.fromEntries(AGENTS.map((agent) => [agent.id, 'pending']))
      setAgentStates(initialStates)
      setLiveAgents({ user_query: trimmed })
      let collected: AgentPayload = { user_query: trimmed }

      await streamPlan({
        username,
        thread_id: threadId,
        message: trimmed,
        run_id: runId,
        onEvent: (event) => {
          if (event.type === 'pipeline' || event.type === 'agent_done') {
            const states = event.data.agent_states as Record<string, string> | undefined
            if (states) setAgentStates({ ...states })
            const status = event.data.status_message as string | undefined
            if (status) setPipelineStatus(status)
          }
          if (event.type === 'status') {
            const status = event.data.message as string | undefined
            if (status) setPipelineStatus(status)
          }
          if (event.type === 'agent_done') {
            const field = event.data.field as keyof AgentPayload
            const value = event.data.value as string
            collected = {
              ...collected,
              [field]: value,
              destination: event.data.destination as string,
            }
            setLiveAgents((prev) => ({
              ...prev,
              [field]: value,
              destination: (event.data.destination as string) || prev.destination,
            }))
          }
          if (event.type === 'lessons_loaded') {
            collected = { ...collected, lessons_loaded: event.data.lessons_loaded as AgentPayload['lessons_loaded'] }
            setLiveAgents((prev) => ({
              ...prev,
              lessons_loaded: event.data.lessons_loaded as AgentPayload['lessons_loaded'],
            }))
          }
          if (event.type === 'review') {
            collected = { ...collected, review_summary: event.data.review_summary as AgentPayload['review_summary'] }
            setLiveAgents((prev) => ({
              ...prev,
              review_summary: event.data.review_summary as AgentPayload['review_summary'],
            }))
          }
          if (event.type === 'complete') {
            collected = event.data.agents as AgentPayload
            setMessages((prev) => [
              ...prev,
              {
                id: newId(),
                role: 'assistant',
                content: String(event.data.message ?? ''),
                message_type: 'plan',
                run_id: runId,
                user_query: trimmed,
                agents: collected,
              },
            ])
            setLastPlan(collected)
          }
        },
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Trip planning failed'
      toast.error(message)
      setMessages((prev) => [
        ...prev,
        {
          id: newId(),
          role: 'assistant',
          content: `Sorry, something went wrong while planning your trip.\n\n**Details:** ${message}`,
          message_type: 'text',
        },
      ])
    } finally {
      setStreaming(false)
      setAgentStates({})
      setLiveAgents({})
      setPipelineStatus('')
      setThinkingPhase('idle')
    }
  }

  function switchUser() {
    localStorage.removeItem('NORTHLINE_username')
    localStorage.removeItem('NORTHLINE_thread_id')
    setStarted(false)
    setUsername('')
    setThreadId('')
    setMessages([])
    setLastPlan(null)
  }

  if (!started) {
    return (
      <div className="flex min-h-[calc(100svh-8rem)] items-center justify-center">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center">
            <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="size-6" />
            </div>
            <CardTitle className="text-2xl">Welcome to Northline</CardTitle>
            <CardDescription>Multi-agent travel planning with memory and self-improvement.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. rahul"
                disabled={sessionLoading}
                onKeyDown={(e) => e.key === 'Enter' && !sessionLoading && startSession()}
              />
            </div>
            <Button className="w-full" onClick={startSession} disabled={!username.trim() || sessionLoading || backendOnline === false}>
              {sessionLoading ? (
                <>
                  <Loader2 data-icon="inline-start" className="animate-spin" />
                  Starting session…
                </>
              ) : (
                'Start planning'
              )}
            </Button>
            {backendOnline === false && (
              <p className="text-center text-xs text-destructive">
                Backend offline. In a terminal run:{' '}
                <code className="rounded bg-muted px-1 py-0.5">cd backend</code> then{' '}
                <code className="rounded bg-muted px-1 py-0.5">.\start.ps1</code>
              </p>
            )}
            {backendOnline === true && !backendReady && (
              <p className="text-center text-xs text-muted-foreground">
                Backend connected — loading graph and database…
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside className="flex flex-col gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Session</CardTitle>
            <CardDescription>Hi, {username}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {lastPlan?.destination && (
              <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2">
                <MapPin className="size-4 text-primary" />
                <span>Saved plan: {lastPlan.destination}</span>
              </div>
            )}
            {planLoading && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3 animate-spin" />
                Checking for saved plans…
              </div>
            )}
            <p className="truncate text-xs text-muted-foreground">Thread: {threadId}</p>
            <Button variant="outline" size="sm" onClick={switchUser}>
              <LogOut data-icon="inline-start" />
              Switch user
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Quick prompts</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {QUICK_PROMPTS.map((prompt) => (
              <Button
                key={prompt}
                variant="secondary"
                size="sm"
                className="h-auto whitespace-normal py-2 text-left"
                disabled={streaming || thinkingPhase !== 'idle'}
                onClick={() => handleSend(prompt)}
              >
                {prompt}
              </Button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">System</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {backendOnline === null && <Badge variant="outline">Connecting…</Badge>}
            {backendOnline === true && !backendReady && <Badge variant="outline">Warming up…</Badge>}
            {backendOnline === false && <Badge variant="destructive">Backend offline</Badge>}
            {backendReady && <Badge variant="secondary">Ready</Badge>}
            {status && (
              <>
                <Badge variant={status.guardrails_enabled ? 'secondary' : 'outline'}>Guardrails</Badge>
                <Badge variant={status.mem0_enabled ? 'secondary' : 'outline'}>Mem0</Badge>
                <Badge variant={status.langsmith?.enabled ? 'secondary' : 'outline'}>LangSmith</Badge>
                <Badge variant={status.mcp_ready ? 'secondary' : 'outline'}>MCP</Badge>
              </>
            )}
          </CardContent>
        </Card>
      </aside>

      <div className="flex min-h-[calc(100svh-10rem)] flex-col rounded-xl border bg-card shadow-sm">
        <div className="border-b px-4 py-3 sm:px-6">
          <h2 className="font-semibold">Travel assistant</h2>
          <p className="text-sm text-muted-foreground">Plan new trips or ask follow-ups without re-running agents.</p>
        </div>

        <ScrollArea className="flex-1 px-4 py-4 sm:px-6">
          <div className="flex flex-col gap-6 pb-4">
            {messages.map((message) => (
              <ChatMessageRow
                key={message.id}
                role={message.role}
                content={message.content}
                username={username}
              >
                {message.agents && (
                  <div className="w-full max-w-3xl">
                    <AgentCards agents={message.agents} />
                  </div>
                )}
                {message.run_id && (message.message_type === 'plan' || message.message_type === 'follow_up') && (
                  <div className="w-full max-w-md">
                    <FeedbackPanel
                      runId={message.run_id}
                      userQuery={message.user_query}
                      agents={message.agents}
                      feedback={message.feedback}
                      onFeedback={(feedback: FeedbackState) => {
                        setMessages((prev) =>
                          prev.map((item) => (item.id === message.id ? { ...item, feedback } : item)),
                        )
                      }}
                    />
                  </div>
                )}
              </ChatMessageRow>
            ))}
            {thinkingPhase !== 'idle' && (
              <div className="flex flex-col gap-4">
                <ThinkingIndicator
                  phase={
                    thinkingPhase === 'planning'
                      ? 'planning'
                      : thinkingPhase === 'responding'
                        ? 'responding'
                        : 'thinking'
                  }
                />
                {(streaming || Object.keys(agentStates).length > 0) && (
                  <AgentPipeline agentStates={agentStates} statusMessage={pipelineStatus} />
                )}
                <LiveAgentResults agents={liveAgents} />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <Separator />
        <form
          className="flex gap-2 p-4 sm:p-6"
          onSubmit={(e) => {
            e.preventDefault()
            handleSend(input)
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Plan a trip or ask a follow-up…"
            disabled={streaming || thinkingPhase !== 'idle'}
            className="flex-1"
          />
          <Button type="submit" disabled={streaming || thinkingPhase !== 'idle' || !input.trim()}>
            <Send data-icon="inline-start" />
            Send
          </Button>
        </form>
      </div>
    </div>
  )
}
