import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'

// Node type colors
const NODE_COLORS = {
  data_source: '#3b82f6', // blue
  indicator: '#8b5cf6', // purple
  transform: '#06b6d4', // cyan
  signal: '#f59e0b', // amber
  risk_mgmt: '#ef4444', // red
  position_sizing: '#10b981', // green
  strategy: '#ec4899', // pink
  default: '#6b7280', // gray
}

function getNodeColor(nodeType) {
  for (const [category, color] of Object.entries(NODE_COLORS)) {
    if (nodeType.toLowerCase().includes(category)) {
      return color
    }
  }
  return NODE_COLORS.default
}

function GraphViewer({ graph }) {
  // Convert graph nodes to react-flow nodes
  const initialNodes = useMemo(() => {
    if (!graph?.nodes) return []

    return graph.nodes.map((node, idx) => {
      const nodeId = node.node_id || node.id || `node_${idx}`
      const nodeType = node.node_type || node.type || ''
      return {
        id: nodeId,
        type: 'default',
        data: {
          label: (
            <div className="text-xs">
              <div className="font-semibold">{nodeId}</div>
              <div className="text-gray-600">{nodeType}</div>
              {node.params && Object.keys(node.params).length > 0 && (
                <div className="text-gray-500 text-[10px] mt-1">
                  {Object.entries(node.params)
                    .slice(0, 2)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(', ')}
                </div>
              )}
            </div>
          ),
        },
        position: {
          x: (idx % 4) * 250,
          y: Math.floor(idx / 4) * 120,
        },
        style: {
          background: getNodeColor(nodeType),
          color: 'white',
          border: '2px solid #fff',
          borderRadius: '8px',
          padding: '10px',
          minWidth: '150px',
        },
      }
    })
  }, [graph])

  // Convert graph edges from node.inputs
  const initialEdges = useMemo(() => {
    if (!graph?.nodes) return []

    const edges = []
    graph.nodes.forEach((node) => {
      if (!node.inputs) return
      const targetId = node.node_id || node.id
      Object.entries(node.inputs).forEach(([inputName, sourceValue]) => {
        const sourceId = Array.isArray(sourceValue)
          ? sourceValue[0]
          : sourceValue
        if (!sourceId || !targetId) return
        edges.push({
          id: `${sourceId}-${targetId}-${inputName}`,
          source: sourceId,
          target: targetId,
          label: inputName,
          type: 'smoothstep',
          animated: false,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
          labelStyle: { fontSize: 10, fill: '#64748b' },
        })
      })
    })
    return edges
  }, [graph])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  const onInit = useCallback((reactFlowInstance) => {
    // Auto-layout on init
    setTimeout(() => {
      reactFlowInstance.fitView({ padding: 0.2 })
    }, 50)
  }, [])

  if (!graph?.nodes || graph.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        No nodes in graph
      </div>
    )
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onInit={onInit}
      fitView
      attributionPosition="bottom-left"
    >
      <Background />
      <Controls />
      <MiniMap
        nodeColor={(node) => node.style?.background || NODE_COLORS.default}
        nodeStrokeWidth={3}
        zoomable
        pannable
      />
    </ReactFlow>
  )
}

export default GraphViewer
