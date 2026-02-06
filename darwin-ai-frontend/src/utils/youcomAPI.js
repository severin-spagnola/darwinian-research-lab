// You.com API wrapper (frontend-friendly)
// --------------------------------------
// NOTE: Putting API keys in the browser is not secure for production.
// Prefer calling You.com from your backend and proxying results to the UI.

const DEFAULT_ENDPOINT = 'https://ydc-index.io/v1/search'
const MIN_CALL_INTERVAL_MS = 900

let _lastCallAt = 0

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function cleanText(s) {
  return String(s ?? '')
    .replace(/\s+/g, ' ')
    .replace(/\u00a0/g, ' ')
    .trim()
}

function pickBestSnippet(item) {
  const candidates = []
  if (item?.description) candidates.push(item.description)
  if (item?.snippet) candidates.push(item.snippet)
  if (Array.isArray(item?.snippets)) candidates.push(...item.snippets)
  if (item?.title) candidates.push(item.title)
  return cleanText(candidates.find((c) => cleanText(c).length >= 10) ?? candidates[0] ?? '')
}

function parseBulletsFromResponse(data, maxBullets = 6) {
  // Try common shapes from the You.com API, but degrade gracefully.
  const buckets = []

  const results = data?.results ?? data?.result ?? data
  if (!results) return []

  const web = results?.web ?? results?.web_results ?? results?.hits ?? null
  const news = results?.news ?? results?.news_results ?? null

  if (Array.isArray(web)) buckets.push(...web)
  if (Array.isArray(news)) buckets.push(...news)

  if (buckets.length === 0 && Array.isArray(results)) buckets.push(...results)

  const bullets = []
  for (let i = 0; i < buckets.length && bullets.length < maxBullets; i += 1) {
    const text = pickBestSnippet(buckets[i])
    if (!text) continue
    bullets.push(text)
  }

  // Ensure unique-ish bullets.
  const seen = new Set()
  return bullets.filter((b) => {
    const key = b.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export const QUERY_TEMPLATES = {
  market_regime: (year = new Date().getFullYear()) =>
    `current market conditions, volatility regime, Fed policy outlook ${year}`,
  strategy_trends: (year = new Date().getFullYear()) =>
    `trading strategy trends ${year}: volatility filters, regime switching, drawdown control`,
  economic_indicators: (year = new Date().getFullYear()) =>
    `economic indicators ${year}: CPI, jobs report, rates, yield curve, credit spreads`,
  sector_performance: (year = new Date().getFullYear()) =>
    `sector performance ${year}: tech vs defensives vs energy, relative strength, macro drivers`,
}

export function makeGenerationQueries(generationNumber) {
  const g = Math.max(0, Math.round(safeNumber(generationNumber, 0)))
  const year = new Date().getFullYear()
  return [
    `gen ${g}: ${QUERY_TEMPLATES.market_regime(year)}`,
    `gen ${g}: ${QUERY_TEMPLATES.sector_performance(year)}`,
    `gen ${g}: ${QUERY_TEMPLATES.strategy_trends(year)}`,
  ]
}

export class YouComRateLimitError extends Error {
  constructor(message, { retryAfterMs } = {}) {
    super(message)
    this.name = 'YouComRateLimitError'
    this.retryAfterMs = retryAfterMs ?? null
  }
}

export async function searchYouCom(query, options = {}) {
  const apiKey =
    options.apiKey ??
    import.meta.env.VITE_YOUCOM_API_KEY ??
    import.meta.env.VITE_YOUCOM_KEY ??
    null

  if (!apiKey) {
    throw new Error(
      'Missing You.com API key. Set VITE_YOUCOM_API_KEY in darwin-ai-frontend/.env (not committed).',
    )
  }

  const endpoint = options.endpoint ?? DEFAULT_ENDPOINT
  const count = clamp(Math.round(safeNumber(options.count, 8)), 1, 15)

  // Basic client-side throttle to avoid hammering the API.
  const now = Date.now()
  const wait = Math.max(0, _lastCallAt + MIN_CALL_INTERVAL_MS - now)
  if (wait > 0) await sleep(wait)
  _lastCallAt = Date.now()

  const url = new URL(endpoint)
  url.searchParams.set('query', String(query ?? ''))
  url.searchParams.set('count', String(count))

  const res = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      'X-API-Key': apiKey,
    },
    signal: options.signal,
  })

  if (res.status === 429) {
    const retryAfter = res.headers.get('retry-after')
    const retryAfterMs = retryAfter ? Number(retryAfter) * 1000 : null
    throw new YouComRateLimitError('You.com rate limit exceeded', { retryAfterMs })
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`You.com API error (${res.status}): ${text.slice(0, 160)}`)
  }

  const data = await res.json()
  const results = parseBulletsFromResponse(data, count)

  return {
    results,
    timestamp: new Date().toISOString(),
    raw: data,
  }
}

