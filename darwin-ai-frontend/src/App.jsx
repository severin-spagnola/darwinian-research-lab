import { useMemo } from 'react'

import Layout from './components/Layout.jsx'
import EvolutionArena from './components/arena/EvolutionArena.jsx'
import APICostDashboard from './components/dashboard/APICostDashboard.jsx'
import MetricsDashboard from './components/dashboard/MetricsDashboard.jsx'
import YouComFeed from './components/feed/YouComFeed.jsx'
import ValidationViewer from './components/validation/ValidationViewer.jsx'
import LineageTree from './components/graph/LineageTree.jsx'
import StrategyGraphViewer from './components/graph/StrategyGraphViewer.jsx'

import useEvolutionPlayback from './hooks/useEvolutionPlayback.js'
import { generateAPICosts, generateEvolutionRun } from './data/mockDataGenerator.js'

export default function App() {
  return <DarwinAIDemo />
}

function DarwinAIDemo() {
  const run = useMemo(() => generateEvolutionRun(5), [])

  const playback = useEvolutionPlayback(run)
  const {
    currentGeneration: genIdx,
    currentPhase,
    isPlaying,
    playbackSpeed,
    strategies: currentGeneration,
    selectedStrategy,
    youComActivity,
    play,
    pause,
    setSpeed,
    selectStrategy,
    nextGeneration,
  } = playback

  const generations = useMemo(() => run.generations ?? [], [run.generations])
  const totalGenerations = generations.length || 5

  const lineageData = useMemo(() => {
    const upto = generations.slice(0, Math.max(0, Math.min(generations.length, genIdx + 1)))
    const all = upto.flat()

    const liveById = new Map((currentGeneration ?? []).map((s) => [s.id, s]))
    const nodes = all.map((s) => ({
      id: s.id,
      label: (liveById.get(s.id)?.graph?.id ?? s.graph?.id) ?? s.id,
      generation: liveById.get(s.id)?.graph?.metadata?.generation ?? s.graph?.metadata?.generation,
      state: liveById.get(s.id)?.state ?? s.state,
      fitness:
        liveById.get(s.id)?.results?.phase3?.aggregated_fitness ??
        s.results?.phase3?.aggregated_fitness,
      strategy: liveById.get(s.id) ?? s,
    }))
    const visible = new Set(nodes.map((n) => n.id))
    const edges = (run.lineage?.edges ?? [])
      .map((e) => ({
        source: e.parent ?? e.source,
        target: e.child ?? e.target,
      }))
      .filter((e) => visible.has(e.source) && visible.has(e.target))
    return { nodes, edges, roots: (run.lineage?.roots ?? []).filter((r) => visible.has(r)) }
  }, [currentGeneration, genIdx, generations, run.lineage?.edges, run.lineage?.roots])

  const api = useMemo(
    () => generateAPICosts(totalGenerations, generations.flat().length),
    [generations, totalGenerations],
  )

  return (
    <Layout
      currentGeneration={genIdx}
      totalGenerations={totalGenerations}
      currentPhase={currentPhase}
      isPlaying={isPlaying}
      playbackSpeed={playbackSpeed}
      onPlayPause={() => (isPlaying ? pause() : play())}
      onSpeedChange={(s) => setSpeed(s)}
      onNextGeneration={() => nextGeneration()}
      selectedStrategy={selectedStrategy}
    >
      <Layout.Arena>
        <EvolutionArena
          strategies={currentGeneration}
          generationNumber={genIdx}
          onStrategySelect={(s) => selectStrategy(s?.id ?? null)}
          selectedStrategyId={selectedStrategy?.id ?? null}
        />
      </Layout.Arena>

      <Layout.Validation>
        <ValidationViewer strategy={selectedStrategy} isAnimating={currentPhase === 'validation'} />
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
          currentGeneration={genIdx}
          onInsightGenerated={() => {}}
        />
      </Layout.YouFeed>

      <Layout.ApiCosts>
        <APICostDashboard
          costData={api}
          currentGeneration={genIdx}
          totalGenerations={totalGenerations}
          updateInterval={1000}
        />
      </Layout.ApiCosts>

      <Layout.Metrics>
        <MetricsDashboard
          generationStats={{ strategies: currentGeneration, generationNumber: genIdx }}
          selectedStrategy={selectedStrategy}
          allGenerations={generations.slice(0, Math.max(0, Math.min(generations.length, genIdx + 1)))}
        />
      </Layout.Metrics>
    </Layout>
  )
}
