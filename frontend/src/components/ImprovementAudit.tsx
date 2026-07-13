import type { AgentPayload } from '@/api/types'
import { CollapsiblePanel } from '@/components/CollapsiblePanel'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, Sparkles } from 'lucide-react'

interface Props {
  agents?: AgentPayload
}

export function ImprovementAudit({ agents }: Props) {
  if (!agents) return null
  const lessons = agents.lessons_loaded ?? []
  const review = agents.review_summary ?? {}
  const findings = review.findings ?? []

  if (!lessons.length && !findings.length && review.problems_found === undefined) {
    return null
  }

  return (
    <CollapsiblePanel
      className="border-dashed"
      defaultOpen={false}
      title={
        <>
          <Sparkles className="size-4 text-primary" />
          Improvement audit
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {lessons.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Lessons used for this plan</p>
            <ul className="flex flex-col gap-2">
              {lessons.map((lesson) => (
                <li key={lesson.lesson_id} className="rounded-lg border bg-muted/40 px-3 py-2 text-sm">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{lesson.category}</Badge>
                    <span className="text-xs text-muted-foreground">confidence {lesson.confidence.toFixed(2)}</span>
                  </div>
                  {lesson.lesson}
                </li>
              ))}
            </ul>
          </div>
        )}
        {findings.length > 0 ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Reviewer findings</p>
            {findings.map((finding, index) => (
              <Alert key={index} variant="destructive">
                <AlertTitle>{finding.problem}</AlertTitle>
                <AlertDescription>{finding.suggested_lesson}</AlertDescription>
              </Alert>
            ))}
          </div>
        ) : (
          review.problems_found === 0 && (
            <Alert>
              <CheckCircle2 className="size-4" />
              <AlertTitle>Looks good</AlertTitle>
              <AlertDescription>Reviewer found no major issues in this itinerary.</AlertDescription>
            </Alert>
          )
        )}
      </div>
    </CollapsiblePanel>
  )
}
