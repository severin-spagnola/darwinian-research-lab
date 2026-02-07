import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Dna, Loader2 } from 'lucide-react'

import Layout from './components/Layout.jsx'
import EvolutionArena from './components/arena/EvolutionArena.jsx'
import ValidationViewer from './components/validation/ValidationViewer.jsx'
import LineageTree from './components/graph/LineageTree.jsx'
import StrategyGraphViewer from './components/graph/StrategyGraphViewer.jsx'
import YouComFeed from './components/feed/YouComFeed.jsx'
import APICostDashboard from './components/dashboard/APICostDashboard.jsx'
import MetricsDashboard from './components/dashboard/MetricsDashboard.jsx'
import PlaybackControls from './components/controls/PlaybackControls.jsx'
import RunCreator from './components/RunCreator.jsx'

import useEvolutionPlayback from './hooks/useEvolutionPlayback.js'
import { generateEvolutionRun } from './data/mockDataGenerator.js'
import {
  listRuns,
  getRunPlayback,
  getRunLLMUsage,
} from './api/client.js'

const MotionDiv = motion.div

function BootScreen() {
  return (
    <div className="relative grid h-screen w-screen place-items-center overflow-hidden bg-bg text-text">
      <div className="pointer-events-none absolute inset-0 opacity-70 [mask-image:radial-gradient(circle_at_center,rgba(0,0,0,0.85),transparent_65%)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(34,211,238,0.12)_1px,transparent_0)] [background-size:28px_28px]" />
      </div>

      <div className="relative mx-auto w-full max-w-md px-6">
        <div className="rounded-3xl border border-border/70 bg-panel-elevated p-6 shadow-[0_0_0_1px_rgba(34,211,238,0.08),0_0_40px_rgba(16,185,129,0.10)]">
          <div className="flex items-center gap-4">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-500/15 ring-1 ring-inset ring-primary-500/25">
              <Dna className="h-6 w-6 text-primary-200" />
            </div>
            <div className="min-w-0">
              <div className="text-lg font-bold tracking-wide">Darwin AI</div>
              <div className="mt-0.5 text-sm text-text-muted">
                Booting evolution lab…
              </div>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-3 rounded-2xl border border-border/60 bg-panel px-4 py-3">
            <MotionDiv
              animate={{ rotate: 360 }}
              transition={{ duration: 0.9, ease: 'linear', repeat: Infinity }}
              className="grid h-9 w-9 place-items-center rounded-xl bg-info-500/14 ring-1 ring-inset ring-info-500/25"
              aria-hidden="true"
            >
              <Loader2 className="h-4 w-4 text-info-200" />
            </MotionDiv>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-text">Loading evolution data</div>
              <div className="mt-0.5 text-xs text-text-subtle">
                Initializing strategies, validation episodes, and dashboards…
              </div>
            </div>
          </div>

          <div className="mt-5 h-2 w-full overflow-hidden rounded-full bg-bg-subtle ring-1 ring-inset ring-border/70">
            <MotionDiv
              className="h-full rounded-full bg-gradient-to-r from-primary-400 via-info-400 to-primary-300"
              initial={{ width: '0%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 2.0, ease: 'easeInOut' }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  // Try to load real data from backend; fall back to mock if unavailable
  const [useRealData, setUseRealData] = useState(null) // null = checking
  const [realRunData, setRealRunData] = useState(null)
  const [realLlmUsage, setRealLlmUsage] = useState(null)
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [availableRuns, setAvailableRuns] = useState([])
  const [runLoadError, setRunLoadError] = useState(null)
  const [isLoadingRun, setIsLoadingRun] = useState(false)
  const [demoMode, setDemoMode] = useState(true)
  const labRef = useRef(null)

  // Mock data fallback
  const mockData = useMemo(() => generateEvolutionRun(5), [])

  // On mount: try backend, fall back to mock
  useEffect(() => {
    let cancelled = false

    async function tryBackend() {
      try {
        console.log('[Darwin] Checking backend for runs...')
        const data = await listRuns()
        const runs = data.runs || []
        console.log(`[Darwin] Backend returned ${runs.length} runs:`, runs.map(r => r.run_id || r))
        if (cancelled) return

        if (runs.length > 0) {
          const runIds = runs.map(r => r.run_id || r)
          setAvailableRuns(runIds)
          setSelectedRunId(runIds[0])
          setUseRealData(true)
          console.log('[Darwin] Using real backend data, selected:', runIds[0])
        } else {
          setUseRealData(false)
          console.log('[Darwin] No runs found, falling back to mock data')
        }
      } catch (err) {
        console.warn('[Darwin] Backend unreachable, using mock data:', err.message)
        if (!cancelled) setUseRealData(false)
      }
    }

    tryBackend()
    return () => { cancelled = true }
  }, [])

  // Load real run data when selected
  useEffect(() => {
    if (!useRealData || !selectedRunId) return
    let cancelled = false

    async function load() {
      try {
        setIsLoadingRun(true)
        setRunLoadError(null)
        console.log(`[Darwin] Loading run: ${selectedRunId}`)

        // Poll summary because newly-created runs may not have results immediately.
        const poll = async (fn, label, { maxAttempts = 60, delayMs = 2000 } = {}) => {
          let lastErr = null
          for (let i = 0; i < maxAttempts; i += 1) {
            if (cancelled) return null
            try {
              const result = await fn()
              console.log(`[Darwin] ${label} loaded (attempt ${i + 1})`)
              return result
            } catch (err) {
              lastErr = err
              if (i < 3 || i % 10 === 0) console.log(`[Darwin] ${label} attempt ${i + 1} failed: ${err.message}`)
              await new Promise((r) => setTimeout(r, delayMs))
            }
          }
          throw lastErr ?? new Error('Timed out')
        }

        const playbackData = await poll(() => getRunPlayback(selectedRunId), 'playback', {
          maxAttempts: 60,
          delayMs: 2000,
        })

        console.log(`[Darwin] Playback data:`, {
          generations: playbackData?.generations?.length,
          strategies: playbackData?.generations?.flat()?.length,
          champion: playbackData?.champion?.id,
        })

        const usage = await poll(() => getRunLLMUsage(selectedRunId), 'llm/usage', {
          maxAttempts: 3,
          delayMs: 1000,
        }).catch(() => null)

        if (cancelled) return
        setRealRunData(playbackData)
        setRealLlmUsage(usage)
        setIsLoadingRun(false)
        console.log('[Darwin] Run loaded successfully')
      } catch (err) {
        if (cancelled) return
        setIsLoadingRun(false)
        setRunLoadError(err instanceof Error ? err.message : String(err))
        console.error('[Darwin] Failed to load run:', err)
      }
    }

    load()
    return () => { cancelled = true }
  }, [useRealData, selectedRunId])

  // Pick data source
  const evolutionData = useRealData && realRunData ? realRunData : mockData

  // Playback hook works with whatever data source we have
  const {
    currentGeneration,
    currentPhase,
    isPlaying,
    playbackSpeed,
    strategies,
    selectedStrategy,
    youComActivity,
    apiCosts,
    play,
    pause,
    setSpeed,
    selectStrategy,
    nextGeneration,
  } = useEvolutionPlayback(evolutionData, { initialIsPlaying: false })

  const totalGenerations = useMemo(() => {
    const gens = evolutionData?.generations
    return Array.isArray(gens) ? gens.length : 5
  }, [evolutionData])

  const [activeLeftTab, setActiveLeftTab] = useState('arena')
  const [booting, setBooting] = useState(true)

  // Boot screen + delayed autoplay
  useEffect(() => {
    pause()
    const t = setTimeout(() => {
      setBooting(false)
      play()
    }, 2000)
    return () => clearTimeout(t)
  }, [pause, play])

  // Build lineage data
  const lineageData = useMemo(() => {
    const gens = evolutionData?.generations ?? []
    const upto = Array.isArray(gens) ? gens.slice(0, Math.max(0, Math.min(gens.length, currentGeneration + 1))) : []
    const all = upto.flat()

    const liveById = new Map((Array.isArray(strategies) ? strategies : []).map((s) => [s.id, s]))
    const nodes = all.map((s) => ({
      id: s.id,
      label: (liveById.get(s.id)?.graph?.id ?? s.graph?.id) ?? s.id,
      generation: liveById.get(s.id)?.graph?.metadata?.generation ?? s.graph?.metadata?.generation,
      state: liveById.get(s.id)?.state ?? s.state,
      fitness:
        liveById.get(s.id)?.results?.phase3?.aggregated_fitness ??
        liveById.get(s.id)?.results?.fitness ??
        s.results?.phase3?.aggregated_fitness ??
        s.results?.fitness,
      strategy: liveById.get(s.id) ?? s,
    }))

    const visible = new Set(nodes.map((n) => n.id))
    const edges = (evolutionData?.lineage?.edges ?? [])
      .map((e) => ({
        source: e.parent ?? e.source,
        target: e.child ?? e.target,
      }))
      .filter((e) => visible.has(e.source) && visible.has(e.target))

    return {
      nodes,
      edges,
      roots: (evolutionData?.lineage?.roots ?? []).filter((r) => visible.has(r)),
    }
  }, [currentGeneration, evolutionData, strategies])

  // Use real LLM usage if available, otherwise use playback costs
  const costData = useRealData && realLlmUsage ? realLlmUsage : apiCosts

  // Handler for when a new run is created
  const handleRunCreated = async (runId) => {
    const id = String(runId)
    setRealRunData(null)
    setRealLlmUsage(null)
    setRunLoadError(null)
    setSelectedRunId(id)
    setAvailableRuns((prev) => [id, ...(Array.isArray(prev) ? prev : [])])
    setUseRealData(true)

    // Scroll into the lab UI after submitting a prompt.
    setTimeout(() => {
      labRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 100)
  }

  // Still checking backend
  if (useRealData === null) {
    return <BootScreen />
  }

  return (
    <>
      <AnimatePresence initial>
        {booting ? (
          <MotionDiv
            key="boot"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            <BootScreen />
          </MotionDiv>
        ) : null}
      </AnimatePresence>

      {/* Keep the app mounted under the boot screen so playback state is ready when it fades. */}
      <div className={booting ? 'pointer-events-none fixed inset-0 opacity-0' : 'block'}>
        <div className="bg-bg">
          <div className="mx-auto max-w-screen-2xl px-3 py-4 sm:px-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-text">
                <button
                  type="button"
                  onClick={() => setDemoMode(d => !d)}
                  className={`grid h-9 w-9 place-items-center rounded-2xl ring-1 ring-inset transition-colors ${
                    demoMode
                      ? 'bg-info-500/25 ring-info-500/40'
                      : 'bg-primary-500/15 ring-primary-500/25'
                  }`}
                  title={demoMode ? 'Demo mode (click for live)' : 'Live mode (click for demo)'}
                >
                  <Dna className={`h-4 w-4 ${demoMode ? 'text-info-300' : 'text-primary-200'}`} />
                </button>
                <div className="min-w-0">
                  <div className="truncate">Create a Darwin run</div>
                  <div className="mt-0.5 text-xs font-medium text-text-muted">
                    Prompt the system, then scroll into the lab to watch evolution.
                  </div>
                </div>
              </div>

              <div className="hidden items-center gap-2 md:flex">
                {selectedRunId ? (
                  <div className="rounded-full bg-panel-elevated px-3 py-1.5 text-xs text-text-muted ring-1 ring-inset ring-border/70">
                    Run: <span className="font-mono text-text">{selectedRunId}</span>
                  </div>
                ) : null}
              </div>
            </div>

            {isLoadingRun ? (
              <div className="mb-3 rounded-2xl border border-border/70 bg-panel-elevated px-4 py-3 text-sm text-text-muted">
                Loading run results from backend (polling)…
              </div>
            ) : null}

            {runLoadError ? (
              <div className="mb-3 rounded-2xl border border-danger-500/35 bg-danger-500/10 px-4 py-3 text-sm text-danger-100">
                Backend run data is not ready yet: <span className="font-mono">{runLoadError}</span>
              </div>
            ) : null}

            <RunCreator onRunCreated={handleRunCreated} demoMode={demoMode} />
          </div>

          <div ref={labRef}>
            <Layout
              currentGeneration={currentGeneration}
              totalGenerations={totalGenerations}
              currentPhase={currentPhase}
              isPlaying={isPlaying}
              playbackSpeed={playbackSpeed}
              onPlayPause={() => (isPlaying ? pause() : play())}
              onSpeedChange={(s) => setSpeed(s)}
              onNextGeneration={() => nextGeneration()}
              selectedStrategy={selectedStrategy}
              activeLeftTab={activeLeftTab}
              onLeftTabChange={setActiveLeftTab}
              ControlsComponent={PlaybackControls}
              availableRuns={availableRuns}
              selectedRunId={selectedRunId}
              onRunSelect={(runId) => setSelectedRunId(runId)}
              useRealData={useRealData}
            >
              <Layout.Arena>
                <EvolutionArena
                  strategies={strategies}
                  generationNumber={currentGeneration}
                  onStrategySelect={(s) => selectStrategy(s?.id ?? null)}
                  selectedStrategyId={selectedStrategy?.id ?? null}
                />
              </Layout.Arena>

              <Layout.Validation>
                <ValidationViewer
                  strategy={selectedStrategy}
                  isAnimating={currentPhase === 'validation'}
                />
              </Layout.Validation>

              <Layout.Graph>
                <StrategyGraphViewer strategyGraph={selectedStrategy?.graph ?? null} />
              </Layout.Graph>

              <Layout.Lineage>
                <LineageTree
                  lineageData={lineageData}
                  selectedStrategyId={selectedStrategy?.id ?? null}
                  onStrategySelect={(payload) => {
                    const id = typeof payload === 'string' ? payload : payload?.id
                    if (id) selectStrategy(id)
                  }}
                  generationCount={totalGenerations}
                />
              </Layout.Lineage>

              <Layout.YouFeed>
                <YouComFeed
                  entries={youComActivity}
                  isActive={false}
                  currentGeneration={currentGeneration}
                  runId={selectedRunId}
                  onInsightGenerated={() => {}}
                />
              </Layout.YouFeed>

              <Layout.ApiCosts>
                <APICostDashboard
                  costData={costData}
                  currentGeneration={currentGeneration}
                  totalGenerations={totalGenerations}
                  updateInterval={1000}
                  simulate={true}
                />
              </Layout.ApiCosts>

              <Layout.Metrics>
                <MetricsDashboard
                  generationStats={{
                    strategies,
                    generationNumber: currentGeneration,
                  }}
                  selectedStrategy={selectedStrategy}
                  allGenerations={(evolutionData?.generations ?? []).slice(
                    0,
                    Math.max(0, Math.min(totalGenerations, currentGeneration + 1)),
                  )}
                />
              </Layout.Metrics>
            </Layout>
          </div>
        </div>
      </div>
    </>
  )
}
