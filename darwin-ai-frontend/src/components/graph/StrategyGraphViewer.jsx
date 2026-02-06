import { memo, useMemo, useState } from 'react'
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
import {
  BarChart3,
  Database,
  Shield,
  ShoppingCart,
  SlidersHorizontal,
  TrafficCone,
  Workflow,
} from 'lucide-react'

const NODE_X_GAP = 260
const NODE_Y_GAP = 130

function classifyKind(type) {
  const t = String(type ?? '')
  if (t === 'MarketData') return 'market'
  if (t === 'OrderGenerator' || t === 'OrderGen' || t === 'Order') return 'order'
  if (t === 'Signal') return 'signal'
  if (t === 'Compare' || t === 'Logic' || t === 'And' || t === 'Or' || t === 'Not') return 'logic'
  if (t === 'RiskManager' || t === 'StopLoss' || t === 'TakeProfit' || t === 'Risk') return 'risk'

  // Indicators (heuristic)
  const indicatorLike = [
    'SMA',
    'RSI',
    'EMA',
    'MACD',
    'ATR',
    'BBANDS',
    'BollingerBands',
    'VWAP',
    'Stoch',
  ]
  if (indicatorLike.includes(t)) return 'indicator'
  return 'other'
}

function kindStyle(kind) {
  if (kind === 'market') {
    return {
      border: 'border-info-500/35',
      bg: 'bg-info-500/10',
      text: 'text-info-100',
      icon: Database,
    }
  }
  if (kind === 'indicator') {
    return {
      border: 'border-[#a78bfa]/35',
      bg: 'bg-[#a78bfa]/10',
      text: 'text-[#ddd6fe]',
      icon: BarChart3,
    }
  }
  if (kind === 'logic') {
    return {
      border: 'border-warning-400/35',
      bg: 'bg-warning-500/10',
      text: 'text-warning-100',
      icon: Workflow,
    }
  }
  if (kind === 'signal') {
    return {
      border: 'border-[#fb923c]/35',
      bg: 'bg-[#fb923c]/10',
      text: 'text-[#fed7aa]',
      icon: TrafficCone,
    }
  }
  if (kind === 'order') {
    return {
      border: 'border-primary-500/35',
      bg: 'bg-primary-500/10',
      text: 'text-primary-100',
      icon: ShoppingCart,
    }
  }
  if (kind === 'risk') {
    return {
      border: 'border-danger-500/35',
      bg: 'bg-danger-500/10',
      text: 'text-danger-100',
      icon: Shield,
    }
  }
  return {
    border: 'border-border/60',
    bg: 'bg-panel',
    text: 'text-text',
    icon: SlidersHorizontal,
  }
}

function formatNodeTitle(type, params, showParams) {
  const t = String(type ?? 'Node')
  if (!showParams) return t
  const p = params ?? {}

  if (t === 'SMA' && Number.isFinite(Number(p.period))) return `SMA(${Number(p.period)})`
  if (t === 'RSI' && Number.isFinite(Number(p.period))) return `RSI(${Number(p.period)})`
  if (t === 'EMA' && Number.isFinite(Number(p.period))) return `EMA(${Number(p.period)})`
  if (t === 'Compare' && p.op) return `Compare(${String(p.op)})`
  if (t === 'Signal' && p.direction) return `Signal(${String(p.direction)})`
  if (t === 'OrderGenerator' && p.sizing) return `OrderGen(${String(p.sizing)})`

  const entries = Object.entries(p)
  if (entries.length === 0) return t
  const short = entries
    .slice(0, 2)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(', ')
  return `${t}(${short}${entries.length > 2 ? ', …' : ''})`
}

function parseInputRef(v) {
  if (typeof v !== 'string') return null
  const parts = v.split('.')
  if (parts.length < 2) return null
  const source = parts[0]
  const output = parts.slice(1).join('.')
  if (!source || !output) return null
  return { source, output }
}

function buildDag(strategyGraph, showParams) {
  const rawNodes = Array.isArray(strategyGraph?.nodes) ? strategyGraph.nodes : []

  const ids = rawNodes.map((n) => String(n?.id ?? '')).filter(Boolean)
  const nodeById = new Map(rawNodes.map((n) => [String(n?.id ?? ''), n]))

  const edges = []
  const seen = new Set()

  rawNodes.forEach((n) => {
    const target = String(n?.id ?? '')
    if (!target) return
    const inputs = n?.inputs ?? {}

    Object.entries(inputs).forEach(([inputKey, value]) => {
      const pushRef = (ref) => {
        if (!ref) return
        const source = String(ref.source)
        if (!source || !nodeById.has(source)) return
        const label = String(ref.output)
        const key = `${source}::${label}::${target}::${inputKey}`
        if (seen.has(key)) return
        seen.add(key)
        edges.push({
          id: `e_${key}`,
          source,
          target,
          type: 'smoothstep',
          label,
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
          style: { stroke: 'rgba(148,163,184,0.45)', strokeWidth: 2 },
          labelStyle: { fill: 'rgba(245,245,245,0.75)', fontSize: 11, fontFamily: 'ui-monospace' },
          labelBgStyle: {
            fill: 'rgba(26,26,26,0.85)',
            stroke: 'rgba(38,38,38,0.9)',
            strokeWidth: 1,
          },
          labelBgPadding: [8, 4],
          labelBgBorderRadius: 10,
        })
      }

      if (Array.isArray(value)) {
        value.forEach((vv) => pushRef(parseInputRef(vv)))
        return
      }
      pushRef(parseInputRef(value))
    })
  })

  // Simple topological layering (relaxation). Works for DAG; best-effort if cycles exist.
  const level = new Map(ids.map((id) => [id, 0]))
  for (let iter = 0; iter < ids.length; iter += 1) {
    let changed = false
    edges.forEach((e) => {
      const s = level.get(e.source) ?? 0
      const t = level.get(e.target) ?? 0
      const next = s + 1
      if (next > t) {
        level.set(e.target, next)
        changed = true
      }
    })
    if (!changed) break
  }

  const levels = new Map()
  ids.forEach((id) => {
    const l = level.get(id) ?? 0
    if (!levels.has(l)) levels.set(l, [])
    levels.get(l).push(id)
  })

  const sortedLevels = [...levels.keys()].sort((a, b) => a - b)
  const posById = new Map()
  sortedLevels.forEach((l) => {
    const list = levels.get(l).slice().sort()
    const startY = -((list.length - 1) * NODE_Y_GAP) / 2
    list.forEach((id, idx) => {
      posById.set(id, { x: l * NODE_X_GAP, y: startY + idx * NODE_Y_GAP })
    })
  })

  const nodes = ids.map((id) => {
    const n = nodeById.get(id) ?? {}
    const kind = classifyKind(n.type)
    const pos = posById.get(id) ?? { x: 0, y: 0 }
    const outputs = Array.isArray(n.outputs) ? n.outputs : []
    return {
      id,
      type: 'dagNode',
      position: pos,
      draggable: false,
      data: {
        id,
        type: n.type ?? 'Node',
        kind,
        title: formatNodeTitle(n.type, n.params, showParams),
        params: n.params ?? {},
        outputs,
        showParams,
      },
      style: {
        transition: 'transform 260ms ease-out, opacity 200ms ease-out',
      },
    }
  })

  return { nodes, edges }
}

const DagNode = memo(function DagNode({ data, selected }) {
  const { border, bg, text, icon: Icon } = kindStyle(data?.kind)
  const outputs = Array.isArray(data?.outputs) ? data.outputs : []

  return (
    <div
      className={[
        'group rounded-2xl border bg-panel-elevated px-4 py-3',
        border,
        selected ? 'ring-2 ring-info-300/35' : 'ring-1 ring-inset ring-border/60',
        'shadow-[0_0_0_1px_rgba(34,211,238,0.05)]',
      ].join(' ')}
    >
      <Handle type="target" position={Position.Left} className="opacity-0" />
      <Handle type="source" position={Position.Right} className="opacity-0" />

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`grid h-7 w-7 place-items-center rounded-xl ${bg} ring-1 ring-inset ring-border/60`}>
              <Icon className={`h-4 w-4 ${text}`} />
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-text">
                {data?.title ?? data?.type ?? 'Node'}
              </div>
              <div className="mt-0.5 truncate font-mono text-[11px] text-text-subtle">
                {String(data?.id ?? '')}
              </div>
            </div>
          </div>

          {data?.showParams ? (
            <div className="mt-2 text-[11px] text-text-muted">
              Type:{' '}
              <span className="font-mono text-text">
                {String(data?.type ?? '—')}
              </span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {outputs.length ? (
          outputs.map((o) => (
            <span
              key={o}
              className="rounded-full bg-panel px-2.5 py-1 font-mono text-[11px] text-text-muted ring-1 ring-inset ring-border/70"
              title="Output"
            >
              {o}
            </span>
          ))
        ) : (
          <span className="rounded-full bg-panel px-2.5 py-1 text-[11px] text-text-subtle ring-1 ring-inset ring-border/70">
            no outputs
          </span>
        )}
      </div>
    </div>
  )
})

function FitViewButton() {
  const rf = useReactFlow()
  return (
    <button
      type="button"
      onClick={() => rf.fitView({ padding: 0.25 })}
      className="rounded-xl bg-panel-elevated px-3 py-2 text-xs font-semibold text-text ring-1 ring-inset ring-border/70 transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-info-500/25"
    >
      Fit view
    </button>
  )
}

function StrategyGraphViewerInner({ strategyGraph }) {
  const [showParams, setShowParams] = useState(true)

  const dag = useMemo(() => buildDag(strategyGraph, showParams), [showParams, strategyGraph])

  const nodeTypes = useMemo(() => ({ dagNode: DagNode }), [])

  if (!strategyGraph) {
    return (
      <div className="grid place-items-center rounded-2xl border border-border/60 bg-panel-elevated p-10 text-center">
        <div className="text-sm font-semibold">Strategy Graph</div>
        <div className="mt-2 max-w-md text-sm text-text-muted">
          Select a strategy to view its internal DAG.
        </div>
      </div>
    )
  }

  const title = strategyGraph?.name ?? strategyGraph?.id ?? 'Strategy Graph'
  const nodeCount = Array.isArray(strategyGraph?.nodes) ? strategyGraph.nodes.length : 0

  return (
    <div className="h-[620px] w-full overflow-hidden rounded-2xl border border-border/60 bg-panel-elevated shadow-[0_0_0_1px_rgba(34,211,238,0.06),0_0_30px_rgba(16,185,129,0.08)]">
      <ReactFlow
        className="dark"
        nodes={dag.nodes}
        edges={dag.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={1.8}
        defaultEdgeOptions={{
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: 'rgba(148,163,184,0.45)' },
          style: { stroke: 'rgba(148,163,184,0.45)', strokeWidth: 2 },
        }}
      >
        <Background gap={22} size={1} color="rgba(148,163,184,0.10)" />
        <MiniMap
          pannable
          zoomable
          nodeColor={(n) => {
            const k = n?.data?.kind
            if (k === 'market') return 'rgba(34,211,238,0.85)'
            if (k === 'indicator') return 'rgba(167,139,250,0.85)'
            if (k === 'logic') return 'rgba(251,191,36,0.85)'
            if (k === 'signal') return 'rgba(251,146,60,0.85)'
            if (k === 'order') return 'rgba(16,185,129,0.85)'
            if (k === 'risk') return 'rgba(239,68,68,0.85)'
            return 'rgba(148,163,184,0.65)'
          }}
          maskColor="rgba(10,10,10,0.55)"
        />
        <Controls showInteractive={false} />

        <Panel position="top-left" className="m-3">
          <div className="rounded-2xl border border-border/60 bg-bg/80 px-4 py-3 shadow-[0_10px_30px_rgba(0,0,0,0.40)] backdrop-blur-sm">
            <div className="text-xs font-semibold text-text">DAG Viewer</div>
            <div className="mt-1 truncate text-sm font-semibold text-text">{title}</div>
            <div className="mt-2 text-xs text-text-muted">
              Nodes: <span className="font-mono text-text">{nodeCount}</span>
            </div>
          </div>
        </Panel>

        <Panel position="top-right" className="m-3 flex items-center gap-2">
          <FitViewButton />
          <button
            type="button"
            onClick={() => setShowParams((v) => !v)}
            className="rounded-xl bg-panel-elevated px-3 py-2 text-xs font-semibold text-text ring-1 ring-inset ring-border/70 transition hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-primary-500/25"
          >
            {showParams ? 'Hide params' : 'Show params'}
          </button>
        </Panel>
      </ReactFlow>
    </div>
  )
}

export default function StrategyGraphViewer(props) {
  return (
    <ReactFlowProvider>
      <StrategyGraphViewerInner {...props} />
    </ReactFlowProvider>
  )
}
