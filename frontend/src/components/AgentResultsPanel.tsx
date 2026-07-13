import { AGENTS, type AgentPayload } from '@/api/types'
import { AgentOutputCard } from '@/components/AgentOutputCard'
import { ImprovementAudit } from '@/components/ImprovementAudit'

const ITINERARY_AGENT_ID = 'final_response_agent'

interface Props {
  agents: AgentPayload
  label?: string
}

export function AgentResultsPanel({ agents, label = 'Agent breakdown' }: Props) {
  const completed = AGENTS.filter((agent) => {
    const value = agents[agent.field as keyof AgentPayload]
    return typeof value === 'string' && value.trim().length > 0
  })

  const hasAudit =
    (agents.lessons_loaded?.length ?? 0) > 0 ||
    (agents.review_summary?.findings?.length ?? 0) > 0 ||
    agents.review_summary?.problems_found !== undefined

  const itineraryDone = completed.some((agent) => agent.id === ITINERARY_AGENT_ID)

  if (completed.length === 0 && !hasAudit) return null

  return (
    <div className="flex flex-col gap-3">
      {completed.length > 0 && (
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      )}
      {AGENTS.map((agent) => {
        const value = agents[agent.field as keyof AgentPayload]
        if (typeof value !== 'string' || !value.trim()) return null

        return (
          <div key={agent.id} className="flex flex-col gap-3">
            <AgentOutputCard
              agent={agent}
              content={value}
              defaultOpen={agent.id === ITINERARY_AGENT_ID}
            />
            {agent.id === ITINERARY_AGENT_ID && itineraryDone && hasAudit && (
              <ImprovementAudit agents={agents} />
            )}
          </div>
        )
      })}
    </div>
  )
}
