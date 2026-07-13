import { cn } from '@/lib/utils'
import { AssistantAvatar } from '@/components/ChatAvatars'

const PHASE_LABELS: Record<string, string> = {
  thinking: 'Thinking',
  planning: 'Planning your trip',
  responding: 'Preparing response',
}

interface Props {
  phase?: 'thinking' | 'planning' | 'responding'
  className?: string
}

export function ThinkingIndicator({ phase = 'thinking', className }: Props) {
  const label = PHASE_LABELS[phase] ?? 'Thinking'

  return (
    <div className={cn('flex items-start gap-3', className)}>
      <AssistantAvatar />
      <div className="rounded-2xl rounded-bl-md border bg-muted/60 px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1" aria-hidden>
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:0ms]" />
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:150ms]" />
            <span className="size-1.5 animate-bounce rounded-full bg-primary/70 [animation-delay:300ms]" />
          </span>
          <span className="text-sm text-muted-foreground">
            {label}
            <span className="animate-pulse">…</span>
          </span>
        </div>
      </div>
    </div>
  )
}
