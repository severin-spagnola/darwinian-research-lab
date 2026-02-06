import { useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle,
  BadgeCheck,
  Ban,
  CheckCircle2,
  ChevronRight,
  Flame,
  Gauge,
  GitPullRequest,
  Minus,
  Shield,
  Sparkles,
  Star,
  TrendingDown,
  TrendingUp,
  Waves,
  XCircle,
} from 'lucide-react'

const MotionDiv = motion.div
const MotionSection = motion.section
const EMPTY_ARRAY = []

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function formatDate(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toISOString().slice(0, 10)
}

function scoreTone(fitness, threshold) {
  if (fitness >= threshold) return 'pass'
  return 'fail'
}

function verdictTone(verdict) {
  if (verdict === 'SURVIVE') return 'survive'
  if (String(verdict ?? '').startsWith('KILL')) return 'kill'
  return 'neutral'
}

function verdictExplanation(verdict) {
  if (verdict === 'SURVIVE') return 'Meets Phase 3 stability and coverage requirements.'
  if (verdict === 'KILL_LUCKY') {
    return 'High fitness likely driven by a lucky spike; repeatability is suspect.'
  }
  if (verdict === 'KILL_DISPERSION') {
    return 'Performance is inconsistent across episodes/regimes (high dispersion).'
  }
  if (verdict === 'KILL_DRAWDOWN') return 'Risk control failed (drawdown exceeded threshold).'
  return 'Insufficient evidence to pass Phase 3.'
}

function nextActionLabel(nextAction) {
  if (nextAction === 'breed') return 'Breed next generation'
  if (nextAction === 'discard') return 'Discard strategy'
  return String(nextAction ?? '—')
}

function difficultyStars(difficulty01) {
  const d = clamp(safeNumber(difficulty01, 0), 0, 1)
  return Math.round(d * 5)
}

function getEpisodeBars(trades, difficulty01) {
  const t = Math.max(0, Math.round(safeNumber(trades, 0)))
  const d = clamp(safeNumber(difficulty01, 0.4), 0, 1)
  const multiplier = 12 + d * 16
  return Math.max(30, Math.round(t * multiplier))
}

function getEpisodeFills(trades, slippageBps) {
  const t = Math.max(0, Math.round(safeNumber(trades, 0)))
  const slip = clamp(safeNumber(slippageBps, 6), 0, 30)
  // Slightly more fills when turnover/slippage is high.
  return Math.max(1, Math.round(t * (1 + slip / 50)))
}

function RegimeBadge({ icon, label, tone = 'neutral' }) {
  const Icon = icon
  const cls =
    tone === 'primary'
      ? 'bg-primary-500/15 text-primary-200 ring-primary-500/20'
      : tone === 'danger'
        ? 'bg-danger-500/15 text-danger-200 ring-danger-500/20'
        : tone === 'warning'
          ? 'bg-warning-500/15 text-warning-200 ring-warning-500/20'
          : tone === 'info'
            ? 'bg-info-500/15 text-info-200 ring-info-500/20'
            : 'bg-panel text-text-muted ring-border/70'

  return (
    <span
      className={[
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold',
        'ring-1 ring-inset',
        cls,
      ].join(' ')}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

function EpisodeCard({ episode, passThreshold, index }) {
  const fitness = safeNumber(episode?.fitness, 0)
  const tone = scoreTone(fitness, passThreshold)
  const passed = tone === 'pass'

  const tags = episode?.tags ?? {}
  const difficulty = clamp(safeNumber(episode?.difficulty, 0), 0, 1)
  const stars = difficultyStars(difficulty)

  const debug = episode?.debug_stats ?? {}
  const trades = Math.max(0, Math.round(safeNumber(debug?.trades, 0)))
  const bars = Math.max(0, Math.round(safeNumber(debug?.bars, getEpisodeBars(trades, difficulty))))
  const fills = Math.max(0, Math.round(safeNumber(debug?.fills, getEpisodeFills(trades, debug?.slippage_bps))))

  const heatAlpha = 0.06 + difficulty * 0.16
  const heatColor = passed ? `rgba(16,185,129,${heatAlpha})` : `rgba(239,68,68,${heatAlpha})`

  const trendBadge = (() => {
    if (tags.trend === 'up') return { icon: TrendingUp, label: 'Up', tone: 'primary' }
    if (tags.trend === 'down') return { icon: TrendingDown, label: 'Down', tone: 'danger' }
    return { icon: Minus, label: 'Sideways', tone: 'info' }
  })()

  const volBadge = (() => {
    if (tags.vol_bucket === 'high') return { icon: Flame, label: 'High Vol', tone: 'warning' }
    if (tags.vol_bucket === 'mid') return { icon: Gauge, label: 'Mid Vol', tone: 'info' }
    return { icon: Gauge, label: 'Low Vol', tone: 'primary' }
  })()

  const chopBadge = (() => {
    if (tags.chop_bucket === 'trending') return { icon: TrendingUp, label: 'Trending', tone: 'primary' }
    if (tags.chop_bucket === 'choppy') return { icon: Waves, label: 'Choppy', tone: 'warning' }
    return { icon: Waves, label: 'Mixed', tone: 'info' }
  })()

  const ddBadge = (() => {
    if (tags.drawdown_state === 'at_highs') return { icon: BadgeCheck, label: 'At Highs', tone: 'primary' }
    if (tags.drawdown_state === 'mid_drawdown') return { icon: AlertTriangle, label: 'Mid DD', tone: 'warning' }
    return { icon: Ban, label: 'Deep DD', tone: 'danger' }
  })()

  return (
    <MotionDiv
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ duration: 0.18, ease: 'easeOut', delay: Math.min(0.2, index * 0.02) }}
      className={[
        'relative overflow-hidden rounded-2xl border bg-panel-elevated p-4',
        passed ? 'border-primary-500/30' : 'border-danger-500/30',
        'shadow-[0_0_0_1px_rgba(34,211,238,0.05)]',
      ].join(' ')}
      style={{
        backgroundImage: `linear-gradient(90deg, ${heatColor}, rgba(0,0,0,0))`,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-sm font-semibold">
              Episode {index + 1}
            </div>
            <ChevronRight className="h-4 w-4 text-text-subtle" />
            <div className="font-mono text-xs text-text-subtle">
              {formatDate(episode?.start_ts)}
            </div>
          </div>
          <div className="mt-1 text-xs text-text-muted">
            <span className="font-mono text-text">{episode?.label ?? `episode_${index + 1}`}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-right">
            <div className="text-[11px] text-text-muted">Fitness</div>
            <div className="font-mono text-sm font-semibold tabular-nums text-text">
              {fitness.toFixed(3)}
            </div>
          </div>
          <div
            className={[
              'grid h-9 w-9 place-items-center rounded-xl ring-1 ring-inset',
              passed
                ? 'bg-primary-500/14 text-primary-200 ring-primary-500/25'
                : 'bg-danger-500/14 text-danger-200 ring-danger-500/25',
            ].join(' ')}
            aria-label={passed ? 'Passed' : 'Failed'}
            title={passed ? 'Passed' : 'Failed'}
          >
            {passed ? (
              <CheckCircle2 className="h-5 w-5" />
            ) : (
              <XCircle className="h-5 w-5" />
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <RegimeBadge icon={trendBadge.icon} label={trendBadge.label} tone={trendBadge.tone} />
        <RegimeBadge icon={volBadge.icon} label={volBadge.label} tone={volBadge.tone} />
        <RegimeBadge icon={chopBadge.icon} label={chopBadge.label} tone={chopBadge.tone} />
        <RegimeBadge icon={ddBadge.icon} label={ddBadge.label} tone={ddBadge.tone} />
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-border/60 bg-panel p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[11px] text-text-muted">Difficulty</div>
            <div className="font-mono text-[11px] tabular-nums text-text-subtle">
              {difficulty.toFixed(2)}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1">
            {Array.from({ length: 5 }, (_, i) => {
              const filled = i < stars
              return (
                <Star
                  key={i}
                  className={[
                    'h-4 w-4',
                    filled ? 'text-warning-200' : 'text-border',
                  ].join(' ')}
                  fill={filled ? 'currentColor' : 'none'}
                  aria-hidden="true"
                />
              )
            })}
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
            <div
              className={[
                'h-full rounded-full transition-[width] duration-200',
                passed
                  ? 'bg-gradient-to-r from-primary-400/70 via-primary-300/60 to-info-400/60'
                  : 'bg-gradient-to-r from-danger-400/70 via-danger-300/60 to-warning-300/40',
              ].join(' ')}
              style={{ width: `${Math.round(difficulty * 100)}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-border/60 bg-panel p-3">
          <div className="text-[11px] text-text-muted">Debug Stats</div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-text-muted">
            <div className="rounded-lg bg-panel-elevated px-2.5 py-2 ring-1 ring-inset ring-border/70">
              <div className="text-[11px] text-text-subtle">Trades</div>
              <div className="mt-0.5 font-mono font-semibold tabular-nums text-text">
                {trades}
              </div>
            </div>
            <div className="rounded-lg bg-panel-elevated px-2.5 py-2 ring-1 ring-inset ring-border/70">
              <div className="text-[11px] text-text-subtle">Bars</div>
              <div className="mt-0.5 font-mono font-semibold tabular-nums text-text">
                {bars}
              </div>
            </div>
            <div className="rounded-lg bg-panel-elevated px-2.5 py-2 ring-1 ring-inset ring-border/70">
              <div className="text-[11px] text-text-subtle">Fills</div>
              <div className="mt-0.5 font-mono font-semibold tabular-nums text-text">
                {fills}
              </div>
            </div>
          </div>
        </div>
      </div>
    </MotionDiv>
  )
}

function PenaltyRow({ label, value01 }) {
  const v = clamp(safeNumber(value01, 0), 0, 1)
  const pct = Math.round(v * 1000) / 10
  const width = clamp(v * 100, 0, 100)
  const tone = v >= 0.08 ? 'danger' : v >= 0.04 ? 'warning' : 'primary'

  const barClass =
    tone === 'danger'
      ? 'from-danger-400/70 via-danger-300/60 to-warning-300/40'
      : tone === 'warning'
        ? 'from-warning-300/70 via-warning-200/60 to-info-300/40'
        : 'from-primary-400/70 via-info-400/60 to-primary-300/60'

  return (
    <div className="rounded-xl border border-border/60 bg-panel p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold text-text">{label}</div>
        <div className="font-mono text-xs tabular-nums text-text-muted">{pct}%</div>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${barClass} transition-[width] duration-200`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  )
}

export default function ValidationViewer({ strategy, isAnimating = false }) {
  const title = useMemo(() => {
    return (
      strategy?.name ??
      strategy?.graph?.name ??
      strategy?.id ??
      'Selected Strategy'
    )
  }, [strategy])

  const results = strategy?.results ?? null
  const phase3 = results?.phase3 ?? null
  const episodes = useMemo(() => {
    return Array.isArray(phase3?.episodes) ? phase3.episodes : EMPTY_ARRAY
  }, [phase3?.episodes])
  const verdict = results?.red_verdict?.verdict ?? null
  const failures = Array.isArray(results?.red_verdict?.failures) ? results.red_verdict.failures : []
  const nextAction = results?.red_verdict?.next_action ?? null

  const aggregated = safeNumber(phase3?.aggregated_fitness, 0)
  const median = safeNumber(phase3?.median_fitness, 0)
  const uniqueRegimes = phase3?.regime_coverage?.unique_regimes
  const years = phase3?.regime_coverage?.years_covered

  const passThreshold = useMemo(() => 0.03, [])
  const passedCount = useMemo(
    () => episodes.filter((e) => safeNumber(e?.fitness, 0) >= passThreshold).length,
    [episodes, passThreshold],
  )

  const completionTarget = useMemo(() => {
    if (!isAnimating) return episodes.length
    return Math.max(8, episodes.length)
  }, [episodes.length, isAnimating])

  const completion01 = completionTarget
    ? clamp(episodes.length / completionTarget, 0, 1)
    : 0

  const verdictInfo = useMemo(() => {
    const tone = verdictTone(verdict)
    const icon =
      tone === 'survive' ? CheckCircle2 : tone === 'kill' ? XCircle : Shield
    const label = verdict ?? '—'
    const explanation = verdictExplanation(verdict)
    const cls =
      tone === 'survive'
        ? 'bg-primary-500/14 text-primary-100 ring-primary-500/25'
        : tone === 'kill'
          ? 'bg-danger-500/14 text-danger-100 ring-danger-500/25'
          : 'bg-panel-elevated text-text ring-border/70'
    return { tone, icon, label, explanation, cls }
  }, [verdict])

  if (!strategy) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/60 bg-panel-elevated p-10 text-center">
        <div className="text-sm font-semibold">Validation Chamber</div>
        <div className="mt-2 max-w-md text-sm text-text-muted">
          Select a strategy in the Arena to view Phase 3 episode testing results.
        </div>
      </div>
    )
  }

  if (!phase3) {
    return (
      <div className="rounded-2xl border border-border/60 bg-panel-elevated p-4">
        <div className="text-sm font-semibold">VALIDATION: {title}</div>
        <div className="mt-2 text-sm text-text-muted">
          No Phase 3 results found for this strategy.
        </div>
      </div>
    )
  }

  return (
    <MotionSection
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="overflow-hidden rounded-2xl border border-border/60 bg-panel-elevated shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_22px_rgba(16,185,129,0.06)]"
    >
      <div className="border-b border-border/60 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-semibold tracking-wide text-text-subtle">
              VALIDATION
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-text">
              {title}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-muted">
              <span className="rounded-full bg-panel px-3 py-1 ring-1 ring-inset ring-border/70">
                Episodes: <span className="font-mono text-text">{episodes.length}</span>
              </span>
              <span className="rounded-full bg-panel px-3 py-1 ring-1 ring-inset ring-border/70">
                Passed: <span className="font-mono text-text">{passedCount}</span>/
                <span className="font-mono text-text">{episodes.length}</span>
              </span>
              {isAnimating ? (
                <span className="rounded-full bg-warning-500/14 px-3 py-1 text-warning-200 ring-1 ring-inset ring-warning-500/25">
                  Live testing…
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-[11px] text-text-muted">Aggregated Fitness</div>
              <div className="font-mono text-2xl font-semibold tabular-nums text-text">
                {aggregated.toFixed(3)}
              </div>
              <div className="mt-1 text-[11px] text-text-muted">
                Median: <span className="font-mono text-text">{median.toFixed(3)}</span>
              </div>
            </div>
            <div className={`rounded-2xl px-3 py-2 text-xs font-semibold ring-1 ring-inset ${verdictInfo.cls}`}>
              <div className="flex items-center gap-2">
                <verdictInfo.icon className="h-4 w-4" />
                <span>{verdictInfo.tone === 'survive' ? 'SURVIVOR' : verdictInfo.label}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-border/60 bg-panel p-4">
            <div className="text-xs font-semibold text-text">Regime Coverage</div>
            <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
              <div>Unique Regimes</div>
              <div className="font-mono font-semibold tabular-nums text-text">
                {uniqueRegimes ?? '—'}
              </div>
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-text-muted">
              <div>Years Covered</div>
              <div className="font-mono font-semibold tabular-nums text-text">
                {years ?? '—'}
              </div>
            </div>
            <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
              <MotionDiv
                className="h-full rounded-full bg-gradient-to-r from-info-400/70 via-primary-300/60 to-info-300/60"
                initial={false}
                animate={{ width: `${Math.round(clamp(completion01, 0, 1) * 100)}%` }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              />
            </div>
            <div className="mt-2 text-[11px] text-text-subtle">
              Episodes completed:{' '}
              <span className="font-mono text-text">{episodes.length}</span>/
              <span className="font-mono text-text">{completionTarget}</span>
            </div>
          </div>

          <div className="rounded-2xl border border-border/60 bg-panel p-4">
            <div className="text-xs font-semibold text-text">Penalties</div>
            <div className="mt-2 grid gap-2">
              <PenaltyRow label="Drawdown" value01={phase3?.penalties?.drawdown_penalty} />
              <PenaltyRow label="Dispersion" value01={phase3?.penalties?.dispersion_penalty} />
            </div>
          </div>

          <div className="rounded-2xl border border-border/60 bg-panel p-4">
            <div className="text-xs font-semibold text-text">Penalties (cont.)</div>
            <div className="mt-2 grid gap-2">
              <PenaltyRow label="Churn" value01={phase3?.penalties?.churn_penalty} />
              <PenaltyRow label="Overfit" value01={phase3?.penalties?.overfit_penalty} />
            </div>
          </div>
        </div>
      </div>

      <div className="border-b border-border/60 px-3 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold text-text">
            EPISODES <span className="text-text-muted">({episodes.length} tested)</span>
          </div>
          <div className="text-xs text-text-muted">
            Pass threshold: <span className="font-mono text-text">{passThreshold.toFixed(2)}</span>
          </div>
        </div>

        <div className="mt-3 grid gap-2">
          <AnimatePresence initial={false}>
            {episodes.map((ep, idx) => (
              <EpisodeCard
                key={ep?.label ?? idx}
                episode={ep}
                passThreshold={passThreshold}
                index={idx}
              />
            ))}
          </AnimatePresence>
        </div>
      </div>

      <div className="px-3 py-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="text-xs font-semibold tracking-wide text-text-subtle">
              VERDICT
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm font-semibold text-text">
              {verdictInfo.tone === 'survive' ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-primary-200" />
                  SURVIVE
                </>
              ) : verdictInfo.tone === 'kill' ? (
                <>
                  <XCircle className="h-5 w-5 text-danger-200" />
                  {verdictInfo.label}
                </>
              ) : (
                <>
                  <Shield className="h-5 w-5 text-text-muted" />
                  {verdictInfo.label}
                </>
              )}
            </div>
            <div className="mt-2 text-sm text-text-muted">
              {verdictInfo.explanation}
            </div>
          </div>

          <div className="w-full max-w-md rounded-2xl border border-border/60 bg-panel p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-semibold text-text">Next Action</div>
              <div className="inline-flex items-center gap-2 rounded-full bg-panel-elevated px-3 py-1 text-xs font-semibold text-text ring-1 ring-inset ring-border/70">
                <GitPullRequest className="h-4 w-4 text-info-200" />
                {nextActionLabel(nextAction)}
              </div>
            </div>

            <div className="mt-3 text-xs text-text-muted">
              Failures:{' '}
              {failures.length === 0 ? (
                <span className="font-semibold text-primary-200">None</span>
              ) : (
                <span className="font-mono text-danger-200">
                  {failures.join(', ')}
                </span>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
              <span className="rounded-full bg-panel-elevated px-3 py-1 ring-1 ring-inset ring-border/70">
                <span className="mr-2 text-primary-200">●</span>Pass
              </span>
              <span className="rounded-full bg-panel-elevated px-3 py-1 ring-1 ring-inset ring-border/70">
                <span className="mr-2 text-danger-200">●</span>Fail
              </span>
              <span className="rounded-full bg-panel-elevated px-3 py-1 ring-1 ring-inset ring-border/70">
                <span className="mr-2 text-warning-200">●</span>Difficulty heat
              </span>
              <span className="rounded-full bg-panel-elevated px-3 py-1 ring-1 ring-inset ring-border/70">
                <Sparkles className="mr-2 inline h-3.5 w-3.5 text-info-200" />
                Phase 3
              </span>
            </div>
          </div>
        </div>
      </div>
    </MotionSection>
  )
}
