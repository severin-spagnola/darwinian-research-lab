import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import GraphViewer from '../components/GraphViewer'
import TranscriptViewer from '../components/TranscriptViewer'

function StrategyDetail() {
  const { runId, graphId } = useParams()
  const [graph, setGraph] = useState(null)
  const [evaluation, setEvaluation] = useState(null)
  const [fingerprint, setFingerprint] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [transcripts, setTranscripts] = useState([])
  const [selectedTranscriptFile, setSelectedTranscriptFile] = useState(null)
  const [selectedTranscript, setSelectedTranscript] = useState(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [transcriptError, setTranscriptError] = useState(null)

  useEffect(() => {
    loadStrategyData()
  }, [runId, graphId])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    api
      .listRunTranscripts(runId)
      .then((list) => {
        if (!cancelled) {
          setTranscripts(list || [])
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTranscripts([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  useEffect(() => {
    setSelectedTranscriptFile(null)
    setSelectedTranscript(null)
  }, [graphId])

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

  async function loadStrategyData() {
    try {
      setLoading(true)
      const graphData = await api.getGraph(runId, graphId)
      const [evalResult, fingerprintResult] = await Promise.allSettled([
        api.getEval(runId, graphId),
        api.getGraphFingerprint(runId, graphId),
      ])

      setGraph(graphData)
      setEvaluation(
        evalResult.status === 'fulfilled' ? evalResult.value : null
      )
      setFingerprint(
        fingerprintResult.status === 'fulfilled' ? fingerprintResult.value : null
      )
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="text-center py-12">Loading strategy...</div>
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800">Error loading strategy: {error}</p>
      </div>
    )
  }

  if (!graph) {
    return <div className="text-center py-12">Strategy not found</div>
  }

  const evalReport = evaluation?.validation_report || {}
  const trainMetrics = evalReport.train_metrics || {}
  const holdoutMetrics = evalReport.holdout_metrics || {}

  const relevantTranscripts = transcripts.filter((t) =>
    t.filename.includes(graphId) ||
    t.stage?.startsWith('compile') ||
    t.stage?.startsWith('mutate')
  )

  const rawJson = JSON.stringify(graph, null, 2)

  const tabOptions = [
    { id: 'overview', label: 'Overview' },
    { id: 'graph', label: 'Graph' },
    { id: 'llm', label: 'LLM' },
    { id: 'raw', label: 'Raw JSON' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/runs/${runId}`} className="text-blue-600 hover:text-blue-800 text-sm">
          ← Back to run
        </Link>
        <h2 className="text-xl font-bold text-gray-900 mt-2">{graph.name}</h2>
        <p className="text-sm text-gray-600 font-mono">{graphId}</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex flex-wrap gap-2">
          {tabOptions.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1 text-xs font-semibold rounded ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-4">
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 border border-dashed border-gray-200 rounded-lg p-4 space-y-2">
                  <p className="text-xs uppercase tracking-wide text-gray-500">
                    Evaluation
                  </p>
                  <div className="flex justify-between text-sm">
                    <span>Decision</span>
                    <span
                      className={`font-semibold ${
                        evaluation?.decision === 'survive'
                          ? 'text-green-600'
                          : 'text-red-600'
                      }`}
                    >
                      {evaluation?.decision || '—'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Fitness</span>
                    <span className="font-semibold">
                      {typeof evaluation?.fitness === 'number'
                        ? evaluation.fitness.toFixed(3)
                        : '—'}
                    </span>
                  </div>
                  {evaluation?.kill_reason?.length > 0 && (
                    <div className="text-[11px] text-gray-500 space-y-1">
                      <p>Kill reasons</p>
                      <div className="flex flex-wrap gap-1">
                        {evaluation.kill_reason.map((reason) => (
                          <span
                            key={reason}
                            className="px-2 py-1 bg-red-100 rounded text-red-700"
                          >
                            {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="bg-gray-50 border border-dashed border-gray-200 rounded-lg p-4 space-y-2">
                  <p className="text-xs uppercase tracking-wide text-gray-500">
                    Performance
                  </p>
                  <div className="text-xs space-y-2">
                    <div>
                      <p className="text-gray-600 text-[11px]">Train</p>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Return</span>
                        <span className="font-semibold">
                          {typeof trainMetrics.return_pct === 'number'
                            ? `${(trainMetrics.return_pct * 100).toFixed(2)}%`
                            : '—'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Sharpe</span>
                        <span className="font-semibold">
                          {typeof trainMetrics.sharpe === 'number'
                            ? trainMetrics.sharpe.toFixed(2)
                            : '—'}
                        </span>
                      </div>
                    </div>

                    <div>
                      <p className="text-gray-600 text-[11px]">Holdout</p>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Return</span>
                        <span className="font-semibold">
                          {typeof holdoutMetrics.return_pct === 'number'
                            ? `${(holdoutMetrics.return_pct * 100).toFixed(2)}%`
                            : '—'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Sharpe</span>
                        <span className="font-semibold">
                          {typeof holdoutMetrics.sharpe === 'number'
                            ? holdoutMetrics.sharpe.toFixed(2)
                            : '—'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-700">
                      Nodes ({graph.nodes?.length || 0})
                    </h3>
                    <span className="text-[10px] text-gray-400 uppercase">
                      {fingerprint?.dimension_labels?.length || 0} dims
                    </span>
                  </div>
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {graph.nodes?.map((node) => (
                      <div key={node.id} className="border border-gray-100 rounded p-3">
                        <div className="flex justify-between text-xs">
                          <div>
                            <span className="font-mono text-[11px]">{node.id}</span>
                            <span className="ml-2 text-[11px] text-gray-500">
                              {node.type}
                            </span>
                          </div>
                        </div>
                        {node.params && (
                          <div className="text-[11px] text-gray-500 mt-1">
                            {Object.entries(node.params).map(([key, value]) => (
                              <div key={key}>
                                <span className="font-semibold">{key}:</span>{' '}
                                {JSON.stringify(value)}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                  <p className="text-xs uppercase tracking-wide text-gray-500">
                    Fingerprint
                  </p>
                  {fingerprint ? (
                    <>
                      <div className="text-[11px] text-gray-600">
                        <div className="flex justify-between">
                          <span>Edge count</span>
                          <span>{fingerprint.edge_count}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Param count</span>
                          <span>{fingerprint.param_count}</span>
                        </div>
                      </div>
                      <div className="text-[10px] text-gray-500">
                        Hash:
                        <div className="font-mono text-[10px] text-gray-600 break-all">
                          {fingerprint.fingerprint_hash}
                        </div>
                      </div>
                    </>
                  ) : (
                    <p className="text-[11px] text-gray-500">Unavailable</p>
                  )}
                </div>
              </div>

              {evaluation?.patch_applied && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">
                    Patch Applied
                  </h3>
                  <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
                    {JSON.stringify(evaluation.patch_applied, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {activeTab === 'graph' && (
            <div className="h-[640px] border border-gray-300 rounded">
              <GraphViewer graph={graph} />
            </div>
          )}

          {activeTab === 'llm' && (
            <div className="space-y-4">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <p className="text-xs uppercase tracking-wide text-gray-500">
                    Transcripts ({relevantTranscripts.length})
                  </p>
                  <span className="text-[10px] text-gray-400">
                    Total available: {transcripts.length}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {relevantTranscripts.length === 0 && (
                    <p className="text-xs text-gray-500">No transcripts yet.</p>
                  )}
                  {relevantTranscripts.map((transcript) => (
                    <button
                      key={transcript.filename}
                      type="button"
                      onClick={() => setSelectedTranscriptFile(transcript.filename)}
                      className={`text-left border rounded p-3 text-xs ${
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

              {transcriptLoading && (
                <p className="text-xs text-gray-500">Loading transcript…</p>
              )}
              {transcriptError && (
                <p className="text-xs text-red-500">{transcriptError}</p>
              )}

              {selectedTranscript && (
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <TranscriptViewer transcript={selectedTranscript} />
                </div>
              )}
            </div>
          )}

          {activeTab === 'raw' && (
            <div>
              <div className="flex justify-between items-center mb-3">
                <p className="text-sm font-semibold text-gray-700">Raw JSON</p>
                <button
                  type="button"
                  className="text-xs text-blue-600"
                  onClick={() => navigator.clipboard?.writeText(rawJson)}
                >
                  Copy
                </button>
              </div>
              <pre className="bg-gray-900 text-white text-xs rounded p-3 whitespace-pre-wrap max-h-[580px] overflow-y-auto">
                {rawJson}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyDetail
