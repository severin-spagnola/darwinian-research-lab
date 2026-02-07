/**
 * Backend API Client for Darwin AI
 *
 * Provides typed interfaces to all backend endpoints.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8050'

/**
 * Base fetch wrapper with error handling
 */
async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    // Mute noisy endpoints that get polled frequently
    const mutePatterns = ['/llm/usage']
    const isMuted = mutePatterns.some((p) => endpoint.includes(p))
    if (!isMuted) {
      console.error(`API Error (${endpoint}):`, error)
    }
    throw error
  }
}

// ============================================================================
// Run Management
// ============================================================================

/**
 * List all evolution runs
 * GET /api/runs
 */
export async function listRuns() {
  return apiFetch('/api/runs')
}

/**
 * Get run summary
 * GET /api/runs/{runId}
 */
export async function getRunSummary(runId) {
  return apiFetch(`/api/runs/${runId}`)
}

/**
 * Get run data in playback-compatible format (generations array)
 * GET /api/runs/{runId}/playback
 */
export async function getRunPlayback(runId) {
  return apiFetch(`/api/runs/${runId}/playback`)
}

/**
 * Start a new evolution run
 * POST /api/run
 */
export async function startRun(config) {
  return apiFetch('/api/run', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

/**
 * Get run lineage (parent-child relationships)
 * GET /api/runs/{runId}/lineage
 */
export async function getRunLineage(runId) {
  return apiFetch(`/api/runs/${runId}/lineage`)
}

// ============================================================================
// Strategy Graphs
// ============================================================================

/**
 * Get strategy graph by ID
 * GET /api/runs/{runId}/graphs/{graphId}
 */
export async function getStrategyGraph(runId, graphId) {
  return apiFetch(`/api/runs/${runId}/graphs/${graphId}`)
}

/**
 * List all graphs in a run
 * GET /api/runs/{runId}/graphs
 */
export async function listGraphs(runId) {
  return apiFetch(`/api/runs/${runId}/graphs`)
}

// ============================================================================
// Evaluation Results
// ============================================================================

/**
 * Get evaluation results for a strategy
 * GET /api/runs/{runId}/evals/{graphId}
 */
export async function getEvaluation(runId, graphId) {
  return apiFetch(`/api/runs/${runId}/evals/${graphId}`)
}

/**
 * Get Phase 3 report for a strategy
 * GET /api/runs/{runId}/phase3/{graphId}
 */
export async function getPhase3Report(runId, graphId) {
  return apiFetch(`/api/runs/${runId}/phase3/${graphId}`)
}

// ============================================================================
// LLM Usage & Costs
// ============================================================================

/**
 * Get global LLM usage statistics
 * GET /api/llm/usage
 */
export async function getGlobalLLMUsage() {
  return apiFetch('/api/llm/usage')
}

/**
 * Get LLM usage for a specific run
 * GET /api/runs/{runId}/llm/usage
 */
export async function getRunLLMUsage(runId) {
  return apiFetch(`/api/runs/${runId}/llm/usage`)
}

// ============================================================================
// Research Layer
// ============================================================================

/**
 * Search You.com via backend proxy (keeps API key secret)
 * POST /api/research/search
 *
 * Compatible with old youcomAPI.js signature: searchYouCom(query, { signal, count })
 */
export async function searchYouCom(query, options = {}) {
  const nResults = options.count || options.n_results || 5
  const signal = options.signal

  const response = await fetch(`${API_BASE_URL}/api/research/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      n_results: nResults,
    }),
    signal, // Pass abort signal for cancellation
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const data = await response.json()

  // Return format compatible with old API: { results, timestamp, raw }
  return {
    results: data.results || [],
    timestamp: new Date().toISOString(),
    raw: data,
  }
}

/**
 * Create a research pack (backend calls You.com)
 * POST /api/research/packs
 */
export async function createResearchPack(query, nResults = 5) {
  return apiFetch('/api/research/packs', {
    method: 'POST',
    body: JSON.stringify({
      query,
      n_results: nResults,
    }),
  })
}

/**
 * Get cached research pack by ID
 * GET /api/research/packs/{packId}
 */
export async function getResearchPack(packId) {
  return apiFetch(`/api/research/packs/${packId}`)
}

/**
 * Get Blue Memo (strategy self-advocacy)
 * GET /api/runs/{runId}/memos/{graphId}
 */
export async function getBlueMemo(runId, graphId) {
  return apiFetch(`/api/runs/${runId}/memos/${graphId}`)
}

/**
 * Get Red Verdict (overseer judgment)
 * GET /api/runs/{runId}/verdicts/{graphId}
 */
export async function getRedVerdict(runId, graphId) {
  return apiFetch(`/api/runs/${runId}/verdicts/${graphId}`)
}

// ============================================================================
// Real-Time Events (SSE)
// ============================================================================

/**
 * Connect to Server-Sent Events stream for a running evolution
 * GET /api/run/{runId}/events
 *
 * @returns EventSource instance
 */
export function connectToRunEvents(runId, callbacks = {}) {
  const url = `${API_BASE_URL}/api/run/${runId}/events`
  const eventSource = new EventSource(url)

  eventSource.addEventListener('run_started', (e) => {
    const data = JSON.parse(e.data)
    callbacks.onRunStarted?.(data)
  })

  eventSource.addEventListener('log', (e) => {
    const data = JSON.parse(e.data)
    callbacks.onLog?.(data)
  })

  eventSource.addEventListener('run_finished', (e) => {
    const data = JSON.parse(e.data)
    callbacks.onRunFinished?.(data)
    eventSource.close()
  })

  eventSource.addEventListener('error', (e) => {
    console.error('SSE Error:', e)
    callbacks.onError?.(e)
    eventSource.close()
  })

  return eventSource
}

// ============================================================================
// Health & Debug
// ============================================================================

/**
 * Health check
 * GET /api/health
 */
export async function checkHealth() {
  return apiFetch('/api/health')
}

/**
 * Get recent API requests (debug)
 * GET /api/debug/requests
 */
export async function getDebugRequests() {
  return apiFetch('/api/debug/requests')
}

/**
 * Get recent errors (debug)
 * GET /api/debug/errors
 */
export async function getDebugErrors() {
  return apiFetch('/api/debug/errors')
}
