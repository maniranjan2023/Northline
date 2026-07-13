import { AGENTS } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { CheckCircle2, CircleDashed, Loader2, XCircle } from 'lucide-react'

const STATUS: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' }> = {
  pending: { label: 'Waiting', variant: 'outline' },
  running: { label: 'Running', variant: 'default' },
  done: { label: 'Done', variant: 'secondary' },
  error: { label: 'Issue', variant: 'destructive' },
}

interface Props {
  agentStates: Record<string, string>
  statusMessage?: string
}

export function AgentPipeline({ agentStates, statusMessage }: Props) {
  const doneCount = AGENTS.filter((agent) => agentStates[agent.id] === 'done').length
  const runningAgent = AGENTS.find((agent) => agentStates[agent.id] === 'running')

  return (
    <Card className="border-primary/20 bg-card/80 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm font-medium">Agent pipeline</CardTitle>
          <Badge variant="outline" className="font-normal">
            {doneCount}/{AGENTS.length} complete
          </Badge>
        </div>
        {statusMessage ? (
          <p className="text-xs text-muted-foreground">{statusMessage}</p>
        ) : runningAgent ? (
          <p className="text-xs text-muted-foreground">
            Now running: <span className="font-medium text-foreground">{runningAgent.title}</span>
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="hidden sm:flex items-center gap-1">
          {AGENTS.map((agent, index) => {
            const state = agentStates[agent.id] ?? 'pending'
            return (
              <div key={agent.id} className="flex min-w-0 flex-1 items-center gap-1">
                <div
                  className={cn(
                    'flex size-8 shrink-0 items-center justify-center rounded-full border text-sm transition-all',
                    state === 'pending' && 'border-muted-foreground/30 bg-muted/40 text-muted-foreground',
                    state === 'running' && 'border-primary bg-primary/10 text-primary shadow-sm ring-2 ring-primary/20',
                    state === 'done' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                    state === 'error' && 'border-destructive bg-destructive/10 text-destructive',
                  )}
                  title={agent.title}
                >
                  {state === 'running' ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : state === 'done' ? (
                    <CheckCircle2 className="size-4" />
                  ) : (
                    <span>{agent.icon}</span>
                  )}
                </div>
                {index < AGENTS.length - 1 && (
                  <div
                    className={cn(
                      'h-0.5 min-w-2 flex-1 rounded-full transition-colors',
                      state === 'done' ? 'bg-emerald-500/50' : 'bg-border',
                    )}
                  />
                )}
              </div>
            )
          })}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {AGENTS.map((agent) => {
            const state = agentStates[agent.id] ?? 'pending'
            const meta = STATUS[state] ?? STATUS.pending
            return (
              <div
                key={agent.id}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-xl border p-3 text-center transition-all',
                  state === 'pending' && 'border-border bg-muted/20 opacity-70',
                  state === 'running' && 'border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/20',
                  state === 'done' && 'border-emerald-500/30 bg-emerald-500/5',
                  state === 'error' && 'border-destructive/40 bg-destructive/5',
                )}
              >
                <span className="text-2xl">{agent.icon}</span>
                <p className="text-xs font-medium leading-tight">{agent.title}</p>
                <Badge variant={meta.variant} className="gap-1 text-[10px]">
                  {state === 'running' && <Loader2 className="size-3 animate-spin" />}
                  {state === 'done' && <CheckCircle2 className="size-3" />}
                  {state === 'pending' && <CircleDashed className="size-3" />}
                  {state === 'error' && <XCircle className="size-3" />}
                  {meta.label}
                </Badge>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
