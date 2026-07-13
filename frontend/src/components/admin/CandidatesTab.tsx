import { useMemo, useState } from 'react'
import type { CandidateSummary } from '@/api/types'
import { TableCell, TableRow } from '@/components/ui/table'
import {
  AdminDataTable,
  AdminEmptyState,
  AdminMonoCell,
  AdminTableShell,
  AdminTextCell,
  StatusBadge,
} from '@/components/admin/admin-shared'

interface Props {
  candidates: CandidateSummary[]
  loading?: boolean
}

export function CandidatesTab({ candidates, loading }: Props) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return candidates
    return candidates.filter(
      (item) =>
        item.problem.toLowerCase().includes(query) ||
        item.suggested_lesson.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query) ||
        item.status.toLowerCase().includes(query),
    )
  }, [candidates, search])

  return (
    <AdminTableShell
      title="Lesson candidates"
      description="Recurring problems awaiting promotion into the lesson book"
      search={search}
      onSearchChange={setSearch}
      searchPlaceholder="Search problem, suggested lesson, category…"
      count={filtered.length}
    >
      {filtered.length === 0 ? (
        <AdminEmptyState message="No candidates match your filters. Candidates accumulate from reviewer findings across trips." />
      ) : (
        <AdminDataTable
          columns={['Problem', 'Suggested lesson', 'Category', 'Confidence', 'Seen', 'Status', 'ID']}
          loading={loading}
        >
          {filtered.map((candidate) => (
            <TableRow key={candidate.candidate_id}>
              <AdminTextCell value={candidate.problem} />
              <AdminTextCell value={candidate.suggested_lesson} />
              <TableCell className="px-4">
                <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{candidate.category}</span>
              </TableCell>
              <TableCell className="px-4 font-mono text-sm">{(candidate.confidence * 100).toFixed(0)}%</TableCell>
              <TableCell className="px-4 text-center">{candidate.times_seen}</TableCell>
              <TableCell className="px-4">
                <StatusBadge status={candidate.status} />
              </TableCell>
              <AdminMonoCell value={candidate.candidate_id} />
            </TableRow>
          ))}
        </AdminDataTable>
      )}
    </AdminTableShell>
  )
}
