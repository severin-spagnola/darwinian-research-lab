import { useEffect, useMemo, useState } from 'react'

import Layout from './components/Layout.jsx'
import EvolutionArena from './components/arena/EvolutionArena.jsx'
import ValidationViewer from './components/validation/ValidationViewer.jsx'
import LineageTree from './components/graph/LineageTree.jsx'
import StrategyGraphViewer from './components/graph/StrategyGraphViewer.jsx'
import {
  generateAPICosts,
  generateEvolutionRun,
  generateYouComResponse,
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

  const you = useMemo(
    () => generateYouComResponse('current macro regime and volatility'),
    [],
  )
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
        <div className="space-y-3">
          <div className="text-xs text-text-muted">
            Query: <span className="font-mono text-text">{you.query}</span>
          </div>
          <div className="space-y-2">
            {you.results.map((r) => (
              <div
                key={r}
                className="rounded-xl border border-border/60 bg-panel-elevated px-4 py-3 text-sm text-text-muted"
              >
                {r}
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4 text-sm">
            <div className="text-xs font-semibold text-text">Insights</div>
            <ul className="mt-2 list-disc pl-5 text-sm text-text-muted">
              {you.insights.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4 text-sm">
            <div className="text-xs font-semibold text-text">
              Mutation Suggestions
            </div>
            <ul className="mt-2 list-disc pl-5 text-sm text-text-muted">
              {you.mutation_suggestions.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      </Layout.YouFeed>

      <Layout.ApiCosts>
        <div className="grid gap-3">
          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4">
            <div className="text-xs text-text-muted">Total cost</div>
            <div className="mt-1 font-mono text-xl font-semibold text-text">
              ${api.total_cost.toFixed(2)}
            </div>
          </div>
          {Object.entries(api.breakdown).map(([k, v]) => (
            <div
              key={k}
              className="flex items-center justify-between rounded-xl border border-border/60 bg-panel-elevated px-4 py-3 text-sm"
            >
              <div className="text-text-muted">{k}</div>
              <div className="font-mono text-text">
                {v.calls} calls · ${v.cost.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </Layout.ApiCosts>

      <Layout.Metrics>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4">
            <div className="text-xs text-text-muted">Champion</div>
            <div className="mt-1 truncate text-sm font-semibold text-text">
              {run.champion?.id ?? '—'}
            </div>
            <div className="mt-2 text-xs text-text-muted">
              Fitness{' '}
              <span className="font-mono text-text">
                {(run.champion?.results?.phase3?.aggregated_fitness ?? 0).toFixed(3)}
              </span>
            </div>
          </div>
          <div className="rounded-xl border border-border/60 bg-panel-elevated p-4">
            <div className="text-xs text-text-muted">Survival rate</div>
            <div className="mt-1 font-mono text-xl font-semibold text-text">
              {(run.stats?.survival_rate ?? 0).toFixed(2)}
            </div>
            <div className="mt-2 text-xs text-text-muted">
              Total strategies{' '}
              <span className="font-mono text-text">
                {run.stats?.total_strategies ?? '—'}
              </span>
            </div>
          </div>
        </div>
      </Layout.Metrics>
    </Layout>
  )
}

