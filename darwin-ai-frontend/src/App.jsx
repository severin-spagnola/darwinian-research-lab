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
  generateAPICosts,
  generateEvolutionRun,
} from './data/mockDataGenerator.js'

export default function App() {
  return <DarwinAIDemo />
}

function DarwinAIDemo() {
  const [isPlaying, setIsPlaying] = useState(true)
  const [playbackSpeed, setPlaybackSpeed] = useState(2)
  const [genIdx, setGenIdx] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [isAnimating, setIsAnimating] = useState(false)

  const run = useMemo(() => generateEvolutionRun(5), [])

  const generations = useMemo(() => run.generations ?? [], [run.generations])
  const currentGeneration = useMemo(
    () => generations[genIdx] ?? [],
    [genIdx, generations],
  )

  const selectedStrategy = useMemo(() => {
    if (!selectedId) return null
    const all = generations.flat()
    return all.find((x) => x?.id === selectedId) ?? null
  }, [generations, selectedId])

  const lineageData = useMemo(() => {
    const all = generations.flat()
    const nodes = all.map((s) => ({
      id: s.id,
      label: s.graph?.id ?? s.id,
      generation: s.graph?.metadata?.generation,
      state: s.state,
      fitness: s.results?.phase3?.aggregated_fitness,
      strategy: s,
    }))
    const edges = (run.lineage?.edges ?? []).map((e) => ({
      source: e.parent ?? e.source,
      target: e.child ?? e.target,
    }))
    return { nodes, edges, roots: run.lineage?.roots ?? [] }
  }, [generations, run.lineage?.edges, run.lineage?.roots])

  const api = useMemo(
    () => generateAPICosts(generations.length || 5, generations.flat().length),
    [generations],
  )

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

  useEffect(() => {
    if (selectedId) return
    if (!currentGeneration.length) return

    const best =
      currentGeneration
        .filter((s) => s.state !== 'dead')
        .slice()
        .sort(
          (a, b) =>
            (b.results?.phase3?.aggregated_fitness ?? 0) -
            (a.results?.phase3?.aggregated_fitness ?? 0),
        )[0] ?? currentGeneration[0]

    setTimeout(() => setSelectedId(best?.id ?? null), 0)
  }, [currentGeneration, selectedId])

  return (
    <Layout
      currentGeneration={genIdx}
      isPlaying={isPlaying}
      playbackSpeed={playbackSpeed}
      onPlayPause={() => setIsPlaying((v) => !v)}
      onSpeedChange={(s) => setPlaybackSpeed(s)}
      selectedStrategy={selectedStrategy}
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
          lineageData={lineageData}
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
          onInsightGenerated={() => {}}
        />
      </Layout.YouFeed>

      <Layout.ApiCosts>
        <APICostDashboard
          costData={api}
          currentGeneration={genIdx}
          totalGenerations={generations.length || 5}
          updateInterval={1000}
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
