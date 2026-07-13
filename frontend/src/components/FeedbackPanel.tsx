import { useState } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { toast } from 'sonner'
import { submitFeedback } from '@/api/client'
import type { AgentPayload, FeedbackState } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  runId: string
  userQuery?: string
  agents?: AgentPayload
  feedback?: FeedbackState | null
  onFeedback: (feedback: FeedbackState) => void
}

export function FeedbackPanel({ runId, userQuery, agents, feedback, onFeedback }: Props) {
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(false)
  const [showNegativeForm, setShowNegativeForm] = useState(false)

  if (feedback) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Your feedback</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          <p>{feedback.score === 1 ? 'Thanks — marked helpful.' : 'Thanks — issue recorded.'}</p>
          {feedback.diagnosis && <p>Suggested component: <strong className="text-foreground">{feedback.diagnosis}</strong></p>}
          {feedback.proposal_path && <p className="truncate">Draft: {feedback.proposal_path}</p>}
          {feedback.proposal_pending && <p>Trace saved; collector will create the draft test case.</p>}
          {feedback.promoted_lesson_id && <p>Promoted lesson: {feedback.promoted_lesson_id}</p>}
        </CardContent>
      </Card>
    )
  }

  async function handleScore(score: number) {
    if (score === 0 && !comment.trim()) {
      toast.error('Please add a short comment for negative feedback.')
      return
    }
    setLoading(true)
    try {
      const result = await submitFeedback({
        run_id: runId,
        score,
        comment: comment.trim(),
        user_query: userQuery,
        destination: agents?.destination,
      })
      if (!result.submitted) {
        toast.error(result.error ?? 'Feedback could not be sent.')
        return
      }
      onFeedback({
        score,
        comment: comment.trim(),
        diagnosis: result.diagnosis ?? undefined,
        proposal_path: result.proposal_path ?? undefined,
        proposal_pending: result.proposal_pending,
        promoted_lesson_id: result.promoted_lesson_id ?? undefined,
      })
      toast.success(score === 1 ? 'Marked as helpful' : 'Feedback recorded')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Feedback failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Was this helpful?</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" disabled={loading} onClick={() => handleScore(1)}>
            <ThumbsUp data-icon="inline-start" />
            Helpful
          </Button>
          <Button variant="outline" size="sm" disabled={loading} onClick={() => setShowNegativeForm(true)}>
            <ThumbsDown data-icon="inline-start" />
            Not helpful
          </Button>
        </div>
        {showNegativeForm && (
          <div className="flex flex-col gap-2">
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="What went wrong? Example: ignored my budget or dietary preference."
              rows={3}
            />
            <Button variant="destructive" size="sm" disabled={loading || !comment.trim()} onClick={() => handleScore(0)}>
              Submit feedback
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
