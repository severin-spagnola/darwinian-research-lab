import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Activity,
  Award,
  Gauge,
  GitCommitHorizontal,
  Heart,
  Skull,
  Star,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'

const EMPTY_ARRAY = []

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function pct(n01, digits = 1) {
  const v = clamp(safeNumber(n01, 0), 0, 1) * 100
  return `${v.toFixed(digits)}%`
}

function fitnessOf(s) {
  // Try Phase 3 aggregated fitness first
  const p3 = s?.results?.phase3?.aggregated_fitness ?? s?.phase3?.aggregated_fitness
  if (p3 !== null && p3 !== undefined) return safeNumber(p3, 0)

  // Fallback to Phase 2 fitness
  const p2 = s?.results?.fitness ?? s?.fitness
  return safeNumber(p2, 0)
}

function strategyLabel(s) {
  return s?.name ?? s?.graph?.name ?? s?.id ?? 'Strategy'
}

function isElite(s) {
  return s?.state === 'elite'
}

function isDead(s) {
  return s?.state === 'dead'
}

function killCategory(strategy) {
  const verdict = strategy?.results?.red_verdict?.verdict ?? strategy?.red_verdict?.verdict ?? ''
  const failures = strategy?.results?.red_verdict?.failures ?? strategy?.red_verdict?.failures ?? []
  const f = Array.isArray(failures) ? failures.join(' ') : String(failures ?? '')
  const v = String(verdict ?? '')

  if (/DISPERSION/i.test(v) || /HIGH_DISPERSION/i.test(f)) return 'High Dispersion'
  if (/LUCKY/i.test(v) || /LUCKY_SPIKE/i.test(f)) return 'Lucky Spike'
  if (/DRAWDOWN/i.test(v) || /DRAWDOWN_EXCEEDED/i.test(f)) return 'Drawdown Failure'
  if (/SINGLE_REGIME/i.test(v) || /SINGLE_REGIME/i.test(f)) return 'Single Regime'
  return 'Other'
}

function toneForValue({ value, good, warn, inverse = false }) {
  const v = safeNumber(value, 0)
  if (!inverse) {
    if (v >= good) return 'good'
    if (v >= warn) return 'warn'
    return 'bad'
  }
  // Lower is better.
  if (v <= good) return 'good'
  if (v <= warn) return 'warn'
  return 'bad'
}

function ToneChip({ tone, label }) {
  const cls =
    tone === 'good'
      ? 'bg-primary-500/14 text-primary-200 ring-primary-500/25'
      : tone === 'warn'
        ? 'bg-warning-500/14 text-warning-200 ring-warning-500/25'
        : 'bg-danger-500/14 text-danger-200 ring-danger-500/25'

  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${cls}`}>
      {label}
    </span>
  )
}

function StatBar({ label, valueText, fraction01, tone = 'good' }) {
  const w = clamp(safeNumber(fraction01, 0), 0, 1) * 100
  const bar =
    tone === 'good'
      ? 'from-primary-400/70 via-info-400/60 to-primary-300/60'
      : tone === 'warn'
        ? 'from-warning-300/75 via-warning-200/55 to-info-300/35'
        : 'from-danger-400/75 via-danger-300/55 to-warning-300/35'

  return (
    <div className="rounded-2xl border border-border/60 bg-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-text">{label}</div>
        <div className="font-mono text-xs font-semibold tabular-nums text-text-muted">
          {valueText}
        </div>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${bar} transition-[width] duration-200`}
          style={{ width: `${w}%` }}
        />
      </div>
    </div>
  )
}

function SimpleTooltip({ active, payload, label, kind }) {
  if (!active || !payload || payload.length === 0) return null
  const p = payload[0]?.payload ?? {}
  if (kind === 'survival') {
    return (
      <div className="rounded-2xl border border-border/60 bg-bg/95 px-4 py-3 text-xs shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
        <div className="text-[11px] font-semibold text-text-muted">
          Generation {p.gen}
        </div>
        <div className="mt-1 text-sm font-semibold text-text">
          Survival: <span className="font-mono">{p.survivalPct.toFixed(1)}%</span>
        </div>
        <div className="mt-1 text-xs text-text-muted">
          Elite: <span className="font-mono text-text">{p.elitePct.toFixed(1)}%</span>
        </div>
      </div>
    )
  }

  if (kind === 'hist') {
    return (
      <div className="rounded-2xl border border-border/60 bg-bg/95 px-4 py-3 text-xs shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
        <div className="text-[11px] font-semibold text-text-muted">{label}</div>
        <div className="mt-1 text-sm font-semibold text-text">
          Count: <span className="font-mono">{p.count}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-border/60 bg-bg/95 px-4 py-3 text-xs shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
      <div className="text-[11px] font-semibold text-text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-text">
        {safeNumber(p.value, 0).toFixed(3)}
      </div>
    </div>
  )
}

function computeGenerationStats(strategies) {
  const list = Array.isArray(strategies) ? strategies : EMPTY_ARRAY
  const population = list.length
  const elite = list.filter(isElite).length
  const dead = list.filter(isDead).length
  const alive = list.filter((s) => !isDead(s) && !isElite(s)).length
  const survivors = elite + alive

  const killReasons = {}
  list.filter(isDead).forEach((s) => {
    const k = killCategory(s)
    killReasons[k] = (killReasons[k] ?? 0) + 1
  })

  const top = [...list]
    .slice()
    .sort((a, b) => fitnessOf(b) - fitnessOf(a))
    .slice(0, 3)
    .map((s) => ({
      id: s?.id ?? '—',
      label: strategyLabel(s),
      fitness: fitnessOf(s),
      state: s?.state ?? null,
    }))

  const fitnessValues = list.map((s) => fitnessOf(s)).filter((v) => Number.isFinite(v))

  return {
    population,
    elite,
    dead,
    alive,
    survivors,
    survivalRate01: population ? survivors / population : 0,
    eliteRate01: population ? elite / population : 0,
    killReasons,
    topPerformers: top,
    fitnessValues,
  }
}

function computeTrend(allGenerations) {
  const gens = Array.isArray(allGenerations) ? allGenerations : EMPTY_ARRAY
  if (gens.length === 0) return EMPTY_ARRAY

  const isArrayOfArrays = Array.isArray(gens[0])
  if (isArrayOfArrays) {
    return gens.map((gen, idx) => {
      const s = computeGenerationStats(gen)
      const avgFitness =
        gen.length > 0
          ? gen.reduce((acc, x) => acc + fitnessOf(x), 0) / gen.length
          : 0
      return {
        gen: idx,
        survivalPct: s.survivalRate01 * 100,
        elitePct: s.eliteRate01 * 100,
        avgFitness,
      }
    })
  }

  // Fallback: if you pass precomputed stats objects.
  return gens.map((g, idx) => ({
    gen: g.generation ?? g.gen ?? idx,
    survivalPct: safeNumber(g.survival_rate, 0) * 100,
    elitePct: safeNumber(g.elite_rate, 0) * 100,
    avgFitness: safeNumber(g.avg_aggregated_fitness, 0),
  }))
}

function buildHistogram(values, { min = 0, max = 0.2, bins = 8 } = {}) {
  const v = Array.isArray(values) ? values : EMPTY_ARRAY
  const binCount = Math.max(3, Math.round(bins))
  const lo = safeNumber(min, 0)
  const hi = Math.max(lo + 0.0001, safeNumber(max, 0.2))
  const step = (hi - lo) / binCount

  const out = Array.from({ length: binCount }, (_, i) => {
    const a = lo + step * i
    const b = a + step
    const label = `${a.toFixed(2)}–${b.toFixed(2)}`
    return { label, a, b, count: 0 }
  })

  v.forEach((x) => {
    const n = safeNumber(x, NaN)
    if (!Number.isFinite(n)) return
    if (n < lo) return
    const idx = Math.min(binCount - 1, Math.floor((n - lo) / step))
    out[idx].count += 1
  })

  return out.map(({ label, count }) => ({ label, count }))
}

function deriveStrategyMetrics(selectedStrategy) {
  if (!selectedStrategy) return null

  const phase3 = selectedStrategy?.results?.phase3 ?? selectedStrategy?.phase3 ?? null
  const episodes = Array.isArray(phase3?.episodes) ? phase3.episodes : EMPTY_ARRAY
  const penalties = phase3?.penalties ?? {}
  const regimes = phase3?.regime_coverage ?? {}
  const verdict = selectedStrategy?.results?.red_verdict?.verdict ?? selectedStrategy?.red_verdict?.verdict ?? null

  const aggregated = safeNumber(phase3?.aggregated_fitness, 0)
  const median = safeNumber(phase3?.median_fitness, 0)

  const sharpeVals = episodes
    .map((e) => safeNumber(e?.debug_stats?.sharpe, NaN))
    .filter((x) => Number.isFinite(x))
  const sharpe = sharpeVals.length ? sharpeVals.reduce((a, b) => a + b, 0) / sharpeVals.length : null

  const ddVals = episodes
    .map((e) => safeNumber(e?.debug_stats?.max_drawdown, NaN))
    .filter((x) => Number.isFinite(x))
  const maxDrawdown01 = ddVals.length ? Math.max(...ddVals) : null

  const tradePairs = episodes
    .map((e) => {
      const trades = Math.max(0, Math.round(safeNumber(e?.debug_stats?.trades, 0)))
      const win = clamp(safeNumber(e?.debug_stats?.win_rate, NaN), 0, 1)
      return Number.isFinite(win) ? { trades, win } : null
    })
    .filter(Boolean)

  const totalTrades = tradePairs.reduce((acc, x) => acc + x.trades, 0)
  const winRate = totalTrades
    ? tradePairs.reduce((acc, x) => acc + x.win * x.trades, 0) / totalTrades
    : null

  // Volatility heuristic (uses episode tags when present).
  const bucketMap = { low: 0.12, mid: 0.18, high: 0.26 }
  const volVals = episodes
    .map((e) => bucketMap[e?.tags?.vol_bucket] ?? null)
    .filter((x) => x !== null)
  const volatility = volVals.length ? volVals.reduce((a, b) => a + b, 0) / volVals.length : null

  const worstEpisode = episodes.length
    ? Math.min(...episodes.map((e) => safeNumber(e?.fitness, 0)))
    : null

  // Profit factor proxy (deterministic, derived from sharpe + win rate).
  const profitFactor = clamp(
    1.0 + (safeNumber(sharpe, 0.8) * 0.35) + (safeNumber(winRate, 0.5) - 0.5) * 1.8,
    0.6,
    3.2,
  )

  // "Lucky spike" is a verdict category in our system; treat as a penalty for display.
  const luckyPenalty = verdict === 'KILL_LUCKY' ? 0.12 : 0

  return {
    aggregated,
    median,
    sharpe,
    maxDrawdown01,
    volatility,
    totalTrades,
    winRate,
    profitFactor,
    uniqueRegimes: regimes?.unique_regimes ?? null,
    yearsCovered: regimes?.years_covered ?? null,
    worstEpisode,
    penalties: {
      lucky: luckyPenalty,
      dispersion: safeNumber(penalties?.dispersion_penalty, 0),
      drawdown: safeNumber(penalties?.drawdown_penalty, 0),
      churn: safeNumber(penalties?.churn_penalty, 0),
      overfit: safeNumber(penalties?.overfit_penalty, 0),
    },
  }
}

export default function MetricsDashboard({
  generationStats,
  selectedStrategy = null,
  allGenerations = [],
}) {
  const strategies = generationStats?.strategies ?? generationStats?.population ?? generationStats?.items ?? null
  const computed = useMemo(() => computeGenerationStats(strategies), [strategies])
  const trend = useMemo(() => computeTrend(allGenerations), [allGenerations])
  const hist = useMemo(() => buildHistogram(computed.fitnessValues), [computed.fitnessValues])
  const strat = useMemo(() => deriveStrategyMetrics(selectedStrategy), [selectedStrategy])

  const killRows = useMemo(() => {
    const order = ['High Dispersion', 'Lucky Spike', 'Drawdown Failure', 'Single Regime', 'Other']
    const max = Math.max(1, ...order.map((k) => computed.killReasons[k] ?? 0))
    return order
      .map((k) => ({ reason: k, count: computed.killReasons[k] ?? 0, max }))
      .filter((r) => r.count > 0 || r.reason !== 'Other')
  }, [computed.killReasons])

  const avgFitness = useMemo(() => {
    const v = computed.fitnessValues
    if (!v.length) return 0
    return v.reduce((a, b) => a + b, 0) / v.length
  }, [computed.fitnessValues])

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-info-500/14 ring-1 ring-inset ring-info-500/25">
            <Activity className="h-5 w-5 text-info-200" />
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-text-subtle">
              GENERATION METRICS
            </div>
            <div className="mt-0.5 text-sm text-text-muted">
              Population health and selection outcomes
            </div>
          </div>
        </div>

        <div className="rounded-2xl bg-panel-elevated px-3 py-2 text-xs text-text-muted ring-1 ring-inset ring-border/70">
          Avg fitness <span className="font-mono text-text">{avgFitness.toFixed(3)}</span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-text">Population</div>
            <div className="font-mono text-xs text-text-muted">
              {computed.population} strategies
            </div>
          </div>

          <div className="mt-3 grid gap-2">
            <StatBar
              label="Survivors"
              valueText={`${computed.survivors} (${pct(computed.survivalRate01)})`}
              fraction01={computed.survivalRate01}
              tone="good"
            />
            <StatBar
              label="Killed"
              valueText={`${computed.dead} (${pct(computed.population ? computed.dead / computed.population : 0)})`}
              fraction01={computed.population ? computed.dead / computed.population : 0}
              tone="bad"
            />
            <StatBar
              label="Elite"
              valueText={`${computed.elite} (${pct(computed.eliteRate01)})`}
              fraction01={computed.eliteRate01}
              tone="warn"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <Skull className="h-4 w-4 text-danger-200" />
              Kill Reasons
            </div>
            <div className="text-xs text-text-muted">Current generation</div>
          </div>

          <div className="mt-3 space-y-2">
            {killRows.map((r) => {
              const w = (r.count / r.max) * 100
              return (
                <div key={r.reason} className="rounded-2xl border border-border/60 bg-panel p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-semibold text-text">{r.reason}</div>
                    <div className="font-mono text-xs font-semibold tabular-nums text-text-muted">
                      {r.count}
                    </div>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-danger-400/75 via-danger-300/55 to-warning-300/35 transition-[width] duration-200"
                      style={{ width: `${w}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <Award className="h-4 w-4 text-warning-200" />
            Top Performers
          </div>
          <div className="text-xs text-text-muted">Fitness (aggregated)</div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {computed.topPerformers.map((t, idx) => {
            const isTopElite = t.state === 'elite'
            return (
              <div
                key={t.id}
                className={[
                  'rounded-2xl border bg-panel p-4',
                  isTopElite ? 'border-warning-500/25' : 'border-border/60',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs text-text-muted">{idx + 1}.</div>
                    <div className="mt-0.5 truncate text-sm font-semibold text-text">
                      {t.label}
                    </div>
                    <div className="mt-1 truncate font-mono text-[11px] text-text-subtle">
                      {t.id}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[11px] text-text-muted">Fitness</div>
                    <div className="font-mono text-sm font-semibold tabular-nums text-text">
                      {t.fitness.toFixed(3)}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <GitCommitHorizontal className="h-4 w-4 text-info-200" />
              Survival Rate Trend
            </div>
            <div className="text-xs text-text-muted">Across generations</div>
          </div>

          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
                <XAxis
                  dataKey="gen"
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                  tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                  domain={[0, 100]}
                />
                <Tooltip content={<SimpleTooltip kind="survival" />} />
                <Line
                  type="monotone"
                  dataKey="survivalPct"
                  stroke="rgba(16,185,129,0.80)"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive
                />
                <Line
                  type="monotone"
                  dataKey="elitePct"
                  stroke="rgba(251,191,36,0.80)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <Target className="h-4 w-4 text-primary-200" />
              Fitness Distribution
            </div>
            <div className="text-xs text-text-muted">Current generation</div>
          </div>

          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hist} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 10 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                  interval={0}
                  height={42}
                />
                <YAxis
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip content={<SimpleTooltip kind="hist" />} />
                <Bar dataKey="count" fill="rgba(34,211,238,0.55)" radius={[10, 10, 10, 10]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Selected strategy details */}
      {selectedStrategy && strat ? (
        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-3 shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_14px_rgba(16,185,129,0.05)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="text-xs font-semibold tracking-wide text-text-subtle">
                STRATEGY METRICS
              </div>
              <div className="mt-1 truncate text-sm font-semibold text-text">
                {strategyLabel(selectedStrategy)}
              </div>
              <div className="mt-1 truncate font-mono text-[11px] text-text-subtle">
                {selectedStrategy?.id ?? '—'}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ToneChip
                tone={toneForValue({ value: strat.sharpe ?? 0, good: 1.5, warn: 0.8 })}
                label={`Sharpe ${strat.sharpe !== null ? strat.sharpe.toFixed(1) : '—'}`}
              />
              <ToneChip
                tone={toneForValue({
                  value: strat.maxDrawdown01 ?? 1,
                  good: 0.2,
                  warn: 0.3,
                  inverse: true,
                })}
                label={`DD ${strat.maxDrawdown01 !== null ? `${Math.round(strat.maxDrawdown01 * 100)}%` : '—'}`}
              />
              <ToneChip
                tone={toneForValue({
                  value: safeNumber(strat.uniqueRegimes, 0),
                  good: 6,
                  warn: 5,
                })}
                label={`Regimes ${strat.uniqueRegimes ?? '—'}`}
              />
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <Star className="h-4 w-4 text-primary-200" />
                Fitness Metrics
              </div>
              <StatBar
                label="Aggregated"
                valueText={strat.aggregated.toFixed(3)}
                fraction01={clamp(strat.aggregated / 0.15, 0, 1)}
                tone="good"
              />
              <StatBar
                label="Median"
                valueText={strat.median.toFixed(3)}
                fraction01={clamp(strat.median / 0.12, 0, 1)}
                tone="good"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <Gauge className="h-4 w-4 text-warning-200" />
                Risk Metrics
              </div>

              <div className="grid gap-2">
                <StatBar
                  label="Sharpe Ratio"
                  valueText={strat.sharpe !== null ? strat.sharpe.toFixed(2) : '—'}
                  fraction01={strat.sharpe !== null ? clamp(strat.sharpe / 3.0, 0, 1) : 0}
                  tone={toneForValue({ value: strat.sharpe ?? 0, good: 1.5, warn: 0.8 })}
                />
                <StatBar
                  label="Max Drawdown"
                  valueText={strat.maxDrawdown01 !== null ? `-${Math.round(strat.maxDrawdown01 * 100)}%` : '—'}
                  fraction01={strat.maxDrawdown01 !== null ? clamp(strat.maxDrawdown01 / 0.35, 0, 1) : 0}
                  tone={toneForValue({
                    value: strat.maxDrawdown01 ?? 1,
                    good: 0.2,
                    warn: 0.3,
                    inverse: true,
                  })}
                />
                <StatBar
                  label="Volatility"
                  valueText={strat.volatility !== null ? `${Math.round(strat.volatility * 100)}%` : '—'}
                  fraction01={strat.volatility !== null ? clamp(strat.volatility / 0.35, 0, 1) : 0}
                  tone={toneForValue({
                    value: strat.volatility ?? 1,
                    good: 0.15,
                    warn: 0.25,
                    inverse: true,
                  })}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <TrendingUp className="h-4 w-4 text-info-200" />
                Trading Metrics
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-border/60 bg-panel p-4">
                  <div className="text-xs text-text-muted">Total Trades</div>
                  <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-text">
                    {strat.totalTrades}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-panel p-4">
                  <div className="text-xs text-text-muted">Profit Factor</div>
                  <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-text">
                    {strat.profitFactor.toFixed(2)}
                  </div>
                </div>
              </div>
              <StatBar
                label="Win Rate"
                valueText={strat.winRate !== null ? pct(strat.winRate, 0) : '—'}
                fraction01={strat.winRate !== null ? strat.winRate : 0}
                tone={toneForValue({
                  value: strat.winRate ?? 0,
                  good: 0.5,
                  warn: 0.47,
                })}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <Heart className="h-4 w-4 text-primary-200" />
                Robustness
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-border/60 bg-panel p-4">
                  <div className="text-xs text-text-muted">Unique Regimes</div>
                  <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-text">
                    {strat.uniqueRegimes ?? '—'}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-panel p-4">
                  <div className="text-xs text-text-muted">Years Covered</div>
                  <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-text">
                    {strat.yearsCovered ?? '—'}
                  </div>
                </div>
              </div>

              <StatBar
                label="Worst Episode"
                valueText={strat.worstEpisode !== null ? strat.worstEpisode.toFixed(3) : '—'}
                fraction01={strat.worstEpisode !== null ? clamp(strat.worstEpisode / 0.15, 0, 1) : 0}
                tone={toneForValue({
                  value: strat.worstEpisode ?? 0,
                  good: 0.06,
                  warn: 0.04,
                })}
              />
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-text">
              <TrendingDown className="h-4 w-4 text-danger-200" />
              Penalties
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <StatBar
                label="Lucky Spike"
                valueText={strat.penalties.lucky.toFixed(2)}
                fraction01={clamp(strat.penalties.lucky / 0.2, 0, 1)}
                tone={toneForValue({ value: strat.penalties.lucky, good: 0.01, warn: 0.05, inverse: true })}
              />
              <StatBar
                label="Dispersion"
                valueText={strat.penalties.dispersion.toFixed(2)}
                fraction01={clamp(strat.penalties.dispersion / 0.2, 0, 1)}
                tone={toneForValue({ value: strat.penalties.dispersion, good: 0.02, warn: 0.06, inverse: true })}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
