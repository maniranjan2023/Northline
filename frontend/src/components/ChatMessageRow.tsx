import type { ReactNode } from 'react'
import { AssistantAvatar, UserAvatar } from '@/components/ChatAvatars'
import { MarkdownContent } from '@/components/MarkdownContent'

interface Props {
  role: 'user' | 'assistant'
  content: string
  username: string
  children?: ReactNode
}

export function ChatMessageRow({ role, content, username, children }: Props) {
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="flex max-w-[min(85%,42rem)] items-end gap-3">
          <div className="flex min-w-0 flex-1 flex-col items-end gap-1.5">
            <div className="rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground shadow-sm">
              {content}
            </div>
            <span className="px-1 text-xs text-muted-foreground">You</span>
            {children}
          </div>
          <UserAvatar name={username} className="mb-5 shrink-0" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="flex max-w-[min(92%,48rem)] items-start gap-3">
        <AssistantAvatar className="mt-0.5 shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col items-start gap-3">
          <div className="w-full rounded-2xl rounded-bl-sm border bg-muted/50 px-4 py-3 shadow-sm">
            <MarkdownContent content={content} />
          </div>
          {children}
        </div>
      </div>
    </div>
  )
}
