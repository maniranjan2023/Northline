import { Plane, User } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return (parts[0]?.slice(0, 2) ?? 'U').toUpperCase()
}

export function UserAvatar({ name, className }: { name: string; className?: string }) {
  return (
    <Avatar size="lg" className={cn('ring-2 ring-primary/20 shadow-md', className)}>
      <AvatarFallback className="bg-gradient-to-br from-primary to-primary/70 text-sm font-semibold text-primary-foreground">
        {name.trim() ? (
          initials(name)
        ) : (
          <User className="size-4" />
        )}
      </AvatarFallback>
    </Avatar>
  )
}

export function AssistantAvatar({ className }: { className?: string }) {
  return (
    <Avatar size="lg" className={cn('ring-2 ring-border shadow-sm', className)}>
      <AvatarFallback className="bg-gradient-to-br from-muted to-muted/50 text-foreground">
        <Plane className="size-4 text-primary" />
      </AvatarFallback>
    </Avatar>
  )
}
