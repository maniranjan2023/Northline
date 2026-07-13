import type { ReactNode } from 'react'
import { Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

export function formatAdminDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function StatusBadge({
  status,
  className,
}: {
  status: string
  className?: string
}) {
  const normalized = status.toLowerCase()
  const variant =
    normalized === 'pending' || normalized === 'open'
      ? 'outline'
      : normalized === 'approved' || normalized === 'active' || normalized === 'promoted'
        ? 'secondary'
        : normalized === 'rejected' || normalized === 'inactive'
          ? 'destructive'
          : 'outline'

  return (
    <Badge variant={variant} className={cn('capitalize', className)}>
      {status.replaceAll('_', ' ')}
    </Badge>
  )
}

export function AdminStatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string
  value: number | string
  hint?: string
  icon: ReactNode
}) {
  return (
    <Card className="shadow-sm">
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
      </CardContent>
    </Card>
  )
}

export function AdminTableShell({
  title,
  description,
  search,
  onSearchChange,
  searchPlaceholder = 'Search…',
  count,
  children,
  className,
}: {
  title: string
  description?: string
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
  count: number
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('overflow-hidden shadow-sm', className)}>
      <CardHeader className="border-b bg-muted/20 pb-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">{title}</CardTitle>
              <Badge variant="secondary">{count}</Badge>
            </div>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              className="pl-9"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  )
}

export function AdminTableLoading({ columns }: { columns: number }) {
  return (
    <div className="flex flex-col gap-2 p-4">
      {Array.from({ length: 5 }).map((_, row) => (
        <div key={row} className="flex gap-3">
          {Array.from({ length: columns }).map((__, col) => (
            <Skeleton key={col} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function AdminEmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <p className="text-sm font-medium text-foreground">No records found</p>
      <p className="max-w-sm text-sm text-muted-foreground">{message}</p>
    </div>
  )
}

export function AdminDataTable({
  columns,
  children,
  loading,
}: {
  columns: string[]
  children: ReactNode
  loading?: boolean
}) {
  if (loading) return <AdminTableLoading columns={columns.length} />

  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          {columns.map((column) => (
            <TableHead key={column} className="h-11 px-4 text-xs font-semibold uppercase tracking-wide">
              {column}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>{children}</TableBody>
    </Table>
  )
}

export function AdminMonoCell({
  value,
  className,
}: {
  value?: string | null
  className?: string
}) {
  if (!value) return <TableCell className="px-4 text-muted-foreground">—</TableCell>
  return (
    <TableCell className={cn('max-w-[10rem] px-4 font-mono text-xs', className)} title={value}>
      <span className="block truncate">{value}</span>
    </TableCell>
  )
}

export function AdminTextCell({
  value,
  className,
}: {
  value?: string | null
  className?: string
}) {
  if (!value) return <TableCell className="px-4 text-muted-foreground">—</TableCell>
  return (
    <TableCell className={cn('max-w-md px-4', className)} title={value}>
      <span className="line-clamp-2 text-sm">{value}</span>
    </TableCell>
  )
}
