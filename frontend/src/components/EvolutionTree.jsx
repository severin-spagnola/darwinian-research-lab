import { useMemo, useCallback } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'

import 'reactflow/dist/style.css'

const DECISION_COLORS = {
  survive: '#16a34a',
  kill: '#dc2626',
  mutate_only: '#f59e0b',
  default: '#6b7280',
}

function getDecisionColor(decision) {
  if (!decision) return DECISION_COLORS.default
  return DECISION_COLORS[decision] || DECISION_COLORS.default
}

function EvolutionTree({ nodes = [], edges = [], bestId, selectedId, onSelect }) {
  const generationMap = useMemo(() => {
    return nodes.reduce((acc, node) => {
      acc[node.id] = node.generation || 0
      return acc
    }, {})
  }, [nodes])

  const grouped = useMemo(() => {
    const map = {}
    nodes.forEach((node) => {
      const generation = node.generation || 0
      map[generation] = map[generation] || []
      map[generation].push(node)
    })
    return map
  }, [nodes])

  const initialNodes = useMemo(() => {
    const nodeList = []
    Object.entries(grouped).forEach(([generation, group]) => {
      group.forEach((node, index) => {
        const isSelected = node.id === selectedId
        nodeList.push({
          id: node.id,
          data: {
            label: (
              <div className="text-xs">
                <div className="font-semibold">{node.id}</div>
                {typeof node.fitness === 'number' && (
                  <div className="text-gray-500">fit: {node.fitness.toFixed(3)}</div>
                )}
                <div className="text-gray-400">{node.decision || 'unknown'}</div>
              </div>
            ),
          },
          position: {
            x: Number(generation) * 240,
            y: index * 120,
          },
          style: {
            background: getDecisionColor(node.decision),
            border: isSelected
              ? '3px solid #2563eb'
              : node.id === bestId
              ? '3px solid #fbbf24'
              : '2px solid #fff',
            boxShadow: isSelected
              ? '0 0 14px rgba(37, 99, 235, 0.75)'
              : node.id === bestId
              ? '0 0 12px rgba(255, 196, 0, 0.9)'
              : undefined,
            color: 'white',
            borderRadius: 8,
            padding: 8,
            minWidth: 140,
          },
        })
      })
    })
    return nodeList
  }, [grouped, bestId, selectedId])

  const initialEdges = useMemo(() => {
    return edges.map((edge, idx) => ({
      id: `edge-${idx}-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      label: edge.generation != null ? `gen ${edge.generation}` : undefined,
      labelStyle: { fontSize: 10, fill: '#475569' },
      style: { stroke: '#94a3b8', strokeWidth: 2 },
    }))
  }, [edges])

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState(initialNodes)
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(initialEdges)

  const handleNodeClick = useCallback(
    (_, node) => {
      onSelect?.(node.id)
    },
    [onSelect]
  )

  const onInit = useCallback((instance) => {
    setTimeout(() => {
      instance.fitView({ padding: 0.2 })
    }, 50)
  }, [])

  if (nodes.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-sm text-gray-500">
        No lineage data available yet.
      </div>
    )
  }

  return (
    <div className="h-96 w-full rounded-lg border border-gray-200">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onInit={onInit}
        fitView
        attributionPosition="bottom-left"
      >
        <Background gap={16} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          nodeColor={(node) => node.style?.background || DECISION_COLORS.default}
        />
      </ReactFlow>
    </div>
  )
}

export default EvolutionTree
