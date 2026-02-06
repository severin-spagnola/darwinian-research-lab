import { useEffect, useMemo, useState } from 'react'
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
  getRunSummary,
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
  const [showCreator, setShowCreator] = useState(false)

  // Mock data fallback
  const mockData = useMemo(() => generateEvolutionRun(5), [])

  // On mount: try backend, fall back to mock
  useEffect(() => {
    let cancelled = false

    async function tryBackend() {
      try {
        const data = await listRuns()
        const runs = data.runs || []
        if (cancelled) return

        if (runs.length > 0) {
          setAvailableRuns(runs)
          setSelectedRunId(runs[0])
          setUseRealData(true)
        } else {
          // Backend up but no runs - use mock
          setUseRealData(false)
        }
      } catch {
        // Backend unreachable - use mock
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
        const [summary, usage] = await Promise.all([
          getRunSummary(selectedRunId),
          getRunLLMUsage(selectedRunId).catch(() => null),
        ])
        if (cancelled) return
        setRealRunData(summary)
        setRealLlmUsage(usage)
      } catch (err) {
        console.error('Failed to load run data:', err)
        if (!cancelled) setUseRealData(false) // Fall back to mock
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
    console.log('New run created:', runId)
    setShowCreator(false)
    setSelectedRunId(runId)
    setAvailableRuns(prev => [runId, ...prev])
    setUseRealData(true)
    // Reload data
    window.location.reload()
  }

  // Still checking backend
  if (useRealData === null) {
    return <BootScreen />
  }

  // Show RunCreator if no real data and user wants to create a run
  if (!useRealData && showCreator) {
    return (
      <div className="min-h-screen bg-bg">
        <div className="container mx-auto py-12">
          <button
            onClick={() => setShowCreator(false)}
            className="mb-4 text-sm text-text-muted hover:text-text transition-colors"
          >
            ← Back to Demo Data
          </button>
          <RunCreator onRunCreated={handleRunCreated} />
        </div>
      </div>
    )
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

      {/* Show "Create Run" button if using mock data */}
      {!useRealData && !booting && (
        <div className="fixed top-4 right-4 z-50">
          <button
            onClick={() => setShowCreator(true)}
            className="px-4 py-2 bg-success-500 hover:bg-success-600 text-white font-medium rounded-lg shadow-lg transition-colors flex items-center gap-2"
          >
            <Dna className="w-4 h-4" />
            Create Real Run
          </button>
        </div>
      )}

      {/* Keep the app mounted under the boot screen so playback state is ready when it fades. */}
      <div className={booting ? 'pointer-events-none fixed inset-0 opacity-0' : 'block'}>
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
              simulate={!useRealData}
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
    </>
  )
}
