import { useEffect, useMemo, useState } from 'react'

import Layout from './components/Layout.jsx'
import EvolutionArena from './components/arena/EvolutionArena.jsx'
import APICostDashboard from './components/dashboard/APICostDashboard.jsx'
import MetricsDashboard from './components/dashboard/MetricsDashboard.jsx'
import YouComFeed from './components/feed/YouComFeed.jsx'
import ValidationViewer from './components/validation/ValidationViewer.jsx'
import LineageTree from './components/graph/LineageTree.jsx'
import StrategyGraphViewer from './components/graph/StrategyGraphViewer.jsx'
import {
  listRuns,
  getRunSummary,
  getRunLineage,
  getRunLLMUsage,
  connectToRunEvents,
} from './api/client.js'

export default function App() {
  return <DarwinAIDemo />
}

function DarwinAIDemo() {
  // Run selection state
  const [availableRuns, setAvailableRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [isLoadingRuns, setIsLoadingRuns] = useState(true)
  const [runLoadError, setRunLoadError] = useState(null)

  // Run data state
  const [runSummary, setRunSummary] = useState(null)
  const [lineageData, setLineageData] = useState(null)
  const [llmUsage, setLlmUsage] = useState(null)
  const [isLoadingRunData, setIsLoadingRunData] = useState(false)
  const [runDataError, setRunDataError] = useState(null)

  // UI state
  const [genIdx, setGenIdx] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [isAnimating, setIsAnimating] = useState(false)
  const [isPlaying, setIsPlaying] = useState(true)
  const [playbackSpeed, setPlaybackSpeed] = useState(2)

  // Load available runs on mount
  useEffect(() => {
    async function loadRuns() {
      try {
        setIsLoadingRuns(true)
        setRunLoadError(null)
        const data = await listRuns()
        const runs = data.runs || []
        setAvailableRuns(runs)

        // Auto-select the most recent run
        if (runs.length > 0) {
          setSelectedRunId(runs[0])
        }
      } catch (error) {
        console.error('Failed to load runs:', error)
        setRunLoadError(error.message)
      } finally {
        setIsLoadingRuns(false)
      }
    }

    loadRuns()
  }, [])

  // Load run data when a run is selected
  useEffect(() => {
    if (!selectedRunId) return

    async function loadRunData() {
      try {
        setIsLoadingRunData(true)
        setRunDataError(null)

        // Fetch all run data in parallel
        const [summary, lineage, usage] = await Promise.all([
          getRunSummary(selectedRunId),
          getRunLineage(selectedRunId),
          getRunLLMUsage(selectedRunId).catch(() => null), // Optional
        ])

        setRunSummary(summary)
        setLineageData(lineage)
        setLlmUsage(usage)
        setGenIdx(0) // Reset to first generation
        setSelectedId(null) // Clear selection
      } catch (error) {
        console.error('Failed to load run data:', error)
        setRunDataError(error.message)
      } finally {
        setIsLoadingRunData(false)
      }
    }

    loadRunData()
  }, [selectedRunId])

  // Build generations from run summary
  const generations = useMemo(() => {
    if (!runSummary?.generations) return []

    // Group strategies by generation
    const genMap = new Map()

    for (const strategy of runSummary.strategies || []) {
      const gen = strategy.generation || 0
      if (!genMap.has(gen)) {
        genMap.set(gen, [])
      }
      genMap.get(gen).push(strategy)
    }

    // Convert to sorted array
    const maxGen = Math.max(...genMap.keys(), 0)
    const result = []
    for (let i = 0; i <= maxGen; i++) {
      result.push(genMap.get(i) || [])
    }

    return result
  }, [runSummary])

  const currentGeneration = useMemo(
    () => generations[genIdx] ?? [],
    [genIdx, generations],
  )

  const selectedStrategy = useMemo(() => {
    if (!selectedId) return null
    const all = generations.flat()
    return all.find((x) => x?.id === selectedId) ?? null
  }, [generations, selectedId])

  const lineageGraphData = useMemo(() => {
    if (!lineageData) return { nodes: [], edges: [], roots: [] }

    const all = generations.flat()
    const nodes = all.map((s) => ({
      id: s.id,
      label: s.graph?.id ?? s.id,
      generation: s.generation ?? s.graph?.metadata?.generation,
      state: s.state,
      fitness: s.results?.phase3?.aggregated_fitness ?? s.results?.fitness,
      strategy: s,
    }))

    const edges = (lineageData.edges ?? []).map((e) => ({
      source: e.parent ?? e.source,
      target: e.child ?? e.target,
    }))

    return { nodes, edges, roots: lineageData.roots ?? [] }
  }, [generations, lineageData])

  // Playback animation
  useEffect(() => {
    if (generations.length === 0) return undefined
    if (!isPlaying) return undefined

    const ms = Math.max(250, Math.round(1400 / Math.max(1, playbackSpeed)))
    const t = setInterval(() => {
      setGenIdx((g) => (g + 1) % Math.max(1, generations.length))
      setIsAnimating(true)
      setTimeout(() => setIsAnimating(false), 360)
    }, ms)

    return () => clearInterval(t)
  }, [generations.length, isPlaying, playbackSpeed])

  // Auto-select best strategy in current generation
  useEffect(() => {
    if (selectedId) return
    if (!currentGeneration.length) return

    const best =
      currentGeneration
        .filter((s) => s.state !== 'dead')
        .slice()
        .sort(
          (a, b) => {
            const aFit = a.results?.phase3?.aggregated_fitness ?? a.results?.fitness ?? 0
            const bFit = b.results?.phase3?.aggregated_fitness ?? b.results?.fitness ?? 0
            return bFit - aFit
          }
        )[0] ?? currentGeneration[0]

    setTimeout(() => setSelectedId(best?.id ?? null), 0)
  }, [currentGeneration, selectedId])

  // Loading state
  if (isLoadingRuns) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: '#fff',
        fontFamily: 'monospace'
      }}>
        Loading runs...
      </div>
    )
  }

  // Error state
  if (runLoadError) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: '#ff4444',
        fontFamily: 'monospace',
        padding: '20px',
        textAlign: 'center'
      }}>
        <div>Failed to load runs</div>
        <div style={{ marginTop: '10px', fontSize: '14px' }}>{runLoadError}</div>
        <button
          onClick={() => window.location.reload()}
          style={{
            marginTop: '20px',
            padding: '10px 20px',
            background: '#333',
            color: '#fff',
            border: '1px solid #666',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  // No runs state
  if (availableRuns.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: '#fff',
        fontFamily: 'monospace',
        textAlign: 'center'
      }}>
        <div>No evolution runs found</div>
        <div style={{ marginTop: '10px', fontSize: '14px', color: '#888' }}>
          Start a new run using the backend API
        </div>
      </div>
    )
  }

  // Loading run data
  if (isLoadingRunData) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: '#fff',
        fontFamily: 'monospace'
      }}>
        Loading run data...
      </div>
    )
  }

  // Run data error
  if (runDataError) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: '#ff4444',
        fontFamily: 'monospace',
        padding: '20px',
        textAlign: 'center'
      }}>
        <div>Failed to load run data</div>
        <div style={{ marginTop: '10px', fontSize: '14px' }}>{runDataError}</div>
      </div>
    )
  }

  return (
    <Layout
      currentGeneration={genIdx}
      isPlaying={isPlaying}
      playbackSpeed={playbackSpeed}
      onPlayPause={() => setIsPlaying((v) => !v)}
      onSpeedChange={(s) => setPlaybackSpeed(s)}
      selectedStrategy={selectedStrategy}
      availableRuns={availableRuns}
      selectedRunId={selectedRunId}
      onRunSelect={(runId) => setSelectedRunId(runId)}
    >
      <Layout.Arena>
        <EvolutionArena
          strategies={currentGeneration}
          generationNumber={genIdx}
          onStrategySelect={(s) => setSelectedId(s?.id ?? null)}
          selectedStrategyId={selectedId}
        />
      </Layout.Arena>

      <Layout.Validation>
        <ValidationViewer strategy={selectedStrategy} isAnimating={isAnimating} />
      </Layout.Validation>

      <Layout.Graph>
        <StrategyGraphViewer strategyGraph={selectedStrategy?.graph ?? null} />
      </Layout.Graph>

      <Layout.Lineage>
        <LineageTree
          lineageData={lineageGraphData}
          selectedStrategyId={selectedId}
          onStrategySelect={(payload) => {
            const id = typeof payload === 'string' ? payload : payload?.id
            if (id) setSelectedId(id)
          }}
          generationCount={generations.length}
        />
      </Layout.Lineage>

      <Layout.YouFeed>
        <YouComFeed
          isActive={isPlaying}
          currentGeneration={genIdx}
          runId={selectedRunId}
          onInsightGenerated={() => {}}
        />
      </Layout.YouFeed>

      <Layout.ApiCosts>
        <APICostDashboard
          runId={selectedRunId}
          costData={llmUsage}
          currentGeneration={genIdx}
          totalGenerations={generations.length || 1}
        />
      </Layout.ApiCosts>

      <Layout.Metrics>
        <MetricsDashboard
          generationStats={{ strategies: currentGeneration, generationNumber: genIdx }}
          selectedStrategy={selectedStrategy}
          allGenerations={generations}
        />
      </Layout.Metrics>
    </Layout>
  )
}
