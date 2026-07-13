import { useMemo, useState } from 'react'
import type { LessonSummary } from '@/api/types'
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
  lessons: LessonSummary[]
  loading?: boolean
}

export function LessonsTab({ lessons, loading }: Props) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return lessons
    return lessons.filter(
      (item) =>
        item.lesson.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query) ||
        (item.destination ?? '').toLowerCase().includes(query) ||
        item.lesson_id.toLowerCase().includes(query),
    )
  }, [lessons, search])

  return (
    <AdminTableShell
      title="Lesson book"
      description="Evidence-backed rules promoted into the live lesson store"
      search={search}
      onSearchChange={setSearch}
      searchPlaceholder="Search lesson text, category, destination…"
      count={filtered.length}
    >
      {filtered.length === 0 ? (
        <AdminEmptyState message="No lessons yet. Lessons are created from reviewer findings and approved proposals." />
      ) : (
        <AdminDataTable
          columns={['Lesson', 'Category', 'Confidence', 'Seen', 'Destination', 'Status', 'ID']}
          loading={loading}
        >
          {filtered.map((lesson) => (
            <TableRow key={lesson.lesson_id}>
              <AdminTextCell value={lesson.lesson} className="min-w-[16rem]" />
              <TableCell className="px-4">
                <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium">{lesson.category}</span>
              </TableCell>
              <TableCell className="px-4">
                <span className="font-mono text-sm">{(lesson.confidence * 100).toFixed(0)}%</span>
              </TableCell>
              <TableCell className="px-4 text-center">{lesson.times_seen}</TableCell>
              <TableCell className="px-4">{lesson.destination ?? '—'}</TableCell>
              <TableCell className="px-4">
                <StatusBadge status={lesson.status} />
              </TableCell>
              <AdminMonoCell value={lesson.lesson_id} />
            </TableRow>
          ))}
        </AdminDataTable>
      )}
    </AdminTableShell>
  )
}
