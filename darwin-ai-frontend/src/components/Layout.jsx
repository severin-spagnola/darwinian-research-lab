import { Children, isValidElement, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity,
  ChevronDown,
  ChevronUp,
  CircleDollarSign,
  Dna,
  GitBranch,
  LayoutGrid,
  Network,
  FlaskConical,
  Sparkles,
} from 'lucide-react'

import PlaybackControls from './controls/PlaybackControls.jsx'

function createSlot(slotName) {
  function Slot({ children }) {
    return children ?? null
  }
  Slot.slotName = slotName
  Slot.displayName = `Layout.${slotName}`
  return Slot
}

const ArenaSlot = createSlot('arena')
const ValidationSlot = createSlot('validation')
const GraphSlot = createSlot('graph')
const LineageSlot = createSlot('lineage')
const YouFeedSlot = createSlot('youFeed')
const ApiCostsSlot = createSlot('apiCosts')
const MetricsSlot = createSlot('metrics')

function formatTime(d) {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const MotionDiv = motion.div

function extractSlots(children) {
  const slots = {
    arena: null,
    validation: null,
    graph: null,
    lineage: null,
    youFeed: null,
    apiCosts: null,
    metrics: null,
  }

  Children.toArray(children).forEach((child) => {
    if (!isValidElement(child)) return
    const slotName = child.type?.slotName
    if (!slotName) return
    if (!(slotName in slots)) return
    slots[slotName] = child.props?.children ?? null
  })

  return slots
}

export default function Layout({
  currentGeneration,
  totalGenerations = 5,
  currentPhase = 'intro',
  isPlaying,
  playbackSpeed,
  onPlayPause,
  onSpeedChange,
  onNextGeneration,
  selectedStrategy,
  activeLeftTab,
  onLeftTabChange,
  ControlsComponent,
  children,
}) {
  const [uncontrolledTab, setUncontrolledTab] = useState('arena')
  const [isFeedOpen, setIsFeedOpen] = useState(true)
  const [now, setNow] = useState(() => new Date())

  const tabKey = activeLeftTab ?? uncontrolledTab
  const setTab =
    typeof onLeftTabChange === 'function'
      ? onLeftTabChange
      : activeLeftTab !== undefined
        ? () => {}
        : setUncontrolledTab

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const slots = useMemo(() => extractSlots(children), [children])
  const hasAnySlot = useMemo(
    () => Object.values(slots).some((v) => v !== null && v !== undefined),
    [slots],
  )

  // If no slot wrappers were used, treat `children` as Arena content.
  const resolvedSlots = useMemo(() => {
    if (hasAnySlot) return slots
    return { ...slots, arena: children ?? null }
  }, [children, hasAnySlot, slots])

  const tabDefs = useMemo(
    () => [
      { key: 'arena', label: 'Arena', icon: LayoutGrid },
      { key: 'validation', label: 'Validation', icon: FlaskConical },
      { key: 'graph', label: 'Graph', icon: Network },
      { key: 'lineage', label: 'Lineage', icon: GitBranch },
    ],
    [],
  )

  const activeContent = useMemo(() => {
    if (tabKey === 'arena') return resolvedSlots.arena
    if (tabKey === 'validation') return resolvedSlots.validation
    if (tabKey === 'graph') return resolvedSlots.graph
    if (tabKey === 'lineage') return resolvedSlots.lineage
    return null
  }, [resolvedSlots, tabKey])

  const selectedLabel = useMemo(() => {
    if (!selectedStrategy) return 'None selected'
    return (
      selectedStrategy?.name ??
      selectedStrategy?.id ??
      selectedStrategy?.graph?.name ??
      selectedStrategy?.graph?.id ??
      'Selected'
    )
  }, [selectedStrategy])

  const Controls = ControlsComponent ?? PlaybackControls

  const panelChrome =
    'shadow-[0_0_0_1px_rgba(34,211,238,0.05),0_0_24px_rgba(16,185,129,0.06)] ring-1 ring-inset ring-info-500/10 transition-shadow'

  return (
    <div className="flex h-screen flex-col bg-bg">
      <header className="border-b border-border/70 bg-panel">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl bg-primary-500/15 ring-1 ring-inset ring-primary-500/25">
              <Dna className="h-5 w-5 text-primary-200" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="truncate text-sm font-semibold tracking-wide">
                  Darwin AI
                </div>
                <span className="rounded-full bg-panel-elevated px-2.5 py-1 text-xs font-medium text-text-muted ring-1 ring-inset ring-border/70">
                  Generation {currentGeneration}
                </span>
              </div>
              <div className="mt-0.5 truncate text-xs text-text-muted">
                {isPlaying ? 'Auto-playing' : 'Paused'} • {formatTime(now)}
              </div>
            </div>
          </div>

          <div className="hidden items-center gap-3 sm:flex">
            <div className="rounded-xl bg-panel-elevated px-3 py-2 text-xs text-text-muted ring-1 ring-inset ring-border/70">
              Selected: <span className="text-text">{selectedLabel}</span>
            </div>
          </div>
        </div>
      </header>

      {/* On small screens, allow the page to scroll so the right column panels aren't clipped. */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto min-h-full max-w-7xl px-4 py-3 sm:px-6">
          <div className="grid h-auto min-h-0 grid-cols-1 gap-3 lg:h-full lg:grid-cols-5">
            <section
              className={`panel ${panelChrome} flex min-h-0 flex-col overflow-hidden lg:col-span-3`}
            >
              <div className="panel-header">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  {tabDefs.map((t) => {
                    const Icon = t.icon
                    const active = tabKey === t.key
                    return (
                      <button
                        key={t.key}
                        type="button"
                        onClick={() => setTab(t.key)}
                        className={[
                          'inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition',
                          'focus:outline-none focus:ring-2 focus:ring-primary-500/30',
                          active
                            ? 'bg-primary-500/12 text-primary-200 ring-1 ring-inset ring-primary-500/25'
                            : 'text-text-muted hover:bg-white/5 hover:text-text',
                        ].join(' ')}
                        aria-pressed={active}
                      >
                        <Icon className="h-4 w-4" />
                        {t.label}
                      </button>
                    )
                  })}
                </div>

                <div className="hidden text-xs text-text-muted md:block">
                  {selectedLabel}
                </div>
              </div>

              <div className="panel-body min-h-0 flex-1 overflow-auto">
                <AnimatePresence mode="wait">
                  <MotionDiv
                    key={tabKey}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.16, ease: 'easeOut' }}
                    className="min-h-[240px]"
                  >
                    {activeContent ?? (
                      <div className="grid place-items-center rounded-xl border border-border/60 bg-panel-elevated p-10 text-center">
                        <div className="text-sm font-semibold">
                          {tabDefs.find((t) => t.key === tabKey)?.label ??
                            'Panel'}
                        </div>
                        <div className="mt-2 max-w-md text-sm text-text-muted">
                          No content provided yet. Pass a slot like{' '}
                          <span className="font-mono text-text">
                            &lt;Layout.Arena&gt;
                          </span>{' '}
                          to render your UI here.
                        </div>
                      </div>
                    )}
                  </MotionDiv>
                </AnimatePresence>
              </div>
            </section>

            <aside className="flex min-h-0 flex-col gap-3 lg:col-span-2">
              <section className={`panel ${panelChrome} flex flex-col overflow-hidden`}>
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-info-200" />
                    <div className="text-sm font-semibold">You.com Feed</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsFeedOpen((v) => !v)}
                    className="inline-flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-medium text-text-muted transition hover:bg-white/5 hover:text-text focus:outline-none focus:ring-2 focus:ring-info-500/25"
                    aria-expanded={isFeedOpen}
                  >
                    {isFeedOpen ? (
                      <>
                        <ChevronUp className="h-4 w-4" />
                        Collapse
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-4 w-4" />
                        Expand
                      </>
                    )}
                  </button>
                </div>

                <AnimatePresence initial={false}>
                  {isFeedOpen ? (
                    <MotionDiv
                      key="feed"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.18, ease: 'easeOut' }}
                      className="overflow-hidden"
                    >
                      <div className="panel-body max-h-[30vh] overflow-auto">
                        {resolvedSlots.youFeed ?? (
                          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4 text-sm text-text-muted">
                            Provide <span className="font-mono text-text">&lt;Layout.YouFeed&gt;</span>{' '}
                            content to render intelligence results.
                          </div>
                        )}
                      </div>
                    </MotionDiv>
                  ) : null}
                </AnimatePresence>
              </section>

              <section
                className={`panel ${panelChrome} flex min-h-0 flex-1 flex-col overflow-hidden`}
              >
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <CircleDollarSign className="h-4 w-4 text-primary-200" />
                    <div className="text-sm font-semibold">API Costs</div>
                  </div>
                  <div className="text-xs text-text-muted">Tracking</div>
                </div>
                <div className="panel-body min-h-0 flex-1 overflow-auto">
                  {resolvedSlots.apiCosts ?? (
                    <div className="rounded-xl border border-border/60 bg-panel-elevated p-4 text-sm text-text-muted">
                      Provide <span className="font-mono text-text">&lt;Layout.ApiCosts&gt;</span>{' '}
                      content to render cost tracking.
                    </div>
                  )}
                </div>
              </section>

              <section className={`panel ${panelChrome} flex flex-col overflow-hidden`}>
                <div className="panel-header">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-warning-200" />
                    <div className="text-sm font-semibold">Metrics</div>
                  </div>
                  <div className="text-xs text-text-muted">Live</div>
                </div>
                <div className="panel-body">
                  {resolvedSlots.metrics ?? (
                    <div className="rounded-xl border border-border/60 bg-panel-elevated p-4 text-sm text-text-muted">
                      Provide <span className="font-mono text-text">&lt;Layout.Metrics&gt;</span>{' '}
                      content to render metrics.
                    </div>
                  )}
                </div>
              </section>
            </aside>
          </div>
        </div>
      </div>

      <footer className="border-t border-border/70 bg-panel">
        <div className="mx-auto max-w-7xl px-4 py-2 sm:px-6">
          <Controls
            isPlaying={isPlaying}
            onPlayPause={onPlayPause}
            playbackSpeed={playbackSpeed}
            onSpeedChange={onSpeedChange}
            currentGeneration={currentGeneration}
            totalGenerations={totalGenerations}
            currentPhase={currentPhase}
            onNextGeneration={onNextGeneration}
          />
        </div>
      </footer>
    </div>
  )
}

Layout.Arena = ArenaSlot
Layout.Validation = ValidationSlot
Layout.Graph = GraphSlot
Layout.Lineage = LineageSlot
Layout.YouFeed = YouFeedSlot
Layout.ApiCosts = ApiCostsSlot
Layout.Metrics = MetricsSlot

export {
  ArenaSlot as LayoutArena,
  ApiCostsSlot as LayoutApiCosts,
  GraphSlot as LayoutGraph,
  LineageSlot as LayoutLineage,
  MetricsSlot as LayoutMetrics,
  ValidationSlot as LayoutValidation,
  YouFeedSlot as LayoutYouFeed,
}
