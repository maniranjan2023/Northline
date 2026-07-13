import { useMemo, useState } from 'react'
import { CheckCircle2, FileJson2, XCircle } from 'lucide-react'
import type { ProposalDetail, ProposalSummary } from '@/api/types'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TableCell, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import {
  AdminDataTable,
  AdminEmptyState,
  AdminMonoCell,
  AdminTableShell,
  AdminTextCell,
  formatAdminDate,
  StatusBadge,
} from '@/components/admin/admin-shared'
import { cn } from '@/lib/utils'

interface Props {
  proposals: ProposalSummary[]
  selected: ProposalDetail | null
  onSelect: (id: string) => void
  onReview: (action: 'approve' | 'reject') => void
  dataset: string
  onDatasetChange: (value: string) => void
  note: string
  onNoteChange: (value: string) => void
  loading?: boolean
}

export function ProposalsTab({
  proposals,
  selected,
  onSelect,
  onReview,
  dataset,
  onDatasetChange,
  note,
  onNoteChange,
  loading,
}: Props) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return proposals
    return proposals.filter(
      (item) =>
        item.component.toLowerCase().includes(query) ||
        item.feedback_comment.toLowerCase().includes(query) ||
        item.run_id.toLowerCase().includes(query) ||
        item.review_status.toLowerCase().includes(query),
    )
  }, [proposals, search])

  const pendingCount = proposals.filter((item) => item.review_status === 'pending').length

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
      <AdminTableShell
        title="Trace proposals"
        description={`${pendingCount} pending review · human gate before golden datasets`}
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search component, feedback, run id…"
        count={filtered.length}
      >
        {filtered.length === 0 ? (
          <AdminEmptyState
            message={
              search.trim()
                ? 'No proposals match your search.'
                : 'No proposals yet. New proposals appear when users submit negative feedback.'
            }
          />
        ) : (
          <AdminDataTable columns={['Status', 'Component', 'Run', 'Feedback', 'Created']} loading={loading}>
            {filtered.map((proposal) => (
              <TableRow
                key={proposal.id}
                className={cn(
                  'cursor-pointer',
                  selected?.id === proposal.id && 'bg-primary/5 hover:bg-primary/5',
                )}
                onClick={() => onSelect(proposal.id)}
              >
                <TableCell className="px-4">
                  <StatusBadge status={proposal.review_status} />
                </TableCell>
                <TableCell className="px-4 font-medium">{proposal.component}</TableCell>
                <AdminMonoCell value={proposal.run_id} />
                <AdminTextCell value={proposal.feedback_comment} />
                <TableCell className="px-4 text-sm text-muted-foreground">
                  {formatAdminDate(proposal.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </AdminDataTable>
        )}
      </AdminTableShell>

      <Card className="shadow-sm">
        <CardHeader className="border-b bg-muted/20">
          <CardTitle className="text-base">Review workspace</CardTitle>
          <CardDescription>Inspect evidence, then approve into a dataset or reject.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 p-4">
          {!selected && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/20 px-4 py-12 text-center">
              <FileJson2 className="size-8 text-muted-foreground" />
              <p className="text-sm font-medium">Select a proposal</p>
              <p className="text-xs text-muted-foreground">Click a row to load trace evidence and review controls.</p>
            </div>
          )}

          {selected && (
            <>
              <div className="grid gap-3 rounded-lg border bg-muted/20 p-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-xs text-muted-foreground">Run ID</p>
                  <p className="truncate font-mono text-xs">{selected.run_id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Component</p>
                  <p className="font-medium">{selected.component}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Dataset target</p>
                  <p>{selected.target_dataset}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Status</p>
                  <StatusBadge status={selected.review_status} />
                </div>
                <div className="sm:col-span-2">
                  <p className="text-xs text-muted-foreground">User feedback</p>
                  <p>{selected.feedback_comment || '—'}</p>
                </div>
              </div>

              <Accordion defaultValue={['evidence']}>
                <AccordionItem value="evidence">
                  <AccordionTrigger>Trace evidence (JSON)</AccordionTrigger>
                  <AccordionContent>
                    <ScrollArea className="max-h-56 rounded-md border bg-background p-3">
                      <pre className="text-xs leading-relaxed whitespace-pre-wrap">
                        {JSON.stringify(selected.proposal, null, 2)}
                      </pre>
                    </ScrollArea>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>

              <div className="flex flex-col gap-2">
                <Label>Target dataset</Label>
                <Select value={dataset} onValueChange={(value) => value && onDatasetChange(value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ci">ci</SelectItem>
                    <SelectItem value="nightly">nightly</SelectItem>
                    <SelectItem value="memory">memory</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-2">
                <Label>Reviewer note</Label>
                <Textarea
                  value={note}
                  onChange={(e) => onNoteChange(e.target.value)}
                  placeholder="Optional context for approve/reject decision"
                  rows={3}
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <Button onClick={() => onReview('approve')}>
                  <CheckCircle2 data-icon="inline-start" />
                  Approve
                </Button>
                <Button variant="outline" onClick={() => onReview('reject')}>
                  <XCircle data-icon="inline-start" />
                  Reject
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
