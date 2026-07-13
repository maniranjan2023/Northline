import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface Props {
  title: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  className?: string
  headerExtra?: ReactNode
}

export function CollapsiblePanel({ title, children, defaultOpen = false, className, headerExtra }: Props) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="flex min-w-0 flex-1 items-center gap-2 text-base">{title}</CardTitle>
        <div className="flex shrink-0 items-center gap-2">
          {headerExtra}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? 'Hide' : 'Show'}
            <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
          </Button>
        </div>
      </CardHeader>
      {open && <CardContent className="pt-0">{children}</CardContent>}
    </Card>
  )
}
