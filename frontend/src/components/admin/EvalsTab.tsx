import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { getEvalCapabilities, getEvalJob, getEvalResults, startEvalRun } from '@/api/client'
import type {
  EvalCapabilities,
  EvalJobResponse,
  EvalResultRow,
  EvalResultsResponse,
  EvalSuiteKey,
  EvalSuiteRequest,
  EvalSuiteResults,
  SuiteRunStatus,
} from '@/api/types'
import {
  AdminDataTable,
  AdminEmptyState,
  AdminMonoCell,
  AdminStatCard,
  AdminTextCell,
  formatAdminDate,
} from '@/components/admin/admin-shared'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TableCell, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

type EvalViewTab = EvalSuiteKey

const SUITE_TABS: { id: EvalViewTab; label: string; description: string; metrics: number }[] = [
  {
    id: 'ci',
    label: 'CI',
    description: 'Guardrail alignment, prompt injection block, router intent',
    metrics: 3,
  },
  {
    id: 'single_turn',
    label: 'Single-turn',
    description: 'Task completion, tool correctness, plan adherence, plan quality, argument correctness',
    metrics: 5,
  },
  {
    id: 'multi_turn',
    label: 'Multi-turn',
    description: 'Knowledge retention, turn relevancy, faithfulness, contextual recall, goal accuracy',
    metrics: 5,
  },
]

const RUN_OPTIONS: { suite: EvalSuiteRequest; label: string; hint: string }[] = [
  { suite: 'all', label: 'Run all 13 metrics', hint: 'CI → Single-turn → Multi-turn (~30–60 min live)' },
  { suite: 'ci', label: 'Run CI only', hint: 'Fast custom checks (~2 min)' },
  { suite: 'single_turn', label: 'Run single-turn', hint: '5 DeepEval agent metrics (live graph)' },
  { suite: 'multi_turn', label: 'Run multi-turn', hint: '5 DeepEval conversation metrics (live graph)' },
]

interface Props {
  adminKey: string
}

function statusIcon(status: SuiteRunStatus) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="size-4 text-emerald-600" />
    case 'failed':
      return <XCircle className="size-4 text-destructive" />
    case 'running':
      return <Loader2 className="size-4 animate-spin text-primary" />
    case 'skipped':
      return <CircleDashed className="size-4 text-muted-foreground" />
    default:
      return <Clock3 className="size-4 text-muted-foreground" />
  }
}

function PassFailBadge({ passed }: { passed: boolean }) {
  return (
    <Badge variant={passed ? 'secondary' : 'destructive'} className="font-mono text-[11px] uppercase">
      {passed ? 'Pass' : 'Fail'}
    </Badge>
  )
}

function SuiteResultsPanel({ suite, data }: { suite: EvalViewTab; data: EvalSuiteResults | null }) {
  const tabMeta = SUITE_TABS.find((item) => item.id === suite)

  if (!data || data.total === 0) {
    return (
      <AdminEmptyState
        message={`No ${tabMeta?.label ?? suite} results yet. Run evals to populate this tab.`}
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <AdminStatCard
          label="Cases passed"
          value={`${data.passed}/${data.total}`}
          hint={data.run_at ? `Last run ${formatAdminDate(data.run_at)}` : undefined}
          icon={<CheckCircle2 className="size-4" />}
        />
        <AdminStatCard
          label="Metrics tracked"
          value={data.metrics_summary.length}
          hint={`${tabMeta?.metrics ?? '—'} metric types in this suite`}
          icon={<CircleDashed className="size-4" />}
        />
        <AdminStatCard
          label="Pass rate"
          value={`${Math.round((data.passed / Math.max(data.total, 1)) * 100)}%`}
          hint={data.suite_label}
          icon={<Clock3 className="size-4" />}
        />
      </div>

      <Card className="overflow-hidden shadow-sm">
        <CardHeader className="border-b bg-muted/20 pb-4">
          <CardTitle className="text-base">Metric summary</CardTitle>
          <CardDescription>Grouped pass/fail counts per eval metric.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <AdminDataTable columns={['Metric', 'Passed', 'Total', 'Pass rate']}>
            {data.metrics_summary.map((metric) => (
              <TableRow key={metric.metric_name}>
                <TableCell className="px-4 font-medium">{metric.metric_name}</TableCell>
                <TableCell className="px-4">{metric.passed}</TableCell>
                <TableCell className="px-4">{metric.total}</TableCell>
                <TableCell className="px-4 font-mono text-sm">
                  {(metric.pass_rate * 100).toFixed(0)}%
                </TableCell>
              </TableRow>
            ))}
          </AdminDataTable>
        </CardContent>
      </Card>

      <Card className="overflow-hidden shadow-sm">
        <CardHeader className="border-b bg-muted/20 pb-4">
          <CardTitle className="text-base">Detailed results</CardTitle>
          <CardDescription>Every golden case with score, threshold, and judge reason.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <AdminDataTable columns={['Metric', 'Case', 'Result', 'Score', 'Threshold', 'Reason']}>
            {data.rows.map((row: EvalResultRow, index) => (
              <TableRow key={`${row.case_id}-${row.metric_name}-${index}`}>
                <TableCell className="px-4 text-sm">{row.metric_name}</TableCell>
                <AdminMonoCell value={row.case_id} />
                <TableCell className="px-4">
                  <PassFailBadge passed={row.passed} />
                </TableCell>
                <TableCell className="px-4 font-mono text-sm">
                  {row.score != null ? row.score.toFixed(2) : '—'}
                </TableCell>
                <TableCell className="px-4 font-mono text-sm">
                  {row.threshold != null ? row.threshold.toFixed(2) : '—'}
                </TableCell>
                <AdminTextCell value={row.reason || row.input_preview} className="min-w-[14rem]" />
              </TableRow>
            ))}
          </AdminDataTable>
        </CardContent>
      </Card>
    </div>
  )
}

export function EvalsTab({ adminKey }: Props) {
  const [capabilities, setCapabilities] = useState<EvalCapabilities | null>(null)
  const [results, setResults] = useState<EvalResultsResponse | null>(null)
  const [activeJob, setActiveJob] = useState<EvalJobResponse | null>(null)
  const [activeView, setActiveView] = useState<EvalViewTab>('ci')
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState<EvalSuiteRequest | null>(null)

  const isRunning = activeJob?.status === 'queued' || activeJob?.status === 'running'

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [caps, res] = await Promise.all([
        getEvalCapabilities(adminKey),
        getEvalResults(adminKey),
      ])
      setCapabilities(caps)
      setResults(res)

      if (res.active_job_id) {
        const job = await getEvalJob(adminKey, res.active_job_id)
        setActiveJob(job)
      } else {
        setActiveJob(null)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load eval data')
    } finally {
      setLoading(false)
    }
  }, [adminKey])

  useEffect(() => {
    void loadData()
  }, [loadData])

  useEffect(() => {
    if (!activeJob || !isRunning) return

    const interval = setInterval(async () => {
      try {
        const job = await getEvalJob(adminKey, activeJob.job_id)
        setActiveJob(job)
        if (job.status === 'completed' || job.status === 'failed') {
          const res = await getEvalResults(adminKey)
          setResults(res)
          if (job.status === 'completed') {
            toast.success('Eval run finished')
          } else {
            toast.error('Eval run finished with failures')
          }
        }
      } catch {
        // keep polling quietly
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [activeJob, adminKey, isRunning])

  async function handleRun(suite: EvalSuiteRequest) {
    setStarting(suite)
    try {
      const started = await startEvalRun(adminKey, suite)
      const job = await getEvalJob(adminKey, started.job_id)
      setActiveJob(job)
      toast.message(started.message)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not start eval run')
    } finally {
      setStarting(null)
    }
  }

  const suiteData = useMemo(() => {
    if (!results) return null
    return {
      ci: results.ci,
      single_turn: results.single_turn,
      multi_turn: results.multi_turn,
    } satisfies Record<EvalViewTab, EvalSuiteResults | null>
  }, [results])

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-xl border bg-muted/10 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex max-w-2xl flex-col gap-2">
            <h2 className="text-lg font-semibold tracking-tight">Evaluation suite</h2>
            <p className="text-sm text-muted-foreground">
              Run all 13 metrics from the admin console: 3 CI checks plus 10 DeepEval metrics across
              single-turn and multi-turn suites. Results are written to JSON for this dashboard.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => loadData()} disabled={loading || isRunning}>
            <RefreshCw data-icon="inline-start" className={cn(loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {!capabilities?.eval_deps_installed && (
          <Alert className="mt-4">
            <AlertCircle data-icon="inline-start" />
            <AlertTitle>Evals Run is not enabled on this server</AlertTitle>
            <AlertDescription className="flex flex-col gap-2">
              <span>
                Chat and the rest of Admin still work. To enable the Run buttons, install{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">pytest</code> and{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">deepeval</code> on the backend
                and redeploy.
              </span>
              <span>
                <strong>Local:</strong>{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">pip install -r requirements-dev.txt</code>
              </span>
              <span>
                <strong>Render build:</strong>{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs break-all">
                  pip install -r requirements.txt && pip install ./aviationstack-mcp-main && pip install -r
                  requirements-evals.txt
                </code>
              </span>
              <span className="text-muted-foreground">
                Live suites (single-turn / multi-turn) can take 30–60 minutes and need your API keys. Prefer
                starting with <strong>Run CI only</strong> first.
              </span>
            </AlertDescription>
          </Alert>
        )}
      </div>

      <Card className="shadow-sm">
        <CardHeader className="border-b bg-muted/20">
          <CardTitle className="text-base">Run controls</CardTitle>
          <CardDescription>
            Live suites need <code className="text-xs">EVAL_LIVE=1</code>, API keys, MCP, and database.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
          {RUN_OPTIONS.map((option) => (
            <div
              key={option.suite}
              className="flex flex-col gap-3 rounded-lg border bg-background p-4 shadow-xs"
            >
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium">{option.label}</p>
                <p className="text-xs text-muted-foreground">{option.hint}</p>
              </div>
              <Button
                size="sm"
                onClick={() => handleRun(option.suite)}
                disabled={
                  !capabilities?.eval_deps_installed ||
                  isRunning ||
                  starting !== null
                }
              >
                {starting === option.suite ? (
                  <Loader2 data-icon="inline-start" className="animate-spin" />
                ) : (
                  <Play data-icon="inline-start" />
                )}
                {starting === option.suite ? 'Starting…' : 'Start run'}
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      {activeJob && (
        <Card className="shadow-sm">
          <CardHeader className="border-b bg-muted/20">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">Run progress</CardTitle>
              <Badge variant={activeJob.status === 'failed' ? 'destructive' : 'secondary'}>
                {activeJob.status}
              </Badge>
              <span className="text-xs text-muted-foreground font-mono">{activeJob.job_id}</span>
            </div>
            <CardDescription>
              Started {formatAdminDate(activeJob.started_at ?? activeJob.created_at)}
              {activeJob.finished_at ? ` · Finished ${formatAdminDate(activeJob.finished_at)}` : ''}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 p-4">
            <div className="grid gap-3 md:grid-cols-3">
              {SUITE_TABS.map((tab) => {
                const progress = activeJob.progress[tab.id]
                return (
                  <div
                    key={tab.id}
                    className="flex flex-col gap-2 rounded-lg border p-4"
                  >
                    <div className="flex items-center gap-2">
                      {statusIcon(progress.status)}
                      <span className="text-sm font-medium">{tab.label}</span>
                      <Badge variant="outline" className="ml-auto capitalize">
                        {progress.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{tab.description}</p>
                    {progress.total != null && (
                      <p className="text-sm font-mono">
                        {progress.passed ?? 0}/{progress.total} passed
                        {progress.duration_seconds != null
                          ? ` · ${progress.duration_seconds}s`
                          : ''}
                      </p>
                    )}
                    {progress.error && (
                      <p className="text-xs text-destructive line-clamp-3">{progress.error}</p>
                    )}
                  </div>
                )
              })}
            </div>

            {activeJob.error && (
              <Alert variant="destructive">
                <AlertDescription>{activeJob.error}</AlertDescription>
              </Alert>
            )}

            {activeJob.log_tail && (
              <div className="rounded-lg border bg-muted/30 p-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Log tail
                </p>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
                  {activeJob.log_tail}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="overflow-hidden shadow-sm">
        <CardHeader className="border-b bg-muted/20 pb-0">
          <CardDescription className="pb-3">
            Browse latest results by suite. Each tab shows metric summaries and per-case details.
          </CardDescription>
          <div role="tablist" aria-label="Eval result suites" className="flex flex-wrap gap-1">
            {SUITE_TABS.map((tab) => {
              const isActive = activeView === tab.id
              const count = suiteData?.[tab.id]?.total ?? 0
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveView(tab.id)}
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
          {loading && !suiteData ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading eval results…
            </div>
          ) : (
            <SuiteResultsPanel suite={activeView} data={suiteData?.[activeView] ?? null} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
