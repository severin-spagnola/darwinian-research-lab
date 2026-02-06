import { useState } from 'react'

function TranscriptViewer({ transcript }) {
  const [showSystem, setShowSystem] = useState(false)
  const [showUser, setShowUser] = useState(false)

  if (!transcript) {
    return (
      <div className="text-sm text-gray-500 py-4">
        Select a transcript to view its details.
      </div>
    )
  }

  const { stage, provider, model, timestamp, system_prompt, user_prompt, raw_response_text, parsed_json, error } =
    transcript

  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-wide text-gray-500">
        <span className="font-semibold text-gray-700">{stage || 'unknown stage'}</span>
        <span>{provider}</span>
        <span>{model}</span>
        <span>{new Date(timestamp).toLocaleString()}</span>
      </div>

      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowSystem((prev) => !prev)}
          className="text-left w-full font-semibold text-gray-700 hover:text-blue-600"
        >
          {showSystem ? 'Hide' : 'Show'} System Prompt
        </button>
        {showSystem && (
          <pre className="bg-gray-900 text-white text-xs rounded p-3 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {system_prompt}
          </pre>
        )}
      </div>

      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowUser((prev) => !prev)}
          className="text-left w-full font-semibold text-gray-700 hover:text-blue-600"
        >
          {showUser ? 'Hide' : 'Show'} User Prompt
        </button>
        {showUser && (
          <pre className="bg-gray-900 text-white text-xs rounded p-3 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {user_prompt}
          </pre>
        )}
      </div>

      <div>
        <p className="text-xs font-semibold text-gray-600 mb-1">Raw Response</p>
        <pre className="bg-gray-50 text-xs text-gray-800 rounded p-3 whitespace-pre-wrap max-h-56 overflow-y-auto">
          {raw_response_text}
        </pre>
      </div>

      {parsed_json && (
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-1">Parsed JSON</p>
          <pre className="bg-gray-900 text-xs text-green-200 rounded p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
            {JSON.stringify(parsed_json, null, 2)}
          </pre>
        </div>
      )}

      {error && (
        <div className="text-xs text-red-600">
          <p className="font-semibold">Error</p>
          <p>{error}</p>
        </div>
      )}
    </div>
  )
}

export default TranscriptViewer
