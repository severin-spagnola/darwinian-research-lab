import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Crown, Filter, Skull, Sparkles } from 'lucide-react'
import StrategyCard from './StrategyCard.jsx'

const MotionDiv = motion.div

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function getFitness(strategy) {
  return safeNumber(strategy?.results?.phase3?.aggregated_fitness, 0)
}

function classifyState(strategy) {
  const s = strategy?.state
  if (s === 'elite') return 'elite'
  if (s === 'dead') return 'dead'
  if (s === 'testing') return 'alive'
  return 'alive'
}

function sortStrategies(strategies) {
  const rank = (s) => {
    const st = s?.state
    if (st === 'elite') return 0
    if (st === 'alive' || st === 'testing') return 1
    return 2 // dead or unknown
  }

  return [...strategies].sort((a, b) => {
    const ra = rank(a)
    const rb = rank(b)
    if (ra !== rb) return ra - rb
    return getFitness(b) - getFitness(a)
  })
}

export default function EvolutionArena({
  strategies = [],
  generationNumber = 0,
  onStrategySelect,
  selectedStrategyId = null,
}) {
  const [filter, setFilter] = useState('all')

  const counts = useMemo(() => {
    const c = { alive: 0, dead: 0, elite: 0 }
    strategies.forEach((s) => {
      const st = classifyState(s)
      if (st === 'elite') c.elite += 1
      else if (st === 'dead') c.dead += 1
      else c.alive += 1
    })
    return c
  }, [strategies])

  const filteredSorted = useMemo(() => {
    const sorted = sortStrategies(strategies)
    if (filter === 'all') return sorted
    if (filter === 'alive') return sorted.filter((s) => s?.state === 'alive' || s?.state === 'testing')
    if (filter === 'dead') return sorted.filter((s) => s?.state === 'dead')
    if (filter === 'elite') return sorted.filter((s) => s?.state === 'elite')
    return sorted
  }, [filter, strategies])

  const filterDefs = useMemo(
    () => [
      { key: 'all', label: 'All', icon: Filter },
      { key: 'alive', label: 'Alive', icon: Sparkles },
      { key: 'dead', label: 'Dead', icon: Skull },
      { key: 'elite', label: 'Elite', icon: Crown },
    ],
    [],
  )

  if (!strategies || strategies.length === 0) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/60 bg-panel-elevated p-10 text-center">
        <div className="text-sm font-semibold">Initializing Generation 0…</div>
        <div className="mt-2 max-w-md text-sm text-text-muted">
          Strategies will appear here as the evolution run begins.
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-sm font-semibold">
            Generation {generationNumber} - {strategies.length} Strategies
          </div>
          <div className="mt-1 text-xs text-text-muted">
            <span className="text-primary-200">{counts.alive} Alive</span> |{' '}
            <span className="text-danger-200">{counts.dead} Dead</span> |{' '}
            <span className="text-warning-200">{counts.elite} Elite</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {filterDefs.map((f) => {
            const Icon = f.icon
            const active = filter === f.key
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={[
                  'inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold transition',
                  'focus:outline-none focus:ring-2 focus:ring-info-500/25',
                  active
                    ? 'bg-info-500/14 text-info-200 ring-1 ring-inset ring-info-500/25'
                    : 'bg-panel-elevated text-text-muted ring-1 ring-inset ring-border/70 hover:bg-white/5 hover:text-text',
                ].join(' ')}
                aria-pressed={active}
              >
                <Icon className="h-4 w-4" />
                {f.label}
              </button>
            )
          })}
        </div>
      </div>

      <MotionDiv
        layout
        className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
      >
        <AnimatePresence initial={false}>
          {filteredSorted.map((s, idx) => (
            <MotionDiv
              key={s?.id ?? idx}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
            >
              <StrategyCard
                strategy={s}
                isSelected={Boolean(selectedStrategyId && s?.id === selectedStrategyId)}
                onSelect={onStrategySelect}
                animationDelay={Math.min(0.18, idx * 0.02)}
              />
            </MotionDiv>
          ))}
        </AnimatePresence>
      </MotionDiv>
    </div>
  )
}
