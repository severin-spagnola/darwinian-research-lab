import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'

function RunTelemetry({ runId }) {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [events, setEvents] = useState([])
  const [eventsError, setEventsError] = useState(null)

  useEffect(() => {
    if (!runId) return
    setLoading(true)
    api
      .getRunLLMUsage(runId)
      .then((data) => {
        setUsage(data)
        setError(null)
      })
      .catch((err) => {
        setError(err.message)
        setUsage(null)
      })
      .finally(() => setLoading(false))
  }, [runId])

  useEffect(() => {
    if (!runId) return
    const source = new EventSource(`/api/run/${runId}/events`)
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        setEvents((prev) => {
          const next = [payload, ...prev]
          return next.slice(0, 20)
        })
      } catch (err) {
        setEventsError(err.message)
      }
    }
    source.onerror = () => {
      setEventsError('Event stream disconnected')
    }
    return () => {
      source.close()
    }
  }, [runId])

  const cacheRatio = useMemo(() => {
    if (!usage) return null
    const hits = usage.cache_hits ?? 0
    const misses = usage.cache_misses ?? 0
    return hits + misses > 0 ? hits / (hits + misses) : null
  }, [usage])

  const mutateCount = usage?.by_stage?.mutate?.count ?? 0
  const compileCount = usage?.by_stage?.compile?.count ?? 0

  return (
    <div className="space-y-4">
      <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">Run Telemetry</h3>
          {loading && <span className="text-xs text-gray-500">Loading…</span>}
        </div>
        {error && (
          <p className="text-xs text-red-600">
            Failed to load telemetry: {error}
          </p>
        )}
        {usage && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-gray-600">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">
                Calls
              </p>
              <p className="font-semibold text-lg text-gray-900">
                {usage.total_calls ?? 0}
              </p>
              <div className="text-[10px] text-gray-500">
                OpenAI: {usage.openai_calls ?? 0} · Anthropic:{' '}
                {usage.anthropic_calls ?? 0}
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">
                Tokens
              </p>
              <p className="font-semibold text-lg text-gray-900">
                {usage.total_tokens ?? 0}
              </p>
              <div className="text-[10px] text-gray-500">
                Cache hits: {usage.cache_hits ?? 0} / Misses:{' '}
                {usage.cache_misses ?? 0}
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">
                Cost
              </p>
              <p className="font-semibold text-lg text-gray-900">
                ${usage.estimated_cost_usd?.toFixed(2) ?? '0.00'}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">
                Stages
              </p>
              <div className="text-[12px] space-y-1">
                <p>Compile: {compileCount}</p>
                <p>Mutate: {mutateCount}</p>
                <p>Repairs: {usage.by_stage?.compile_repair?.count ?? 0}</p>
              </div>
            </div>
          </div>
        )}

        {usage && (
          <div className="text-[10px] text-gray-500 space-y-1">
            {usage.total_calls === 0 && (
              <p>No LLM calls recorded; likely cache-only or pre-LLM failure.</p>
            )}
            {cacheRatio !== null && cacheRatio > 0.7 && (
              <p>Mostly cached responses ({(cacheRatio * 100).toFixed(0)}% hits)</p>
            )}
            {mutateCount === 0 && (
              <p>No mutations executed (Adam likely killed or branching short-circuited).</p>
            )}
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Live Events</h3>
          <span className="text-[10px] text-gray-400">Streaming</span>
        </div>
        {eventsError && (
          <p className="text-xs text-red-500">Events disconnected.</p>
        )}
        <div className="max-h-52 overflow-y-auto text-xs text-gray-600 space-y-2">
          {events.length === 0 && (
            <p className="text-[11px] text-gray-500">No events yet.</p>
          )}
          {events.map((event, idx) => (
            <div key={`${event.timestamp}-${idx}`} className="border-b border-dashed border-gray-100 pb-1">
              <p className="font-semibold text-gray-700 mb-1">
                {event.type || 'event'}
              </p>
              <p className="text-[10px] text-gray-500">
                {new Date(event.timestamp || Date.now()).toLocaleTimeString()}
              </p>
              {event.message && (
                <p className="text-[11px] text-gray-500">{event.message}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default RunTelemetry
