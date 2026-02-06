import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import TranscriptViewer from './TranscriptViewer'

function StrategyInspector({ runId, graphId }) {
  const [evaluation, setEvaluation] = useState(null)
  const [fingerprint, setFingerprint] = useState(null)
  const [transcripts, setTranscripts] = useState([])
  const [loading, setLoading] = useState(false)
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [selectedTranscript, setSelectedTranscript] = useState(null)
  const [selectedTranscriptFile, setSelectedTranscriptFile] = useState(null)
  const [transcriptError, setTranscriptError] = useState(null)

  useEffect(() => {
    if (!graphId) {
      setEvaluation(null)
      setFingerprint(null)
      return
    }

    setLoading(true)
    Promise.allSettled([
      api.getEval(runId, graphId),
      api.getGraphFingerprint(runId, graphId),
    ])
      .then(([evalResult, fingerprintResult]) => {
        setEvaluation(evalResult.status === 'fulfilled' ? evalResult.value : null)
        setFingerprint(fingerprintResult.status === 'fulfilled' ? fingerprintResult.value : null)
      })
      .finally(() => setLoading(false))
  }, [runId, graphId])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    api.listRunTranscripts(runId)
      .then((list) => {
        if (!cancelled) setTranscripts(list || [])
      })
      .catch(() => {
        if (!cancelled) setTranscripts([])
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  useEffect(() => {
    if (!selectedTranscriptFile) {
      setSelectedTranscript(null)
      setTranscriptError(null)
      return
    }

    setTranscriptLoading(true)
    api
      .getTranscript(runId, selectedTranscriptFile)
      .then((data) => {
        setSelectedTranscript(data)
        setTranscriptError(null)
      })
      .catch((err) => {
        setTranscriptError(err.message)
        setSelectedTranscript(null)
      })
      .finally(() => setTranscriptLoading(false))
  }, [runId, selectedTranscriptFile])

  const relevantTranscripts = transcripts.filter((t) =>
    graphId
      ? t.filename.includes(graphId) ||
        t.stage?.startsWith('compile') ||
        t.stage?.startsWith('mutate')
      : t.stage?.startsWith('compile')
  )
  const relevantNames = new Set(relevantTranscripts.map((t) => t.filename))
  const otherTranscripts = transcripts.filter(
    (t) => !relevantNames.has(t.filename)
  )

  const handleTranscriptClick = (filename) => {
    setSelectedTranscriptFile(filename)
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Strategy Inspector</h3>
          {graphId && (
            <p className="text-xs text-gray-500 font-mono">{graphId}</p>
          )}
        </div>
        {graphId && (
          <Link
            to={`/runs/${runId}/strategy/${graphId}`}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Open strategy detail →
          </Link>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-gray-50 rounded-lg p-4 space-y-3 border border-dashed border-gray-200">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Evaluation Snapshot
          </p>
          {loading ? (
            <p className="text-xs text-gray-500">Loading evaluation…</p>
          ) : evaluation ? (
            <>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Decision</span>
                <span
                  className={`font-semibold ${
                    evaluation.decision === 'survive'
                      ? 'text-green-600'
                      : 'text-red-600'
                  }`}
                >
                  {evaluation.decision || 'unknown'}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Fitness</span>
                <span className="font-semibold">
                  {typeof evaluation.fitness === 'number'
                    ? evaluation.fitness.toFixed(3)
                    : '—'}
                </span>
              </div>
              {evaluation.kill_reason?.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-gray-500">Kill reasons</p>
                  <div className="flex flex-wrap gap-1">
                    {evaluation.kill_reason.map((reason) => (
                      <span
                        key={reason}
                        className="text-[10px] px-2 py-1 rounded bg-red-100 text-red-800"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-gray-500">No evaluation recorded yet.</p>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-4 border border-dashed border-gray-200 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Fingerprint
          </p>
          {fingerprint ? (
            <>
              <div className="flex justify-between text-xs text-gray-500">
                <span>Vector length</span>
                <span>{fingerprint.fingerprint_vector.length}</span>
              </div>
              <div className="text-[10px] text-gray-700">
                {fingerprint.dimension_labels
                  ?.slice(0, 6)
                  .map((label) => (
                    <span
                      key={label}
                      className="inline-flex items-center mr-1 mb-1 px-2 py-0.5 bg-gray-100 rounded"
                    >
                      {label}
                    </span>
                  ))}
                {fingerprint.dimension_labels?.length > 6 && (
                  <span className="text-gray-500 text-[09px]">
                    +{fingerprint.dimension_labels.length - 6} more
                  </span>
                )}
              </div>
              <div>
                <p className="text-[10px] uppercase text-gray-500">Hash</p>
                <p className="text-xs font-mono text-gray-600">
                  {fingerprint.fingerprint_hash}
                </p>
              </div>
            </>
          ) : (
            <p className="text-xs text-gray-500">Fingerprint unavailable.</p>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-4 border border-dashed border-gray-200">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Metrics
          </p>
          <div className="text-[11px] text-gray-600 space-y-1 mt-2">
            <div className="flex justify-between">
              <span>Edge count</span>
              <span>{fingerprint?.edge_count ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span>Param count</span>
              {<span>{fingerprint?.param_count ?? '—'}</span>}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            LLM Transcripts
          </p>
          <span className="text-[10px] text-gray-400">
            {relevantTranscripts.length} found
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {relevantTranscripts.length === 0 && (
              <p className="text-xs text-gray-500">No transcripts available yet.</p>
            )}
            {relevantTranscripts.map((transcript) => (
              <button
                key={transcript.filename}
                type="button"
                onClick={() => handleTranscriptClick(transcript.filename)}
                className={`text-left border rounded p-3 text-sm ${
                  selectedTranscriptFile === transcript.filename
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <div className="flex flex-col">
                  <span className="font-mono text-xs">{transcript.filename}</span>
                  <span className="text-[10px] text-gray-500">
                    {transcript.stage} · {transcript.provider}
                  </span>
                </div>
              </button>
            ))}
          </div>

        {transcriptLoading && (
          <p className="text-xs text-gray-500">Loading transcript…</p>
        )}

        {transcriptError && (
          <p className="text-xs text-red-500">{transcriptError}</p>
        )}

      {otherTranscripts.length > 0 && (
        <div className="pt-4">
          <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-2">
            All run transcripts
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {otherTranscripts.map((transcript) => (
              <button
                key={transcript.filename}
                type="button"
                onClick={() => handleTranscriptClick(transcript.filename)}
                className={`text-left border rounded p-2 text-xs ${
                  selectedTranscriptFile === transcript.filename
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <p className="font-mono">{transcript.filename}</p>
                <p className="text-[10px] text-gray-500">
                  {transcript.stage} · {transcript.provider}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedTranscript && (
        <div className="pt-3 border-t border-gray-200">
          <TranscriptViewer transcript={selectedTranscript} />
        </div>
      )}
      </div>
    </div>
  )
}

export default StrategyInspector
