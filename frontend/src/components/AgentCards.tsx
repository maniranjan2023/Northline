import type { AgentPayload } from '@/api/types'
import { AgentResultsPanel } from '@/components/AgentResultsPanel'

interface Props {
  agents: AgentPayload
}

export function AgentCards({ agents }: Props) {
  return <AgentResultsPanel agents={agents} label="Agent breakdown" />
}
