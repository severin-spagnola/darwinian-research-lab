import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../lib/api'
import LiveProgress from '../components/LiveProgress'
import EvolutionTree from '../components/EvolutionTree'
import StrategyInspector from '../components/StrategyInspector'
import RunTelemetry from '../components/RunTelemetry'

function RunDetail() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [run, setRun] = useState(null)
  const [lineageGraph, setLineageGraph] = useState(null)
  const [lineageError, setLineageError] = useState(null)
  const [lineageLoading, setLineageLoading] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [selectedGraphId, setSelectedGraphId] = useState(null)

  useEffect(() => {
    loadRunData()
  }, [runId])

  useEffect(() => {
    setSelectedGraphId(null)
  }, [runId])

  useEffect(() => {
    if (!lineageGraph) return
    if (selectedGraphId) return
    const defaultId = lineageGraph.best_id || lineageGraph.nodes?.[0]?.id
    setSelectedGraphId(defaultId || null)
  }, [lineageGraph, selectedGraphId])

  async function loadRunData() {
    try {
      setLoading(true)
      const [runData, lineageData] = await Promise.all([
        api.getRun(runId),
        api.getLineageGraph(runId)
      ])
      setRun(runData)
      setLineageGraph(lineageData)
      setLineageError(null)
      setLineageLoading(false)

      // Check if run is in progress (no summary yet)
      setIsRunning(!runData.summary)

      setError(null)
    } catch (err) {
      // If 404, the run might be in progress but not saved yet
      if (err.response?.status === 404) {
        setIsRunning(true)
        setError(null)
      } else {
        setError(err.message)
      }
      setLineageError(err.message)
      setLineageLoading(false)
    } finally {
      setLoading(false)
    }
  }

  async function reloadLineageGraph() {
    setLineageLoading(true)
    try {
      const graph = await api.getLineageGraph(runId)
      setLineageGraph(graph)
      setLineageError(null)
    } catch (err) {
      setLineageGraph(null)
      setLineageError(err.message)
    } finally {
      setLineageLoading(false)
    }
  }

  function handleRunComplete() {
    // Reload run data when live run completes
    loadRunData()
  }

  if (loading) {
    return <div className="text-center py-12">Loading run details...</div>
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800">Error loading run: {error}</p>
      </div>
    )
  }

  if (!run) {
    return <div className="text-center py-12">Run not found</div>
  }

  const summary = run.summary || {}
  const config = run.config || {}

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-blue-600 hover:text-blue-800 text-sm">
          ← Back to runs
        </Link>
        <h2 className="text-2xl font-bold text-gray-900 mt-2 font-mono">{runId}</h2>
      </div>

      {/* Live Progress for running jobs */}
      {isRunning && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Live Progress</h3>
          <LiveProgress runId={runId} onComplete={handleRunComplete} />
        </div>
      )}

      {/* Run Summary */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Run Summary</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-600">Total Evaluations:</span>
            <span className="ml-2 font-medium">{summary.total_evaluations}</span>
          </div>
          <div>
            <span className="text-gray-600">Best Fitness:</span>
            <span className="ml-2 font-medium">{summary.best_fitness?.toFixed(3)}</span>
          </div>
          <div>
            <span className="text-gray-600">Depth:</span>
            <span className="ml-2 font-medium">{config.depth}</span>
          </div>
          <div>
            <span className="text-gray-600">Branching:</span>
            <span className="ml-2 font-medium">{config.branching}</span>
          </div>
        </div>
      </div>

      <RunTelemetry runId={runId} />

      {/* Top Strategies */}
      {summary.top_strategies && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Top Strategies</h3>
          <div className="space-y-2">
            {summary.top_strategies.map((strategy, idx) => (
              <Link
                key={strategy.graph_id}
                to={`/runs/${runId}/strategy/${strategy.graph_id}`}
                className="block border border-gray-200 rounded p-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-gray-500 text-sm mr-3">#{idx + 1}</span>
                    <span className="font-mono text-sm">{strategy.graph_id}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm">
                      Fitness: <span className="font-medium">{strategy.fitness.toFixed(3)}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {strategy.decision}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Kill Statistics */}
      {summary.kill_stats && Object.keys(summary.kill_stats).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Kill Statistics</h3>
          <div className="space-y-2">
            {Object.entries(summary.kill_stats)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 10)
              .map(([reason, count]) => (
                <div key={reason} className="flex justify-between text-sm">
                  <span className="text-gray-700">{reason}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Evolution Lineage</h3>
          <button
            className="text-blue-600 hover:underline text-sm"
            onClick={reloadLineageGraph}
          >
            Refresh
          </button>
        </div>
        {lineageLoading ? (
          <div className="text-center text-sm text-gray-500 py-12">
            Loading evolution tree…
          </div>
        ) : lineageError ? (
          <div className="text-sm text-red-600">Failed to load tree: {lineageError}</div>
        ) : (
          <EvolutionTree
            nodes={lineageGraph?.nodes || []}
            edges={lineageGraph?.edges || []}
            bestId={lineageGraph?.best_id}
            selectedId={selectedGraphId}
            onSelect={(graphId) => {
              setSelectedGraphId(graphId)
            }}
          />
        )}
      </div>
      {selectedGraphId && (
        <StrategyInspector runId={runId} graphId={selectedGraphId} />
      )}
    </div>
  )
}

export default RunDetail
