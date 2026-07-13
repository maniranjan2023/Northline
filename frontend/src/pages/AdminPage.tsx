import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  BookOpen,
  FileStack,
  KeyRound,
  Lightbulb,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  getProposal,
  listCandidates,
  listEvents,
  listLessons,
  listProposals,
  reviewProposal,
} from '@/api/client'
import type { CandidateSummary, ImprovementEvent, LessonSummary, ProposalDetail, ProposalSummary } from '@/api/types'
import { AdminStatCard } from '@/components/admin/admin-shared'
import { CandidatesTab } from '@/components/admin/CandidatesTab'
import { EventsTab } from '@/components/admin/EventsTab'
import { LessonsTab } from '@/components/admin/LessonsTab'
import { ProposalsTab } from '@/components/admin/ProposalsTab'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type AdminTab = 'proposals' | 'lessons' | 'candidates' | 'events'

const TAB_ITEMS: { id: AdminTab; label: string }[] = [
  { id: 'proposals', label: 'Proposals' },
  { id: 'lessons', label: 'Lessons' },
  { id: 'candidates', label: 'Candidates' },
  { id: 'events', label: 'Events' },
]

export function AdminPage() {
  const defaultAdminKey = import.meta.env.VITE_ADMIN_API_KEY ?? ''
  const [adminKey, setAdminKey] = useState(localStorage.getItem('NORTHLINE_admin_key') ?? defaultAdminKey)
  const [authenticated, setAuthenticated] = useState(false)
  const [activeTab, setActiveTab] = useState<AdminTab>('lessons')
  const [proposals, setProposals] = useState<ProposalSummary[]>([])
  const [selected, setSelected] = useState<ProposalDetail | null>(null)
  const [lessons, setLessons] = useState<LessonSummary[]>([])
  const [candidates, setCandidates] = useState<CandidateSummary[]>([])
  const [events, setEvents] = useState<ImprovementEvent[]>([])
  const [dataLoaded, setDataLoaded] = useState(false)
  const [note, setNote] = useState('')
  const [dataset, setDataset] = useState('nightly')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const autoUnlockRef = useRef(false)

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

  const counts: Record<AdminTab, number> = {
    proposals: proposals.length,
    lessons: lessons.length,
    candidates: candidates.length,
    events: events.length,
  }

  const stats = useMemo(() => {
    const pendingProposals = proposals.filter((item) => item.review_status === 'pending').length
    const activeLessons = lessons.filter((item) => item.status === 'active').length
    const openCandidates = candidates.filter((item) => item.status !== 'promoted').length
    return {
      pendingProposals,
      activeLessons,
      openCandidates,
      eventCount: events.length,
    }
  }, [proposals, lessons, candidates, events])

  async function fetchAllData(key: string) {
    const [nextProposals, nextLessons, nextCandidates, nextEvents] = await Promise.all([
      listProposals(key),
      listLessons(key),
      listCandidates(key),
      listEvents(key),
    ])
    setProposals(nextProposals)
    setLessons(nextLessons)
    setCandidates(nextCandidates)
    setEvents(nextEvents)
    setDataLoaded(true)
    return { nextProposals, nextLessons }
  }

  async function loadAllData(key: string) {
    setLoading(true)
    try {
      return await fetchAllData(key)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load admin data'
      toast.error(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  async function unlock(key: string) {
    setError('')
    setLoading(true)
    try {
      for (let attempt = 0; attempt < 30; attempt += 1) {
        try {
          const { nextProposals, nextLessons } = await fetchAllData(key)
          setAuthenticated(true)
          setActiveTab(nextProposals.length > 0 ? 'proposals' : nextLessons.length > 0 ? 'lessons' : 'events')
          localStorage.setItem('NORTHLINE_admin_key', key)
          return
        } catch (err) {
          const message = err instanceof Error ? err.message : ''
          const retryable = /8000|backend|unreachable|starting|timed out|502|retrying/i.test(message)
          if (attempt < 29 && retryable) {
            await sleep(2000)
            continue
          }
          setAuthenticated(false)
          setDataLoaded(false)
          if (retryable) {
            setError('Backend is not ready. Run: cd backend then .\\start.ps1 — then click Unlock again.')
          } else {
            setError('Admin authentication failed. Check your API key.')
          }
          return
        }
      }
    } finally {
      setLoading(false)
    }
  }

  async function refreshAll(key: string) {
    try {
      await loadAllData(key)
      toast.success('Data refreshed')
    } catch {
      // loadAllData already toasts
    }
  }

  useEffect(() => {
    if (!adminKey || autoUnlockRef.current) return
    autoUnlockRef.current = true
    void unlock(adminKey)
  }, [adminKey])

  function selectTab(tab: AdminTab) {
    setActiveTab(tab)
    if (tab !== 'proposals') setSelected(null)
  }

  async function openProposal(id: string) {
    try {
      const detail = await getProposal(adminKey, id)
      setSelected(detail)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not load proposal')
    }
  }

  async function handleReview(action: 'approve' | 'reject') {
    if (!selected) return
    try {
      await reviewProposal(adminKey, selected.id, {
        action,
        target_dataset: dataset,
        reviewer_note: note,
      })
      toast.success(`Proposal ${action}d`)
      setSelected(null)
      setNote('')
      await loadAllData(adminKey)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action} proposal`)
    }
  }

  if (!authenticated) {
    return (
      <div className="flex min-h-[calc(100svh-8rem)] items-center justify-center">
        <Card className="w-full max-w-md border-primary/10 shadow-lg">
          <CardHeader className="text-center">
            <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <ShieldCheck className="size-6" />
            </div>
            <CardTitle>Self-improvement console</CardTitle>
            <CardDescription>Unlock the admin workspace to review proposals, lessons, and audit events.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="admin-key">Admin API key</Label>
              <Input
                id="admin-key"
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                placeholder="Matches backend ADMIN_API_KEY"
                onKeyDown={(e) => e.key === 'Enter' && adminKey && unlock(adminKey)}
              />
            </div>
            <Button onClick={() => unlock(adminKey)} disabled={loading || !adminKey}>
              <KeyRound data-icon="inline-start" />
              {loading ? 'Loading workspace…' : 'Unlock workspace'}
            </Button>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-xl border bg-linear-to-br from-primary/5 via-background to-background p-5 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Sparkles className="size-4" />
              </span>
              <h1 className="text-2xl font-semibold tracking-tight">Self-improvement admin</h1>
            </div>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Lessons, events, and proposals load together when you unlock. Use the tabs below to switch views.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => refreshAll(adminKey)} disabled={loading}>
            <RefreshCw data-icon="inline-start" className={cn(loading && 'animate-spin')} />
            Refresh data
          </Button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <AdminStatCard
            label="Pending proposals"
            value={stats.pendingProposals}
            hint={dataLoaded ? `${proposals.length} total` : 'Loading…'}
            icon={<FileStack className="size-4" />}
          />
          <AdminStatCard
            label="Active lessons"
            value={stats.activeLessons}
            hint={dataLoaded ? `${lessons.length} total` : 'Loading…'}
            icon={<BookOpen className="size-4" />}
          />
          <AdminStatCard
            label="Open candidates"
            value={stats.openCandidates}
            hint={dataLoaded ? `${candidates.length} total` : 'Loading…'}
            icon={<Lightbulb className="size-4" />}
          />
          <AdminStatCard
            label="Audit events"
            value={stats.eventCount}
            hint={dataLoaded ? `${events.length} loaded` : 'Loading…'}
            icon={<Activity className="size-4" />}
          />
        </div>
      </div>

      <Card className="overflow-hidden shadow-sm">
        <CardHeader className="border-b bg-muted/20 pb-0">
          <CardDescription className="pb-3">Switch sections to browse proposals, lessons, candidates, and events.</CardDescription>
          <div
            role="tablist"
            aria-label="Admin sections"
            className="flex flex-wrap gap-1 rounded-t-lg"
          >
            {TAB_ITEMS.map((tab) => {
              const isActive = activeTab === tab.id
              const count = counts[tab.id]
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => selectTab(tab.id)}
                  className={cn(
                    'inline-flex items-center gap-2 rounded-t-md border border-b-0 px-4 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'border-border bg-background text-foreground shadow-sm'
                      : 'border-transparent bg-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                  )}
                >
                  {tab.label}
                  <Badge variant={isActive ? 'secondary' : 'outline'}>{count}</Badge>
                </button>
              )
            })}
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6" role="tabpanel">
          {activeTab === 'proposals' && (
            <ProposalsTab
              proposals={proposals}
              selected={selected}
              onSelect={openProposal}
              onReview={handleReview}
              dataset={dataset}
              onDatasetChange={setDataset}
              note={note}
              onNoteChange={setNote}
              loading={loading}
            />
          )}

          {activeTab === 'lessons' && <LessonsTab lessons={lessons} loading={loading} />}

          {activeTab === 'candidates' && <CandidatesTab candidates={candidates} loading={loading} />}

          {activeTab === 'events' && <EventsTab events={events} loading={loading} />}
        </CardContent>
      </Card>
    </div>
  )
}
