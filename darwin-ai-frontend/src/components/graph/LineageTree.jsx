import { memo, useMemo } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  Handle,
  MarkerType,
  Position,
  useReactFlow,
} from '@xyflow/react'
import { Crown, Heart, Info, Skull, X } from 'lucide-react'

const NODE_X_GAP = 230
const NODE_Y_GAP = 160

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function parseGenerationFromId(id) {
  const m = String(id ?? '').match(/gen(?:eration)?[_-]?(\d+)/i)
  if (m) return Number(m[1])
  const m2 = String(id ?? '').match(/strat_gen(\d+)_/i)
  if (m2) return Number(m2[1])
  return null
}

function deriveFitness(strategyLike) {
  return safeNumber(
    strategyLike?.results?.phase3?.aggregated_fitness,
    safeNumber(strategyLike?.phase3?.aggregated_fitness, 0),
  )
}

function deriveState(strategyLike) {
  const s = strategyLike?.state
  if (s === 'elite' || s === 'alive' || s === 'dead' || s === 'testing') return s
  const verdict = strategyLike?.results?.red_verdict?.verdict
  if (verdict && verdict !== 'SURVIVE') return 'dead'
  return 'alive'
}

function normalizeLineage(lineageData) {
  if (!lineageData) return { nodes: [], edges: [] }

  const rawNodes = Array.isArray(lineageData.nodes) ? lineageData.nodes : null
  const rawEdges = Array.isArray(lineageData.edges) ? lineageData.edges : []

  const edges = rawEdges
    .map((e, idx) => {
      if (e?.source && e?.target) {
        return { id: e.id ?? `e_${idx}`, source: String(e.source), target: String(e.target) }
      }
      if (e?.parent && e?.child) {
        return { id: e.id ?? `e_${idx}`, source: String(e.parent), target: String(e.child) }
      }
      return null
    })
    .filter(Boolean)

  let nodes = []
  if (rawNodes) {
    nodes = rawNodes
      .map((n) => {
        if (!n) return null
        const id = String(n.id ?? n.strategy?.id ?? n.strategy_id ?? '')
        if (!id) return null
        const strategy = n.strategy ?? n
        const generation =
          n.generation ?? n.gen ?? n.strategy?.generation ?? parseGenerationFromId(id)
        const fitness = n.fitness ?? deriveFitness(strategy)
        const state = n.state ?? deriveState(strategy)
        const label =
          n.label ??
          n.shortId ??
          n.short_id ??
          strategy?.shortId ??
          strategy?.short_id ??
          strategy?.name ??
          id

        return { id, label, generation, state, fitness, strategy }
      })
      .filter(Boolean)
  } else {
    const ids = new Set()
    edges.forEach((e) => {
      ids.add(e.source)
      ids.add(e.target)
    })
    if (Array.isArray(lineageData.roots)) {
      lineageData.roots.forEach((r) => ids.add(String(r)))
    }
    nodes = [...ids].map((id) => {
      const generation = parseGenerationFromId(id)
      return { id, label: id, generation, state: 'alive', fitness: 0, strategy: null }
    })
  }

  return { nodes, edges }
}

function buildLayout({ nodes, edges, generationCount }) {
  const parentFor = new Map()
  edges.forEach((e) => {
    if (!parentFor.has(e.target)) parentFor.set(e.target, e.source)
  })

  // Prefer explicit generation; fallback to parsed generation; else 0.
  const maxGenFromNodes = nodes.reduce((acc, n) => Math.max(acc, safeNumber(n.generation, 0)), 0)
  const genCount = Math.max(
    1,
    safeNumber(generationCount, 0) || 0,
    maxGenFromNodes + 1,
  )

  const byGen = Array.from({ length: genCount }, () => [])
  nodes.forEach((n) => {
    const g = clamp(safeNumber(n.generation, 0), 0, genCount - 1)
    byGen[g].push(n)
  })

  // Order within each generation to keep siblings adjacent.
  const orderedByGen = []
  for (let g = 0; g < genCount; g += 1) {
    const list = byGen[g]
    if (g === 0) {
      orderedByGen[g] = [...list].sort((a, b) => b.fitness - a.fitness || a.id.localeCompare(b.id))
      continue
    }

    const prev = orderedByGen[g - 1] ?? []
    const parentIndex = new Map(prev.map((n, i) => [n.id, i]))

    const groups = new Map()
    list.forEach((n) => {
      const p = parentFor.get(n.id) ?? '__root__'
      if (!groups.has(p)) groups.set(p, [])
      groups.get(p).push(n)
    })

    const groupKeys = [...groups.keys()].sort((a, b) => {
      const ia = parentIndex.has(a) ? parentIndex.get(a) : 1e9
      const ib = parentIndex.has(b) ? parentIndex.get(b) : 1e9
      if (ia !== ib) return ia - ib
      return String(a).localeCompare(String(b))
    })

    orderedByGen[g] = groupKeys.flatMap((k) =>
      groups
        .get(k)
        .slice()
        .sort((a, b) => b.fitness - a.fitness || a.id.localeCompare(b.id)),
    )
  }

  const idToPos = new Map()
  for (let g = 0; g < genCount; g += 1) {
    const list = orderedByGen[g] ?? []
    const startX = -((list.length - 1) * NODE_X_GAP) / 2
    list.forEach((n, idx) => {
      idToPos.set(n.id, { x: startX + idx * NODE_X_GAP, y: g * NODE_Y_GAP })
    })
  }

  const flowNodes = nodes.map((n) => {
    const pos = idToPos.get(n.id) ?? { x: 0, y: 0 }
    return {
      id: n.id,
      type: 'lineageNode',
      position: pos,
      data: {
        id: n.id,
        label: n.label,
        generation: n.generation,
        state: n.state,
        fitness: n.fitness,
        strategy: n.strategy,
        parentId: parentFor.get(n.id) ?? null,
      },
      draggable: false,
      selectable: true,
      style: {
        transition: 'transform 260ms ease-out, opacity 200ms ease-out',
      },
    }
  })

  const markerNodes = Array.from({ length: genCount }, (_, g) => ({
    id: `gen_marker_${g}`,
    type: 'generationMarker',
    position: { x: -NODE_X_GAP * 1.6, y: g * NODE_Y_GAP },
    data: { label: `Generation ${g}` },
    draggable: false,
    selectable: false,
    focusable: false,
    style: {
      pointerEvents: 'none',
      transition: 'transform 260ms ease-out, opacity 200ms ease-out',
    },
  }))

  return { genCount, flowNodes: [...markerNodes, ...flowNodes] }
}

function buildEdges(flowNodes, edges) {
  const stateById = new Map(flowNodes.map((n) => [n.id, n?.data?.state ?? null]))

  return edges.map((e, idx) => {
    const parentState = stateById.get(e.source)
    const childState = stateById.get(e.target)
    const parentDead = parentState === 'dead'
    const childDead = childState === 'dead'

    let stroke = 'rgba(148,163,184,0.35)' // slate
    let animated = false

    if (parentDead) {
      stroke = 'rgba(148,163,184,0.26)'
    } else if (!childDead) {
      stroke = 'rgba(16,185,129,0.60)'
      animated = true
    } else {
      stroke = 'rgba(251,191,36,0.55)'
    }

    return {
      id: e.id ?? `edge_${idx}`,
      source: e.source,
      target: e.target,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: stroke },
      style: { stroke, strokeWidth: 2 },
      animated,
    }
  })
}

const LineageNode = memo(function LineageNode({ data, selected }) {
  const state = data?.state ?? 'alive'
  const isElite = state === 'elite'
  const isDead = state === 'dead'

  const border =
    isElite
      ? 'border-warning-400/55'
      : isDead
        ? 'border-danger-500/35'
        : 'border-primary-500/35'

  const chrome =
    isElite
      ? 'shadow-[0_0_0_1px_rgba(251,191,36,0.10),0_0_30px_rgba(16,185,129,0.12)]'
      : isDead
        ? 'shadow-[0_0_0_1px_rgba(239,68,68,0.10),0_0_24px_rgba(239,68,68,0.08)]'
        : 'shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_28px_rgba(16,185,129,0.10)]'

  const badge =
    isElite ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-warning-500/14 px-2.5 py-1 text-[11px] font-semibold text-warning-200 ring-1 ring-inset ring-warning-500/25">
        <Crown className="h-3.5 w-3.5" />
        Elite
      </span>
    ) : isDead ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-danger-500/14 px-2.5 py-1 text-[11px] font-semibold text-danger-200 ring-1 ring-inset ring-danger-500/25">
        <Skull className="h-3.5 w-3.5" />
        Dead
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary-500/14 px-2.5 py-1 text-[11px] font-semibold text-primary-200 ring-1 ring-inset ring-primary-500/25">
        <Heart className="h-3.5 w-3.5" />
        Alive
      </span>
    )

  const fitness = safeNumber(data?.fitness, 0)
  const label = String(data?.label ?? data?.id ?? '')

  const tooltip = (() => {
    const s = data?.strategy
    if (!s) return null
    const phase3 = s?.results?.phase3 ?? s?.phase3
    const penalties = phase3?.penalties
    const regimes = phase3?.regime_coverage

    return {
      median: safeNumber(phase3?.median_fitness, 0).toFixed(4),
      episodes: Array.isArray(phase3?.episodes) ? phase3.episodes.length : '—',
      regimes: regimes?.unique_regimes ?? '—',
      years: regimes?.years_covered ?? '—',
      penalty: penalties?.total_penalty ?? '—',
    }
  })()

  return (
    <div
      className={[
        'group relative rounded-2xl border bg-panel-elevated px-4 py-3',
        border,
        chrome,
        selected ? 'ring-2 ring-info-300/40' : 'ring-1 ring-inset ring-border/60',
        isDead ? 'opacity-70 grayscale' : 'opacity-100',
      ].join(' ')}
    >
      {/* Invisible handles to anchor edges cleanly */}
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <Handle type="source" position={Position.Right} className="opacity-0" />

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-text">{label}</div>
          <div className="mt-1 text-xs text-text-muted">
            Fitness{' '}
            <span className="font-mono font-semibold tabular-nums text-text">
              {fitness.toFixed(3)}
            </span>
          </div>
        </div>
        <div className="shrink-0">{badge}</div>
      </div>

      {isDead ? (
        <div className="pointer-events-none absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-xl bg-danger-500/14 ring-1 ring-inset ring-danger-500/25">
          <X className="h-4 w-4 text-danger-200" />
        </div>
      ) : null}

      {/* Tooltip */}
      {tooltip ? (
        <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-[240px] -translate-x-1/2 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
          <div className="rounded-2xl border border-border/60 bg-bg/95 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.45)] backdrop-blur-sm">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-text-muted">
              <Info className="h-3.5 w-3.5 text-info-200" />
              Phase 3
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-text-muted">
              <div>
                Median <span className="font-mono text-text">{tooltip.median}</span>
              </div>
              <div>
                Episodes <span className="font-mono text-text">{tooltip.episodes}</span>
              </div>
              <div>
                Regimes <span className="font-mono text-text">{tooltip.regimes}</span>
              </div>
              <div>
                Years <span className="font-mono text-text">{tooltip.years}</span>
              </div>
              <div className="col-span-2">
                Penalty <span className="font-mono text-text">{tooltip.penalty}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
})

const GenerationMarker = memo(function GenerationMarker({ data }) {
  return (
    <div className="pointer-events-none rounded-xl border border-border/60 bg-panel px-3 py-2 text-xs font-semibold text-text-muted shadow-[0_0_0_1px_rgba(34,211,238,0.05)]">
      {data?.label ?? 'Generation'}
    </div>
  )
})

function FitViewButton() {
  const rf = useReactFlow()
  return (
    <button
      type="button"
      onClick={() => rf.fitView({ padding: 0.2 })}
      className="rounded-xl bg-panel-elevated px-3 py-2 text-xs font-semibold text-text ring-1 ring-inset ring-border/70 transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-info-500/25"
    >
      Fit view
    </button>
  )
}

function LineageTreeInner({
  lineageData,
  selectedStrategyId,
  onStrategySelect,
  generationCount,
}) {
  const normalized = useMemo(() => normalizeLineage(lineageData), [lineageData])

  const layout = useMemo(() => {
    return buildLayout({
      nodes: normalized.nodes,
      edges: normalized.edges,
      generationCount,
    })
  }, [generationCount, normalized.edges, normalized.nodes])

  const nodes = useMemo(() => {
    return layout.flowNodes.map((n) => {
      if (n.type === 'generationMarker') return n
      return { ...n, selected: Boolean(selectedStrategyId && n.id === selectedStrategyId) }
    })
  }, [layout.flowNodes, selectedStrategyId])

  const edges = useMemo(() => buildEdges(nodes, normalized.edges), [nodes, normalized.edges])

  const nodeTypes = useMemo(
    () => ({
      lineageNode: LineageNode,
      generationMarker: GenerationMarker,
    }),
    [],
  )

  if (!lineageData) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/60 bg-panel-elevated p-10 text-center">
        <div className="text-sm font-semibold">Lineage Tree</div>
        <div className="mt-2 max-w-md text-sm text-text-muted">
          No lineage data available yet.
        </div>
      </div>
    )
  }

  return (
    <div className="h-[620px] w-full overflow-hidden rounded-2xl border border-border/60 bg-panel-elevated shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
      <ReactFlow
        className="dark"
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => {
          if (node?.type === 'generationMarker') return
          const payload = node?.data?.strategy ?? node?.data?.id ?? node?.id
          onStrategySelect?.(payload)
        }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={1.6}
      >
        <Background gap={22} size={1} color="rgba(148,163,184,0.10)" />
        <MiniMap
          pannable
          zoomable
          nodeColor={(n) => {
            const st = n?.data?.state
            if (st === 'elite') return 'rgba(251,191,36,0.9)'
            if (st === 'dead') return 'rgba(239,68,68,0.75)'
            if (n.type === 'generationMarker') return 'rgba(148,163,184,0.35)'
            return 'rgba(16,185,129,0.85)'
          }}
          maskColor="rgba(10,10,10,0.55)"
        />
        <Controls showInteractive={false} />

        <Panel position="top-right" className="m-3 flex items-center gap-2">
          <FitViewButton />
        </Panel>

        <Panel position="bottom-left" className="m-3">
          <div className="rounded-2xl border border-border/60 bg-bg/80 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.40)] backdrop-blur-sm">
            <div className="text-xs font-semibold text-text">Legend</div>
            <div className="mt-2 flex flex-col gap-2 text-xs text-text-muted">
              <div className="flex items-center gap-2">
                <Crown className="h-4 w-4 text-warning-200" />
                Elite (top 10%)
              </div>
              <div className="flex items-center gap-2">
                <Heart className="h-4 w-4 text-primary-200" />
                Alive
              </div>
              <div className="flex items-center gap-2">
                <X className="h-4 w-4 text-danger-200" />
                Dead
              </div>
              <div className="mt-1 text-[11px] text-text-subtle">
                Layers are arranged by generation (vertical).
              </div>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  )
}

export default function LineageTree(props) {
  return (
    <ReactFlowProvider>
      <LineageTreeInner {...props} />
    </ReactFlowProvider>
  )
}

