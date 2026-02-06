import { useState, useEffect, useRef } from 'react'

function LiveProgress({ runId, onComplete }) {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState('connecting')
  const [progress, setProgress] = useState({})
  const [isPaused, setIsPaused] = useState(false)
  const eventSourceRef = useRef(null)
  const logEndRef = useRef(null)

  useEffect(() => {
    // Connect to SSE
    const eventSource = new EventSource(`/api/run/${runId}/events`)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setStatus('connected')
    }

    eventSource.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)

        // Handle different event types
        if (event.type === 'status') {
          setStatus(event.status)
          if (event.progress) {
            setProgress(event.progress)
          }
        } else if (event.type === 'run_finished') {
          setStatus('completed')
          setEvents(prev => [...prev, {
            type: 'success',
            message: `Evolution complete! Best fitness: ${event.best_fitness?.toFixed(3)}`,
            timestamp: event.timestamp
          }])
          if (onComplete) onComplete()
        } else if (event.type === 'error') {
          setStatus('failed')
          setEvents(prev => [...prev, {
            type: 'error',
            message: event.message || 'Unknown error',
            timestamp: event.timestamp
          }])
        } else {
          // Generic log event
          setEvents(prev => [...prev, event])
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', err)
      }
    }

    eventSource.onerror = () => {
      setStatus('disconnected')
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [runId, onComplete])

  // Auto-scroll to bottom unless paused
  useEffect(() => {
    if (!isPaused && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, isPaused])

  const progressPct = progress.max_total_evals > 0
    ? (progress.evals_completed / progress.max_total_evals) * 100
    : 0

  return (
    <div className="space-y-4">
      {/* Progress Bar */}
      {status === 'running' && progress.max_total_evals && (
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-600">
              Progress: {progress.evals_completed || 0} / {progress.max_total_evals} evaluations
            </span>
            <span className="text-gray-600">
              Generation: {progress.current_generation || 0}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* Status Badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className={`inline-block px-3 py-1 text-sm rounded-full ${
            status === 'connected' || status === 'running' ? 'bg-blue-100 text-blue-800' :
            status === 'completed' ? 'bg-green-100 text-green-800' :
            status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {status === 'running' ? '🧬 Evolving...' :
             status === 'completed' ? '✓ Complete' :
             status === 'failed' ? '✗ Failed' :
             status === 'connecting' ? '⟳ Connecting...' :
             status}
          </span>
          {progress.best_fitness !== null && progress.best_fitness !== undefined && (
            <span className="text-sm text-gray-600">
              Best: <span className="font-medium">{progress.best_fitness.toFixed(3)}</span>
            </span>
          )}
        </div>
        <button
          onClick={() => setIsPaused(!isPaused)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {isPaused ? 'Resume scroll' : 'Pause scroll'}
        </button>
      </div>

      {/* Event Log */}
      <div className="bg-gray-900 text-gray-100 rounded p-4 h-96 overflow-y-auto font-mono text-xs">
        {events.length === 0 && (
          <div className="text-gray-500">Waiting for events...</div>
        )}
        {events.map((event, idx) => (
          <div key={idx} className="mb-1">
            <span className="text-gray-500">{new Date(event.timestamp).toLocaleTimeString()}</span>
            {' '}
            <span className={
              event.type === 'error' ? 'text-red-400' :
              event.type === 'success' ? 'text-green-400' :
              event.type === 'log' ? 'text-gray-300' :
              'text-blue-400'
            }>
              {event.message || JSON.stringify(event)}
            </span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>

      {/* Kill Stats */}
      {progress.kill_stats && Object.keys(progress.kill_stats).length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Kill Statistics</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(progress.kill_stats)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 6)
              .map(([reason, count]) => (
                <div key={reason} className="flex justify-between bg-gray-50 px-2 py-1 rounded">
                  <span className="text-gray-600">{reason}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default LiveProgress
