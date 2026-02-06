import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  Banknote,
  DollarSign,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'

const MotionDiv = motion.div
const MotionSpan = motion.span

const SERVICES = [
  {
    key: 'you_com_searches',
    label: 'You.com Searches',
    unitCost: 0.002,
    bar: 'from-info-400/70 via-info-300/55 to-info-200/45',
    chip: 'bg-info-500/14 text-info-200 ring-info-500/25',
  },
  {
    key: 'llm_mutations',
    label: 'LLM Mutations',
    unitCost: 0.03,
    bar: 'from-warning-300/75 via-warning-200/55 to-warning-300/35',
    chip: 'bg-warning-500/14 text-warning-200 ring-warning-500/25',
  },
  {
    key: 'validation_runs',
    label: 'Validation Runs',
    unitCost: 0.008,
    bar: 'from-primary-400/70 via-primary-300/55 to-info-400/35',
    chip: 'bg-primary-500/14 text-primary-200 ring-primary-500/25',
  },
]

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function usd(n) {
  return `$${safeNumber(n, 0).toFixed(2)}`
}

function mmss(ts) {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${mm}:${ss}`
}

function pickWeighted(items, weights) {
  const total = weights.reduce((a, b) => a + b, 0)
  if (total <= 0) return items[0]
  let r = Math.random() * total
  for (let i = 0; i < items.length; i += 1) {
    r -= weights[i]
    if (r <= 0) return items[i]
  }
  return items[items.length - 1]
}

function normalizeCostData(costData, totalGenerations) {
  const raw = costData ?? {}

  const breakdown = raw.breakdown ?? {}
  const normalizedBreakdown = {}
  SERVICES.forEach((s) => {
    const row = breakdown[s.key] ?? {}
    normalizedBreakdown[s.key] = {
      calls: Math.max(0, Math.round(safeNumber(row.calls, 0))),
      cost: Math.max(0, safeNumber(row.cost, 0)),
    }
  })

  // Prefer declared total_cost; otherwise sum breakdown costs.
  const sumBreakdown = SERVICES.reduce(
    (acc, s) => acc + safeNumber(normalizedBreakdown[s.key]?.cost, 0),
    0,
  )
  const totalCost = Math.max(0, safeNumber(raw.total_cost, sumBreakdown))

  // Cost per generation (scaled to match totalCost).
  const rawPerGen = Array.isArray(raw.cost_per_generation) ? raw.cost_per_generation : []
  const tg = Math.max(1, Math.round(safeNumber(totalGenerations, rawPerGen.length || 5)))
  const perGen = Array.from({ length: tg }, (_, i) => Math.max(0, safeNumber(rawPerGen[i], 0)))
  const sumPerGen = perGen.reduce((acc, v) => acc + v, 0)
  const scale = sumPerGen > 0 ? totalCost / sumPerGen : 0
  const scaledPerGen = sumPerGen > 0 ? perGen.map((v) => v * scale) : perGen

  const budget = raw.budget ?? raw.budget_usd ?? null

  return {
    totalCost,
    breakdown: normalizedBreakdown,
    perGen: scaledPerGen,
    budget: budget !== null && budget !== undefined ? safeNumber(budget, null) : null,
  }
}

function useAnimatedNumber(target, { durationMs = 450 } = {}) {
  const [value, setValue] = useState(() => safeNumber(target, 0))
  const fromRef = useRef(value)
  const rafRef = useRef(null)

  useEffect(() => {
    const from = safeNumber(fromRef.current, 0)
    const to = safeNumber(target, 0)
    fromRef.current = to

    const start = performance.now()
    const tick = (t) => {
      const p = clamp((t - start) / Math.max(1, durationMs), 0, 1)
      // Ease-out cubic.
      const e = 1 - (1 - p) ** 3
      setValue(from + (to - from) * e)
      if (p < 1) rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [durationMs, target])

  return value
}

function computeBurnRate(series, windowMs = 60_000) {
  if (!Array.isArray(series) || series.length < 2) return { ratePerMin: 0, delta: 0, seconds: 0 }
  const latest = series[series.length - 1]
  const cutoff = latest.ts - windowMs
  let earliest = series[0]
  for (let i = series.length - 1; i >= 0; i -= 1) {
    if (series[i].ts <= cutoff) {
      earliest = series[i]
      break
    }
    earliest = series[i]
  }

  const dt = Math.max(1, latest.ts - earliest.ts)
  const delta = safeNumber(latest.total, 0) - safeNumber(earliest.total, 0)
  const ratePerMin = (delta / dt) * 60_000
  const seconds = dt / 1000
  return { ratePerMin, delta, seconds }
}

function estimateFinalCost({ perGen, currentGen, totalGens, currentTotal }) {
  const tg = Math.max(1, Math.round(safeNumber(totalGens, perGen.length || 5)))
  const cg = clamp(Math.round(safeNumber(currentGen, 0)), 0, tg - 1)
  const remaining = Math.max(0, tg - (cg + 1))

  const completed = perGen.slice(0, Math.max(0, cg)) // completed generations only
  const recent = completed.slice(-3).filter((v) => v > 0)
  const baseline = recent.length
    ? recent.reduce((acc, v) => acc + v, 0) / recent.length
    : completed.length
      ? completed.reduce((acc, v) => acc + v, 0) / completed.length
      : perGen.length
        ? perGen.reduce((acc, v) => acc + v, 0) / perGen.length
        : 0

  const estimatedFinal = safeNumber(currentTotal, 0) + baseline * remaining

  return {
    estimatedFinal,
    method: {
      baselinePerGen: baseline,
      remaining,
      used: recent.length ? `avg(last ${recent.length} completed gens)` : 'avg(completed gens)',
    },
  }
}

function MoneyTooltip({ active, payload, label, kind }) {
  if (!active || !payload || payload.length === 0) return null
  const p = payload[0]?.payload ?? {}

  if (kind === 'perGen') {
    return (
      <div className="rounded-2xl border border-border/60 bg-bg/95 px-4 py-3 text-xs shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
        <div className="text-[11px] font-semibold text-text-muted">Generation {p.gen}</div>
        <div className="mt-1 font-mono text-sm font-semibold text-text">{usd(p.cost)}</div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-border/60 bg-bg/95 px-4 py-3 text-xs shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
      <div className="text-[11px] font-semibold text-text-muted">{mmss(label)}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-text">{usd(p.total)}</div>
    </div>
  )
}

export default function APICostDashboard({
  costData,
  currentGeneration = 0,
  totalGenerations = 5,
  updateInterval = 1000,
}) {
  const base = useMemo(
    () => normalizeCostData(costData, totalGenerations),
    [costData, totalGenerations],
  )

  const [live, setLive] = useState(() => {
    const now = Date.now()
    return {
      totalCost: base.totalCost,
      breakdown: base.breakdown,
      perGen: base.perGen,
      series: [{ ts: now, total: base.totalCost }],
      flashKey: 0,
      lastTick: 0,
      budget: base.budget,
    }
  })

  // Reset baseline when new costData arrives (async to avoid setState-in-effect lint).
  useEffect(() => {
    const t = setTimeout(() => {
      const now = Date.now()
      setLive({
        totalCost: base.totalCost,
        breakdown: base.breakdown,
        perGen: base.perGen,
        series: [{ ts: now, total: base.totalCost }],
        flashKey: 0,
        lastTick: 0,
        budget: base.budget,
      })
    }, 0)
    return () => clearTimeout(t)
  }, [base])

  useEffect(() => {
    const interval = Math.max(250, Math.round(safeNumber(updateInterval, 1000)))

    const t = setInterval(() => {
      const now = Date.now()

      setLive((prev) => {
        const cg = clamp(Math.round(safeNumber(currentGeneration, 0)), 0, Math.max(0, prev.perGen.length - 1))

        // Convert interval to approximate event count; keep it readable and "live".
        const seconds = interval / 1000
        const eventCount = Math.max(0, Math.round((0.8 + Math.random() * 2.2) * seconds))

        // Weight services by current spend share (fallback to unit cost weights).
        const weights = SERVICES.map((s) => {
          const c = safeNumber(prev.breakdown?.[s.key]?.cost, 0)
          return c > 0 ? c : s.unitCost * 10
        })

        const breakdown = { ...prev.breakdown }
        SERVICES.forEach((s) => {
          breakdown[s.key] = { ...breakdown[s.key] }
        })

        let delta = 0
        for (let i = 0; i < eventCount; i += 1) {
          const svc = pickWeighted(SERVICES, weights)
          breakdown[svc.key].calls += 1
          breakdown[svc.key].cost = safeNumber(breakdown[svc.key].cost, 0) + svc.unitCost
          delta += svc.unitCost
        }

        // Small “overhead” noise for non-call costs (logging, orchestration, etc.).
        const overhead = eventCount > 0 ? (0.0004 + Math.random() * 0.0012) * seconds : 0
        delta += overhead

        if (delta <= 0) {
          // Still advance the time series so burn rate stays well-defined.
          const nextSeries = [...prev.series, { ts: now, total: prev.totalCost }].slice(-180)
          return { ...prev, series: nextSeries, lastTick: 0 }
        }

        const totalCost = prev.totalCost + delta
        const perGen = prev.perGen.slice()
        if (perGen.length) perGen[cg] = safeNumber(perGen[cg], 0) + delta

        const series = [...prev.series, { ts: now, total: totalCost }].slice(-180)

        return {
          ...prev,
          totalCost,
          breakdown,
          perGen,
          series,
          lastTick: delta,
          flashKey: prev.flashKey + 1,
        }
      })
    }, interval)

    return () => clearInterval(t)
  }, [currentGeneration, updateInterval])

  const animatedTotal = useAnimatedNumber(live.totalCost, { durationMs: 520 })
  const animatedRate = useAnimatedNumber(
    computeBurnRate(live.series).ratePerMin,
    { durationMs: 520 },
  )

  const burn = useMemo(() => computeBurnRate(live.series), [live.series])
  const trendUp = burn.ratePerMin > 0.0001

  const breakdownRows = useMemo(() => {
    const total = Math.max(0.000001, live.totalCost)
    return SERVICES.map((s) => {
      const row = live.breakdown?.[s.key] ?? { calls: 0, cost: 0 }
      const cost = Math.max(0, safeNumber(row.cost, 0))
      const calls = Math.max(0, Math.round(safeNumber(row.calls, 0)))
      const pct = clamp((cost / total) * 100, 0, 100)
      return { ...s, calls, cost, pct }
    }).sort((a, b) => b.cost - a.cost)
  }, [live.breakdown, live.totalCost])

  const perGenData = useMemo(() => {
    const tg = Math.max(1, Math.round(safeNumber(totalGenerations, live.perGen.length || 5)))
    const arr = Array.from({ length: tg }, (_, i) => ({
      gen: i,
      cost: safeNumber(live.perGen[i], 0),
      isCurrent: i === Math.round(safeNumber(currentGeneration, 0)),
    }))
    return arr
  }, [currentGeneration, live.perGen, totalGenerations])

  const seriesData = useMemo(() => {
    return live.series.map((p) => ({ ts: p.ts, total: p.total }))
  }, [live.series])

  const estimate = useMemo(() => {
    return estimateFinalCost({
      perGen: live.perGen,
      currentGen: currentGeneration,
      totalGens: totalGenerations,
      currentTotal: live.totalCost,
    })
  }, [currentGeneration, live.perGen, live.totalCost, totalGenerations])

  const overBudget =
    live.budget !== null &&
    live.budget !== undefined &&
    (live.totalCost > live.budget || estimate.estimatedFinal > live.budget)

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-warning-500/14 ring-1 ring-inset ring-warning-500/25">
            <Banknote className="h-5 w-5 text-warning-200" />
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-text-subtle">
              API COST TRACKER
            </div>
            <div className="mt-0.5 text-sm text-text-muted">
              Live burn rate and cost attribution
            </div>
          </div>
        </div>

        {live.budget !== null && live.budget !== undefined ? (
          <div
            className={[
              'rounded-2xl px-3 py-2 text-xs font-semibold ring-1 ring-inset',
              overBudget
                ? 'bg-danger-500/14 text-danger-100 ring-danger-500/25'
                : 'bg-panel-elevated text-text ring-border/70',
            ].join(' ')}
          >
            Budget: <span className="font-mono">{usd(live.budget)}</span>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <MotionDiv
          key={live.flashKey}
          initial={{
            boxShadow:
              '0 0 0 1px rgba(34,211,238,0.06), 0 0 30px rgba(16,185,129,0.08)',
          }}
          animate={{
            boxShadow: [
              '0 0 0 1px rgba(34,211,238,0.06), 0 0 30px rgba(16,185,129,0.08)',
              '0 0 0 1px rgba(251,191,36,0.14), 0 0 46px rgba(251,191,36,0.10)',
              '0 0 0 1px rgba(34,211,238,0.06), 0 0 30px rgba(16,185,129,0.08)',
            ],
          }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
          className={[
            'rounded-2xl border border-border/60 bg-panel-elevated p-5',
            overBudget ? 'ring-1 ring-inset ring-danger-500/20' : '',
          ].join(' ')}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs text-text-muted">TOTAL COST</div>
              <div className="mt-1 flex items-end gap-2">
                <MotionSpan className="font-mono text-3xl font-semibold tabular-nums text-text">
                  {usd(animatedTotal)}
                </MotionSpan>
              </div>
            </div>
            <div className="rounded-2xl bg-panel px-3 py-2 ring-1 ring-inset ring-border/70">
              <div className="flex items-center gap-2 text-xs font-semibold text-text-muted">
                <DollarSign className="h-4 w-4 text-warning-200" />
                Burn rate
              </div>
              <div className="mt-1 flex items-center justify-between gap-3 text-sm">
                <div
                  className={[
                    'inline-flex items-center gap-1 font-mono font-semibold tabular-nums',
                    trendUp ? 'text-warning-200' : 'text-text-muted',
                  ].join(' ')}
                >
                  {trendUp ? (
                    <TrendingUp className="h-4 w-4" />
                  ) : (
                    <TrendingDown className="h-4 w-4" />
                  )}
                  {trendUp ? `+${usd(animatedRate)}/min` : `${usd(0)}/min`}
                </div>
                <div className="text-[11px] text-text-subtle">(last 60s)</div>
              </div>
            </div>
          </div>

          <div className="mt-4 text-xs text-text-muted">
            Last tick:{' '}
            <span className="font-mono text-text">
              {live.lastTick > 0 ? `+${usd(live.lastTick)}` : usd(0)}
            </span>
          </div>
        </MotionDiv>

        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-5 shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs font-semibold tracking-wide text-text-subtle">
                ESTIMATE
              </div>
              <div className="mt-1 text-sm text-text-muted">
                Projected final spend
              </div>
            </div>
            <div
              className={[
                'inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-xs font-semibold ring-1 ring-inset',
                overBudget
                  ? 'bg-danger-500/14 text-danger-100 ring-danger-500/25'
                  : 'bg-warning-500/14 text-warning-200 ring-warning-500/25',
              ].join(' ')}
            >
              {overBudget ? (
                <AlertTriangle className="h-4 w-4" />
              ) : (
                <Banknote className="h-4 w-4" />
              )}
              Estimated Final Cost: <span className="font-mono">{usd(estimate.estimatedFinal)}</span>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-border/60 bg-panel p-4 text-xs text-text-muted">
            Method:{' '}
            <span className="font-semibold text-text">{estimate.method.used}</span>{' '}
            = <span className="font-mono text-text">{usd(estimate.method.baselinePerGen)}</span> per gen
            <span className="text-text-subtle"> × </span>
            <span className="font-mono text-text">{estimate.method.remaining}</span> remaining gens
            <span className="text-text-subtle"> + </span>
            current total <span className="font-mono text-text">{usd(live.totalCost)}</span>
          </div>

          {live.budget !== null && live.budget !== undefined ? (
            <div className="mt-3 text-xs text-text-muted">
              Budget remaining:{' '}
              <span className={`font-mono ${overBudget ? 'text-danger-200' : 'text-text'}`}>
                {usd(live.budget - live.totalCost)}
              </span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-border/60 bg-panel-elevated p-5 shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
        <div className="text-sm font-semibold text-text">BREAKDOWN</div>
        <div className="mt-4 grid gap-4">
          {breakdownRows.map((r) => (
            <div key={r.key} className="rounded-2xl border border-border/60 bg-panel p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-text">{r.label}</div>
                  <div className="mt-1 text-xs text-text-muted">
                    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 ring-1 ring-inset ${r.chip}`}>
                      {r.calls} calls
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-text-muted">Cost</div>
                  <div className="font-mono text-sm font-semibold tabular-nums text-text">
                    {usd(r.cost)}
                  </div>
                </div>
              </div>

              <div className="mt-3">
                <div className="flex items-center justify-between text-[11px] text-text-subtle">
                  <div>Share</div>
                  <div className="font-mono tabular-nums text-text">{Math.round(r.pct)}%</div>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${r.bar} transition-[width] duration-200`}
                    style={{ width: `${r.pct}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-5 shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm font-semibold text-text">COST PER GENERATION</div>
            <div className="text-xs text-text-muted">
              Gen <span className="font-mono text-text">{currentGeneration}</span> /{' '}
              <span className="font-mono text-text">{totalGenerations}</span>
            </div>
          </div>

          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={perGenData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
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
                  tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
                />
                <Tooltip content={<MoneyTooltip kind="perGen" />} />
                <Bar dataKey="cost" radius={[10, 10, 10, 10]} isAnimationActive>
                  {perGenData.map((entry) => (
                    <Cell
                      key={entry.gen}
                      fill={
                        entry.isCurrent
                          ? 'rgba(34,211,238,0.65)'
                          : 'rgba(16,185,129,0.40)'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-5 shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm font-semibold text-text">RUNNING TOTAL</div>
            <div className="text-xs text-text-muted">
              Window: <span className="font-mono text-text">~{Math.round(burn.seconds)}s</span>
            </div>
          </div>

          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={seriesData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(148,163,184,0.10)" vertical={false} />
                <XAxis
                  dataKey="ts"
                  tickFormatter={mmss}
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                  minTickGap={26}
                />
                <YAxis
                  tick={{ fill: 'rgba(245,245,245,0.55)', fontSize: 11 }}
                  axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                  tickLine={false}
                  tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
                  domain={['auto', 'auto']}
                />
                <Tooltip content={<MoneyTooltip />} />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="rgba(251,191,36,0.85)"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <AnimatePresence>
            {overBudget ? (
              <MotionDiv
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className="mt-4 flex items-start gap-2 rounded-2xl border border-danger-500/30 bg-danger-500/10 p-4 text-sm text-danger-100"
              >
                <AlertTriangle className="mt-0.5 h-5 w-5 text-danger-200" />
                <div>
                  <div className="font-semibold">Budget risk</div>
                  <div className="mt-1 text-sm text-danger-100/90">
                    Projected final cost exceeds budget. Consider reducing LLM mutation frequency or
                    tightening validation cadence.
                  </div>
                </div>
              </MotionDiv>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

