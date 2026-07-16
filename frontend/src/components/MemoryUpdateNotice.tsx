import { Brain, X } from 'lucide-react'
import { useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { MemoryUpdateInfo } from '@/api/types'

interface Props {
  update: MemoryUpdateInfo
  open: boolean
  onOpenChange: (open: boolean) => void
}

function formatValue(value: string) {
  if (!value) return '—'
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('-')
}

export function MemoryUpdateNotice({ update, open, onOpenChange }: Props) {
  const isAdded = update.action === 'added'
  const label = isAdded ? 'Memory added' : 'Memory updated'
  const chipClass = isAdded
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-300'
    : 'border-amber-500/30 bg-amber-500/10 text-amber-800 hover:bg-amber-500/20 dark:text-amber-300'

  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onOpenChange(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onOpenChange])

  return (
    <>
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        className={`group inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${chipClass}`}
      >
        <Brain className="size-3.5" />
        <span>{label}</span>
        <span className="opacity-70 group-hover:opacity-100">· tap for details</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-[1px]"
          onClick={() => onOpenChange(false)}
          role="presentation"
        >
          <Card
            className="w-full max-w-md shadow-xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="memory-update-title"
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Brain className="size-4 text-emerald-600" />
                    <Badge variant="secondary">{label}</Badge>
                  </div>
                  <CardTitle id="memory-update-title" className="text-lg">
                    {update.attribute_label}
                  </CardTitle>
                  <CardDescription>
                    {isAdded
                      ? 'Saved to your profile and will be used in future trip plans.'
                      : 'Your latest preference replaced the previous value.'}
                  </CardDescription>
                </div>
                <Button variant="ghost" size="icon-sm" onClick={() => onOpenChange(false)} aria-label="Close">
                  <X className="size-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {!isAdded && update.previous_value && (
                <div className="rounded-lg border bg-muted/40 px-3 py-2.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Previous</p>
                  <p className="mt-1 font-medium">{formatValue(update.previous_value)}</p>
                </div>
              )}
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5">
                <p className="text-xs font-medium uppercase tracking-wide text-emerald-700/80 dark:text-emerald-300/80">
                  {isAdded ? 'Saved as' : 'Updated to'}
                </p>
                <p className="mt-1 text-base font-semibold text-emerald-800 dark:text-emerald-200">
                  {formatValue(update.new_value)}
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                Stored in your structured profile memory. Trip planning and follow-ups will treat this as your latest
                confirmed preference.
              </p>
              <Button className="w-full" onClick={() => onOpenChange(false)}>
                Got it
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
