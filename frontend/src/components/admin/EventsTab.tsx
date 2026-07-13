import { useMemo, useState } from 'react'
import type { ImprovementEvent } from '@/api/types'
import { TableCell, TableRow } from '@/components/ui/table'
import {
  AdminDataTable,
  AdminEmptyState,
  AdminMonoCell,
  AdminTableShell,
  AdminTextCell,
  formatAdminDate,
} from '@/components/admin/admin-shared'

interface Props {
  events: ImprovementEvent[]
  loading?: boolean
}

function summarizePayload(payload: Record<string, unknown>) {
  const keys = Object.keys(payload)
  if (keys.length === 0) return '—'
  const preview = keys.slice(0, 3).map((key) => `${key}: ${String(payload[key]).slice(0, 40)}`)
  return preview.join(' · ')
}

export function EventsTab({ events, loading }: Props) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return events
    return events.filter(
      (item) =>
        item.event_type.toLowerCase().includes(query) ||
        (item.user_id ?? '').toLowerCase().includes(query) ||
        (item.run_id ?? '').toLowerCase().includes(query) ||
        JSON.stringify(item.payload).toLowerCase().includes(query),
    )
  }, [events, search])

  return (
    <AdminTableShell
      title="Improvement audit log"
      description="Chronological record of lesson promotions, reviews, and pipeline events"
      search={search}
      onSearchChange={setSearch}
      searchPlaceholder="Search event type, user, run id, payload…"
      count={filtered.length}
    >
      {filtered.length === 0 ? (
        <AdminEmptyState message="No events recorded yet. Events appear as the self-improvement loop runs." />
      ) : (
        <AdminDataTable
          columns={['Event', 'User', 'Run', 'Thread', 'Summary', 'When']}
          loading={loading}
        >
          {filtered.map((event, index) => (
            <TableRow key={event.event_id ?? `${event.event_type}-${index}`}>
              <TableCell className="px-4">
                <span className="rounded-md border bg-background px-2 py-0.5 font-mono text-xs">
                  {event.event_type}
                </span>
              </TableCell>
              <TableCell className="px-4 text-sm">{event.user_id ?? '—'}</TableCell>
              <AdminMonoCell value={event.run_id} />
              <AdminMonoCell value={event.thread_id} />
              <AdminTextCell value={summarizePayload(event.payload)} />
              <TableCell className="px-4 text-sm text-muted-foreground">
                {formatAdminDate(event.created_at)}
              </TableCell>
            </TableRow>
          ))}
        </AdminDataTable>
      )}
    </AdminTableShell>
  )
}
