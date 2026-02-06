import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

function RunsList() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadRuns()
  }, [])

  async function loadRuns() {
    try {
      setLoading(true)
      const data = await api.getRuns()
      setRuns(data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading runs...</div>
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800">Error loading runs: {error}</p>
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No runs found. Start a Darwin run to get started.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-gray-900">Evolution Runs</h2>
        <button
          onClick={loadRuns}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      <div className="space-y-4">
        {runs.map((run) => (
          <Link
            key={run.run_id}
            to={`/runs/${run.run_id}`}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div>
                <h3 className="font-mono text-lg font-medium text-gray-900">
                  {run.run_id}
                </h3>
                {run.summary && (
                  <div className="mt-2 text-sm text-gray-600 space-y-1">
                    <p>
                      Best Fitness: <span className="font-medium">{run.summary.best_fitness?.toFixed(3)}</span>
                    </p>
                    <p>
                      Total Evaluations: <span className="font-medium">{run.summary.total_evaluations}</span>
                    </p>
                  </div>
                )}
              </div>
              <div className="text-sm text-gray-500">
                {run.summary?.timestamp && new Date(run.summary.timestamp).toLocaleString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default RunsList
