import type { AgentMeta } from '@/api/types'
import { MarkdownContent } from '@/components/MarkdownContent'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { CheckCircle2 } from 'lucide-react'

interface Props {
  agent: AgentMeta
  content: string
  className?: string
  defaultOpen?: boolean
}

export function AgentOutputCard({ agent, content, className, defaultOpen = false }: Props) {
  return (
    <Accordion
      defaultValue={defaultOpen ? [agent.id] : undefined}
      className={cn('animate-in fade-in slide-in-from-bottom-2 rounded-xl border border-emerald-500/20 bg-card duration-500', className)}
    >
      <AccordionItem value={agent.id} className="border-0 px-3">
        <AccordionTrigger className="py-3 hover:no-underline">
          <span className="flex flex-1 items-center gap-2 text-left">
            <span className="text-xl">{agent.icon}</span>
            <span className="font-medium">{agent.title}</span>
          </span>
          <Badge variant="secondary" className="mr-2 gap-1">
            <CheckCircle2 className="size-3" />
            Done
          </Badge>
        </AccordionTrigger>
        <AccordionContent className="pb-3">
          <MarkdownContent content={content} />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
