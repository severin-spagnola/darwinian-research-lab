import { useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Crown, Skull, Sparkles, X } from 'lucide-react'

const MotionArticle = motion.article
const MotionDiv = motion.div

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function formatPct01(v) {
  const pct = Math.round(clamp(safeNumber(v, 0) * 100, 0, 100))
  return `${pct}%`
}

function hash01(input) {
  const s = String(input ?? '')
  let h = 2166136261
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  // Map to [0, 1)
  return ((h >>> 0) % 10_000) / 10_000
}

function deriveMetrics(strategy) {
  const results = strategy?.results ?? null
  const phase3 = results?.phase3 ?? null
  const episodes = Array.isArray(phase3?.episodes) ? phase3.episodes : []
  const totalEpisodes = episodes.length

  const fitness = safeNumber(phase3?.aggregated_fitness, safeNumber(phase3?.median_fitness, 0))

  const sharpes = episodes
    .map((e) => safeNumber(e?.debug_stats?.sharpe, NaN))
    .filter((v) => Number.isFinite(v))
  const sharpe =
    sharpes.length > 0
      ? sharpes.reduce((acc, v) => acc + v, 0) / sharpes.length
      : null

  const drawdowns = episodes
    .map((e) => safeNumber(e?.debug_stats?.max_drawdown, NaN))
    .filter((v) => Number.isFinite(v))
  const maxDrawdown01 = drawdowns.length > 0 ? Math.max(...drawdowns) : null

  const verdict = results?.red_verdict?.verdict ?? null
  const shouldPassAll = verdict === 'SURVIVE' || strategy?.state === 'alive' || strategy?.state === 'elite'
  const passThreshold = Math.max(0.02, safeNumber(phase3?.median_fitness, 0.03))
  const passedEpisodes = shouldPassAll
    ? totalEpisodes
    : episodes.filter((e) => safeNumber(e?.fitness, 0) >= passThreshold).length

  const explicitProgress = strategy?.validation_progress ?? strategy?.progress ?? null
  const progress01 =
    explicitProgress !== null && explicitProgress !== undefined
      ? clamp(safeNumber(explicitProgress, 0), 0, 1)
      : totalEpisodes > 0
        ? clamp(passedEpisodes / totalEpisodes, 0, 1)
        : 0

  return {
    results,
    phase3,
    episodes,
    verdict,
    fitness,
    sharpe,
    maxDrawdown01,
    passedEpisodes,
    totalEpisodes,
    progress01,
  }
}

function parseGenerationFromId(id) {
  const m = String(id ?? '').match(/strat_gen(\d+)_/)
  if (!m) return null
  return Number(m[1])
}

export default function StrategyCard({
  strategy,
  isSelected,
  onSelect,
  animationDelay = 0,
}) {
  const state = strategy?.state ?? 'alive'
  const isElite = state === 'elite'
  const isDead = state === 'dead'
  const isTesting = state === 'testing'
  const isAlive = !isDead

  const {
    results,
    phase3,
    verdict,
    fitness,
    sharpe,
    maxDrawdown01,
    passedEpisodes,
    totalEpisodes,
    progress01,
  } = useMemo(() => deriveMetrics(strategy), [strategy])

  const title = useMemo(() => {
    return strategy?.name ?? strategy?.graph?.name ?? strategy?.id ?? 'Strategy'
  }, [strategy])

  const generation = useMemo(() => {
    return (
      safeNumber(strategy?.graph?.metadata?.generation, parseGenerationFromId(strategy?.id)) ??
      null
    )
  }, [strategy])

  const parentGraphId = strategy?.parent ?? strategy?.graph?.metadata?.parent_graph ?? null
  const parentGen = parentGraphId ? parseGenerationFromId(parentGraphId) : null
  const parentLabel = parentGraphId
    ? `${String(parentGraphId).slice(0, 18)}${String(parentGraphId).length > 18 ? '…' : ''}${parentGen !== null ? ` → Gen ${parentGen}` : ''}`
    : 'Root'

  const badge = useMemo(() => {
    if (isElite) return { text: 'ELITE', tone: 'warning' }
    if (isTesting) return { text: 'Testing…', tone: 'warning' }
    if (isDead) return { text: 'DEAD', tone: 'danger' }
    return { text: 'ALIVE', tone: 'primary' }
  }, [isDead, isElite, isTesting])

  const borderClass = useMemo(() => {
    if (isElite) return 'border-primary-400/70'
    if (isTesting) return 'border-warning-400/70'
    if (isDead) return 'border-danger-500/55'
    return 'border-primary-500/45'
  }, [isDead, isElite, isTesting])

  const selectedClass = isSelected
    ? 'ring-2 ring-info-300/40 shadow-[0_0_0_1px_rgba(34,211,238,0.15),0_0_30px_rgba(34,211,238,0.14)]'
    : ''

  const badgeClass = useMemo(() => {
    if (badge.tone === 'danger') {
      return 'bg-danger-500/15 text-danger-200 ring-1 ring-inset ring-danger-500/25'
    }
    if (badge.tone === 'warning') {
      return 'bg-warning-500/15 text-warning-200 ring-1 ring-inset ring-warning-500/25'
    }
    return 'bg-primary-500/15 text-primary-200 ring-1 ring-inset ring-primary-500/25'
  }, [badge.tone])

  const glowKeyframes = useMemo(() => {
    // Reduce motion for dead/testing, stronger for elite.
    if (isDead) return null
    const base = isElite
      ? [
          '0 0 0 1px rgba(16,185,129,0.16), 0 0 22px rgba(16,185,129,0.14), 0 0 0 rgba(251,191,36,0)',
          '0 0 0 1px rgba(16,185,129,0.24), 0 0 30px rgba(16,185,129,0.18), 0 0 16px rgba(251,191,36,0.12)',
        ]
      : [
          '0 0 0 1px rgba(16,185,129,0.12), 0 0 16px rgba(16,185,129,0.10)',
          '0 0 0 1px rgba(16,185,129,0.18), 0 0 22px rgba(16,185,129,0.12)',
        ]
    return isTesting ? null : base
  }, [isDead, isElite, isTesting])

  const shimmerSeed = useMemo(() => hash01(strategy?.id ?? title), [strategy?.id, title])
  const testingProgress = useMemo(() => {
    if (!isTesting) return progress01
    const p = 0.22 + shimmerSeed * 0.72
    return clamp(p, 0.05, 0.95)
  }, [isTesting, progress01, shimmerSeed])

  const progressPct = Math.round(clamp((isTesting ? testingProgress : progress01) * 100, 0, 100))

  const variants = useMemo(
    () => ({
      initial: { opacity: 0, y: 10, scale: 0.985 },
      alive: {
        opacity: 1,
        y: 0,
        scale: 1,
        filter: 'grayscale(0)',
        boxShadow: glowKeyframes ?? undefined,
      },
      elite: {
        opacity: 1,
        y: 0,
        scale: 1,
        filter: 'grayscale(0)',
        boxShadow: glowKeyframes ?? undefined,
      },
      testing: {
        opacity: 1,
        y: 0,
        scale: 1,
        filter: 'grayscale(0)',
      },
      dead: {
        opacity: 0.55,
        y: 12,
        scale: 0.985,
        filter: 'grayscale(0.92)',
        boxShadow: '0 0 0 1px rgba(239,68,68,0.14), 0 0 16px rgba(239,68,68,0.08)',
      },
    }),
    [glowKeyframes],
  )

  const animateKey = isElite ? 'elite' : isDead ? 'dead' : isTesting ? 'testing' : 'alive'

  const episodeLabel =
    totalEpisodes > 0 ? `${passedEpisodes}/${totalEpisodes} passed` : isTesting ? 'Testing…' : '—'

  const sharpeLabel = sharpe !== null ? sharpe.toFixed(1) : '—'
  const ddLabel = maxDrawdown01 !== null ? `-${formatPct01(maxDrawdown01)}` : '—'

  const tooltipText = useMemo(() => {
    const symbols = strategy?.graph?.universe?.symbols
    const universe = Array.isArray(symbols) ? symbols.join(', ') : '—'
    const coverage = phase3?.regime_coverage
    const uniqueRegimes = coverage?.unique_regimes ?? '—'
    const yearsCovered = coverage?.years_covered ?? '—'
    const penalties = phase3?.penalties
    const totalPenalty = penalties?.total_penalty ?? '—'

    return {
      id: strategy?.id ?? '—',
      verdict: verdict ?? '—',
      generation: generation ?? '—',
      universe,
      fitness: fitness ? fitness.toFixed(4) : '0.0000',
      median_fitness: safeNumber(phase3?.median_fitness, 0).toFixed(4),
      sharpe: sharpe !== null ? sharpe.toFixed(3) : '—',
      max_drawdown: maxDrawdown01 !== null ? maxDrawdown01.toFixed(4) : '—',
      episodes: totalEpisodes,
      unique_regimes: uniqueRegimes,
      years_covered: yearsCovered,
      total_penalty: totalPenalty,
    }
  }, [
    fitness,
    generation,
    maxDrawdown01,
    phase3,
    sharpe,
    totalEpisodes,
    strategy?.graph?.universe?.symbols,
    strategy?.id,
    verdict,
  ])

  return (
    <MotionArticle
      layout
      initial="initial"
      animate={animateKey}
      variants={variants}
      transition={{
        duration: 0.22,
        ease: 'easeOut',
        delay: clamp(safeNumber(animationDelay, 0), 0, 1),
        boxShadow:
          glowKeyframes && isAlive
            ? { duration: isElite ? 2.4 : 2.8, repeat: Infinity, repeatType: 'mirror' }
            : undefined,
      }}
      onClick={() => onSelect?.(strategy)}
      className={[
        'group relative cursor-pointer select-none overflow-hidden rounded-2xl border bg-panel-elevated p-3',
        'transition-[border-color,transform,filter] duration-200',
        'focus-within:outline-none',
        borderClass,
        selectedClass,
        isDead ? 'opacity-70' : 'hover:-translate-y-0.5',
      ].join(' ')}
      role="button"
      tabIndex={0}
      aria-pressed={Boolean(isSelected)}
    >
      {/* State overlays */}
      <AnimatePresence>
        {isTesting ? (
          <MotionDiv
            key="shimmer"
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <MotionDiv
              className="absolute -inset-x-1/2 inset-y-0 rotate-12 bg-gradient-to-r from-transparent via-warning-300/18 to-transparent"
              initial={{ x: '-40%' }}
              animate={{ x: '40%' }}
              transition={{
                duration: 1.35,
                repeat: Infinity,
                repeatType: 'loop',
                ease: 'linear',
              }}
            />
          </MotionDiv>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {isElite ? (
          <MotionDiv
            key="elite-flash"
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.7, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-warning-300/22 via-primary-400/10 to-transparent" />
          </MotionDiv>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {isDead ? (
          <MotionDiv
            key="dead-overlay"
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-danger-500/10 via-transparent to-black/40" />
            <MotionDiv
              className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-xl bg-danger-500/14 ring-1 ring-inset ring-danger-500/25"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.18, ease: 'easeOut', delay: 0.06 }}
            >
              <X className="h-4 w-4 text-danger-200" />
            </MotionDiv>
          </MotionDiv>
        ) : null}
      </AnimatePresence>

      {/* Hover tooltip overlay (kept inside card to avoid clipping) */}
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <div className="absolute inset-0 bg-bg/85 backdrop-blur-sm" />
        <div className="relative h-full p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{title}</div>
              <div className="mt-1 truncate font-mono text-[11px] text-text-subtle">
                {tooltipText.id}
              </div>
            </div>
            <div className="rounded-full bg-panel-elevated px-2.5 py-1 text-[11px] font-semibold text-text-muted ring-1 ring-inset ring-border/70">
              {tooltipText.verdict}
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl border border-border/60 bg-panel p-3">
              <div className="text-[11px] text-text-subtle">Fitness</div>
              <div className="mt-1 font-mono text-sm font-semibold tabular-nums text-text">
                {tooltipText.fitness}
              </div>
              <div className="mt-2 text-[11px] text-text-muted">
                Median: <span className="font-mono text-text">{tooltipText.median_fitness}</span>
              </div>
            </div>
            <div className="rounded-xl border border-border/60 bg-panel p-3">
              <div className="text-[11px] text-text-subtle">Risk</div>
              <div className="mt-1 text-[11px] text-text-muted">
                Sharpe: <span className="font-mono text-text">{tooltipText.sharpe}</span>
              </div>
              <div className="mt-1 text-[11px] text-text-muted">
                Max DD: <span className="font-mono text-text">{tooltipText.max_drawdown}</span>
              </div>
              <div className="mt-1 text-[11px] text-text-muted">
                Penalty: <span className="font-mono text-text">{tooltipText.total_penalty}</span>
              </div>
            </div>
            <div className="col-span-2 rounded-xl border border-border/60 bg-panel p-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-text-muted">
                <div>
                  Gen: <span className="font-mono text-text">{tooltipText.generation}</span>
                </div>
                <div>
                  Episodes: <span className="font-mono text-text">{tooltipText.episodes}</span>
                </div>
                <div>
                  Regimes:{' '}
                  <span className="font-mono text-text">{tooltipText.unique_regimes}</span>
                </div>
                <div>
                  Years:{' '}
                  <span className="font-mono text-text">{tooltipText.years_covered}</span>
                </div>
              </div>
              <div className="mt-2 truncate text-[11px] text-text-muted">
                Universe: <span className="font-mono text-text">{tooltipText.universe}</span>
              </div>
              <div className="mt-2 truncate text-[11px] text-text-muted">
                Parent: <span className="font-mono text-text">{parentLabel}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Card content */}
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {isElite ? (
                <span className="grid h-6 w-6 place-items-center rounded-xl bg-warning-500/16 ring-1 ring-inset ring-warning-500/25">
                  <Crown className="h-4 w-4 text-warning-200" />
                </span>
              ) : isDead ? (
                <span className="grid h-6 w-6 place-items-center rounded-xl bg-danger-500/14 ring-1 ring-inset ring-danger-500/20">
                  <Skull className="h-4 w-4 text-danger-200" />
                </span>
              ) : (
                <span className="grid h-6 w-6 place-items-center rounded-xl bg-primary-500/14 ring-1 ring-inset ring-primary-500/20">
                  <Sparkles className="h-4 w-4 text-primary-200" />
                </span>
              )}
              <div className="truncate text-sm font-semibold">{title}</div>
            </div>
            <div className="mt-1 truncate font-mono text-[11px] text-text-subtle">
              {strategy?.id ?? '—'}
            </div>
          </div>

          <div className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${badgeClass}`}>
            {badge.text}
          </div>
        </div>

        <div className="mt-3 grid gap-2">
          <div className="flex items-end justify-between">
            <div className="text-xs text-text-muted">Fitness</div>
            <div className="text-lg font-semibold tabular-nums text-text">
              {safeNumber(fitness, 0).toFixed(3)}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-text-muted">
            <div>
              Sharpe: <span className="font-semibold tabular-nums text-text">{sharpeLabel}</span>
            </div>
            <div>
              DD:{' '}
              <span className="font-semibold tabular-nums text-text">
                {ddLabel}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-text-muted">
            <div>Episodes</div>
            <div className="font-semibold tabular-nums text-text">{episodeLabel}</div>
          </div>
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between text-[11px] text-text-subtle">
            <div>Validation</div>
            <div className="font-mono tabular-nums text-text">{progressPct}%</div>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
            <div
              className={[
                'h-full rounded-full transition-[width] duration-200',
                isDead
                  ? 'bg-gradient-to-r from-danger-400/70 via-danger-300/60 to-danger-400/70'
                  : isTesting
                    ? 'bg-gradient-to-r from-warning-300/80 via-warning-200/60 to-warning-300/80'
                    : 'bg-gradient-to-r from-primary-400 via-info-400 to-primary-300',
              ].join(' ')}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between gap-3 text-xs text-text-muted">
          <div className="truncate">
            Parent: <span className="font-mono text-text">{parentLabel}</span>
          </div>
          <div className="shrink-0 font-mono text-text-subtle">
            {generation !== null ? `Gen ${generation}` : ''}
          </div>
        </div>

        {results?.red_verdict?.verdict && results.red_verdict.verdict !== 'SURVIVE' ? (
          <div className="mt-2 text-[11px] text-text-subtle">
            Verdict: <span className="font-mono text-text-muted">{results.red_verdict.verdict}</span>
          </div>
        ) : null}
      </div>
    </MotionArticle>
  )
}
