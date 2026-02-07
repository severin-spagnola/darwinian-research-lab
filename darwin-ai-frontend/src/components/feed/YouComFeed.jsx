import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Dna,
  Lightbulb,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  XCircle,
} from 'lucide-react'

import { generateYouComResponse } from '../../data/mockDataGenerator.js'
import {
  makeGenerationQueries,
  YouComRateLimitError,
} from '../../utils/youcomAPI.js'
import { searchYouCom } from '../../api/client.js'

const MotionDiv = motion.div
const MotionSpan = motion.span
const EMPTY_ARRAY = []

function nowIso() {
  return new Date().toISOString()
}

function formatClock(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString([], { hour12: false })
}

function shortQuery(q, max = 44) {
  const s = String(q ?? '').trim()
  if (s.length <= max) return s
  return `${s.slice(0, max - 1)}…`
}

function hashId(input) {
  const s = String(input ?? '')
  let h = 2166136261
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0).toString(16)
}

function inferInsights(results) {
  const text = results.join(' ').toLowerCase()

  const insights = []
  const suggestions = []

  const hasVix = /vix|volatility|skew|realized/.test(text)
  const hasRates = /fed|rates|yield|inflation|cpi|tighten|higher[- ]for[- ]longer/.test(text)
  const hasTech = /tech|nasdaq|semiconductor|growth/.test(text)
  const hasEnergy = /energy|oil|xom|wti|brent/.test(text)
  const hasCredit = /credit|spreads|high[- ]yield|defaults/.test(text)

  if (hasVix) insights.push('Current regime: Elevated volatility; defensive positioning favored.')
  if (hasRates) insights.push('Interest-rate sensitivity is high; avoid duration-heavy exposure.')
  if (hasCredit) insights.push('Credit conditions tightening; reduce leverage and tail risk.')
  if (hasTech) insights.push('Growth/tech beta may be unstable; add risk filters and confirmations.')
  if (hasEnergy) insights.push('Energy relative strength is notable; consider defensive rotation overlays.')

  if (insights.length === 0) {
    insights.push('Regime signals mixed; prioritize robustness and risk controls.')
    insights.push('Prefer filters that reduce trading in choppy conditions.')
  }

  if (hasVix) suggestions.push('Add volatility filter (VIX/ATR) to gate entries during high vol')
  if (hasRates) suggestions.push('Reduce position sizing when rate shock risk increases')
  if (hasTech) suggestions.push('Require trend confirmation before adding growth exposure')
  if (hasEnergy) suggestions.push('Implement defensive sector rotation when energy outperforms')
  suggestions.push('Add drawdown throttle to reduce risk after consecutive losses')

  return {
    insights: insights.slice(0, 3),
    mutation_suggestions: suggestions.slice(0, 3),
  }
}

function EntryCard({
  entry,
  index,
  isCollapsed,
  onToggleCollapse,
}) {
  const isLoading = entry.status === 'loading'
  const isSuccess = entry.status === 'success' || entry.status === 'live' || entry.status === 'cached'
  const isError = entry.status === 'error'

  const headerIcon = isLoading ? Loader2 : isSuccess ? CheckCircle2 : XCircle
  const headerTone =
    isLoading ? 'warning' : isSuccess ? 'primary' : 'danger'

  const toneCls =
    headerTone === 'primary'
      ? 'text-primary-200'
      : headerTone === 'warning'
        ? 'text-warning-200'
        : headerTone === 'info'
          ? 'text-info-200'
          : 'text-danger-200'

  const chipCls =
    headerTone === 'primary'
      ? 'bg-primary-500/14 text-primary-200 ring-primary-500/25'
      : headerTone === 'warning'
        ? 'bg-warning-500/14 text-warning-200 ring-warning-500/25'
        : headerTone === 'info'
          ? 'bg-info-500/14 text-info-200 ring-info-500/25'
          : 'bg-danger-500/14 text-danger-200 ring-danger-500/25'

  const HeaderIcon = headerIcon

  return (
    <MotionDiv
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ duration: 0.18, ease: 'easeOut', delay: Math.min(0.2, index * 0.02) }}
      className="rounded-2xl border border-border/60 bg-panel p-4 shadow-[0_0_0_1px_rgba(34,211,238,0.05)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 ring-1 ring-inset ${chipCls}`}>
              <HeaderIcon
                className={[
                  'h-4 w-4',
                  isLoading ? 'animate-spin' : '',
                ].join(' ')}
              />
              <span className="font-mono">{formatClock(entry.timestamp)}</span>
            </span>
            <span className="truncate">
              {isLoading ? 'Searching:' : 'Search:'}{' '}
              <span className="font-semibold text-text">{shortQuery(entry.query, 64)}</span>
            </span>
          </div>

          {entry.error ? (
            <div className="mt-2 text-xs text-danger-200">
              {entry.error}
            </div>
          ) : null}
        </div>

        <button
          type="button"
          onClick={onToggleCollapse}
          className="inline-flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-semibold text-text-muted transition hover:bg-white/5 hover:text-text focus:outline-none focus:ring-2 focus:ring-info-500/25"
          aria-expanded={!isCollapsed}
        >
          {isCollapsed ? (
            <>
              <ChevronDown className="h-4 w-4" />
              Expand
            </>
          ) : (
            <>
              <ChevronUp className="h-4 w-4" />
              Collapse
            </>
          )}
        </button>
      </div>

      <AnimatePresence initial={false}>
        {!isCollapsed ? (
          <MotionDiv
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2">
              <div>
                <div className="text-xs font-semibold text-text">Results</div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-text-muted">
                  {(entry.results ?? EMPTY_ARRAY).map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                  {isLoading ? (
                    <li className="text-text-subtle">Fetching You.com results…</li>
                  ) : null}
                </ul>
              </div>

              <div className="rounded-2xl border border-border/60 bg-panel-elevated p-4">
                <div className="flex items-center gap-2 text-xs font-semibold text-text">
                  <Lightbulb className={`h-4 w-4 ${toneCls}`} />
                  Insights Generated
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-text-muted">
                  {(entry.insights ?? EMPTY_ARRAY).map((i) => (
                    <li key={i}>{i}</li>
                  ))}
                  {!isLoading && (!entry.insights || entry.insights.length === 0) ? (
                    <li className="text-text-subtle">No insights available.</li>
                  ) : null}
                </ul>
              </div>

              <div className="rounded-2xl border border-border/60 bg-panel-elevated p-4">
                <div className="flex items-center gap-2 text-xs font-semibold text-text">
                  <Dna className={`h-4 w-4 ${toneCls}`} />
                  Applied to Mutations
                </div>
                <div className="mt-2 space-y-2">
                  {(entry.mutation_suggestions ?? EMPTY_ARRAY).map((m) => (
                    <div
                      key={m}
                      className="flex items-start gap-2 rounded-xl border border-border/60 bg-panel px-3 py-2 text-xs text-text-muted"
                    >
                      <ArrowRight className="mt-0.5 h-4 w-4 text-text-subtle" />
                      <div>{m}</div>
                    </div>
                  ))}
                  {!isLoading && (!entry.mutation_suggestions || entry.mutation_suggestions.length === 0) ? (
                    <div className="text-xs text-text-subtle">No mutation suggestions yet.</div>
                  ) : null}
                </div>
              </div>

              {isError ? (
                <div className="rounded-2xl border border-danger-500/30 bg-danger-500/10 p-4 text-sm text-danger-100">
                  The You.com request failed. This entry used fallback content.
                </div>
              ) : null}
            </div>
          </MotionDiv>
        ) : null}
      </AnimatePresence>
    </MotionDiv>
  )
}

export default function YouComFeed({
  entries: externalEntries,
  isActive = true,
  currentGeneration = 0,
  onInsightGenerated,
}) {
  const isControlled = Array.isArray(externalEntries)
  const [internalEntries, setInternalEntries] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [activeQuery, setActiveQuery] = useState('')
  const [viewAll, setViewAll] = useState(false)
  const [collapsed, setCollapsed] = useState({})

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const endRef = useRef(null)
  const genRef = useRef(currentGeneration)

  const entries = isControlled ? externalEntries : internalEntries

  const visibleEntries = useMemo(() => {
    if (viewAll) return entries
    return entries.slice(-2)
  }, [entries, viewAll])

  const hiddenCount = Math.max(0, entries.length - visibleEntries.length)

  useEffect(() => {
    genRef.current = currentGeneration
  }, [currentGeneration])

  useEffect(() => {
    // Auto-scroll to newest entry.
    if (!endRef.current) return
    endRef.current.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [entries.length, viewAll])

  async function runSearch(query, { reason } = {}) {
    if (isControlled) return
    const q = String(query ?? '').trim()
    if (!q) return

    // Cancel any in-flight request.
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const id = `you_${Date.now()}_${hashId(q)}`
    const startTs = nowIso()

    setIsSearching(true)
    setActiveQuery(q)
    setInternalEntries((prev) => [
      ...prev,
      {
        id,
        timestamp: startTs,
        query: q,
        status: 'loading',
        reason: reason ?? null,
        results: [],
        insights: [],
        mutation_suggestions: [],
        error: null,
      },
    ].slice(-30))

    // Default collapse for older entries when viewing all.
    setCollapsed((prev) => {
      const next = { ...prev }
      next[id] = false
      return next
    })

    const minDelay = 650 + Math.random() * 650
    const delayP = new Promise((resolve) => setTimeout(resolve, minDelay))

    try {
      const apiP = searchYouCom(q, { signal: controller.signal, count: 8 })
      const [resp] = await Promise.all([apiP, delayP])

      const results = Array.isArray(resp?.results) ? resp.results : []
      const { insights, mutation_suggestions } = inferInsights(results)

      setInternalEntries((prev) =>
        prev.map((e) =>
          e.id === id
            ? {
                ...e,
                timestamp: resp?.timestamp ?? startTs,
                status: 'success',
                results,
                insights,
                mutation_suggestions,
              }
            : e,
        ),
      )

      onInsightGenerated?.({
        query: q,
        timestamp: resp?.timestamp ?? startTs,
        results,
        insights,
        mutation_suggestions,
        source: 'youcom',
      })
    } catch (err) {
      await delayP

      let errorMsg = err instanceof Error ? err.message : String(err)
      if (err instanceof YouComRateLimitError && err.retryAfterMs) {
        errorMsg = `Rate limited by You.com (retry after ~${Math.round(err.retryAfterMs / 1000)}s).`
      }

      const mock = generateYouComResponse(q)

      setInternalEntries((prev) =>
        prev.map((e) =>
          e.id === id
            ? {
                ...e,
                timestamp: mock.timestamp ?? startTs,
                status: 'mock',
                results: mock.results ?? [],
                insights: mock.insights ?? [],
                mutation_suggestions: mock.mutation_suggestions ?? [],
                error: errorMsg,
              }
            : e,
        ),
      )

      onInsightGenerated?.({
        query: q,
        timestamp: mock.timestamp ?? startTs,
        results: mock.results ?? [],
        insights: mock.insights ?? [],
        mutation_suggestions: mock.mutation_suggestions ?? [],
        source: 'mock',
        error: errorMsg,
      })
    } finally {
      setIsSearching(false)
      setActiveQuery('')
      abortRef.current = null
    }
  }

  useEffect(() => {
    if (!isActive) return undefined
    if (isControlled) return undefined

    const queries = makeGenerationQueries(currentGeneration)
    const genStartQuery = queries[0]
    const mutationQuery = queries[2] ?? queries[1]

    runSearch(genStartQuery, { reason: 'generation_start' })

    // "Mutation phase" trigger a bit later.
    const t = setTimeout(() => {
      if (!isActive) return
      if (genRef.current !== currentGeneration) return
      runSearch(mutationQuery, { reason: 'mutation_phase' })
    }, 2800)

    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentGeneration, isActive])

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-info-500/14 ring-1 ring-inset ring-info-500/25">
            <Search className="h-5 w-5 text-info-200" />
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-text-subtle">
              YOU.COM INTELLIGENCE STREAM
            </div>
            <div className="mt-0.5 text-sm text-text-muted">
              Generation {currentGeneration} intelligence and mutation guidance
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setViewAll((v) => !v)}
            className="inline-flex items-center gap-2 rounded-xl bg-panel-elevated px-3 py-2 text-xs font-semibold text-text ring-1 ring-inset ring-border/70 transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-info-500/25"
          >
            {viewAll ? (
              <>
                <ChevronUp className="h-4 w-4 text-text-muted" />
                Collapse
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 text-text-muted" />
                View all
              </>
            )}
          </button>

          {!isControlled ? (
            <button
              type="button"
              onClick={() => {
                const queries = makeGenerationQueries(currentGeneration)
                const manual = queries[1] ?? queries[0]
                runSearch(manual, { reason: 'manual' })
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-panel-elevated px-3 py-2 text-xs font-semibold text-text ring-1 ring-inset ring-border/70 transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-primary-500/25"
            >
              <RefreshCw className="h-4 w-4 text-text-muted" />
              Search now
            </button>
          ) : null}
        </div>
      </div>

      {isSearching ? (
        <div className="rounded-2xl border border-border/60 bg-panel-elevated p-4">
          <div className="flex items-center gap-3 text-sm">
            <MotionDiv
              animate={{ rotate: 360 }}
              transition={{ duration: 0.9, ease: 'linear', repeat: Infinity }}
              className="grid h-8 w-8 place-items-center rounded-xl bg-warning-500/14 ring-1 ring-inset ring-warning-500/25"
            >
              <Loader2 className="h-4 w-4 text-warning-200" />
            </MotionDiv>
            <div>
              <div className="text-xs font-semibold text-text">Searching…</div>
              <div className="mt-0.5 text-sm text-text-muted">
                <span className="font-mono text-text">{shortQuery(activeQuery, 72)}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {hiddenCount > 0 && !viewAll ? (
        <div className="rounded-2xl border border-border/60 bg-panel-elevated px-4 py-3 text-xs text-text-muted">
          <Sparkles className="mr-2 inline h-4 w-4 text-info-200" />
          {hiddenCount} older {hiddenCount === 1 ? 'entry' : 'entries'} hidden.
          <button
            type="button"
            onClick={() => setViewAll(true)}
            className="ml-2 font-semibold text-info-200 hover:text-info-100"
          >
            View all
          </button>
        </div>
      ) : null}

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-2 overflow-auto pr-1"
      >
        <AnimatePresence initial={false}>
          {visibleEntries.map((e, idx) => {
            const isOld = viewAll && idx < Math.max(0, visibleEntries.length - 2)
            const isCollapsed = collapsed[e.id] ?? isOld
            return (
              <EntryCard
                key={e.id}
                entry={e}
                index={idx}
                isCollapsed={isCollapsed}
                onToggleCollapse={() =>
                  setCollapsed((prev) => ({ ...prev, [e.id]: !isCollapsed }))
                }
              />
            )
          })}
        </AnimatePresence>

        <div ref={endRef} />
      </div>
    </div>
  )
}
