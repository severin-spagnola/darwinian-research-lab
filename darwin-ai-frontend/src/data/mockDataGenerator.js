/*
  Darwin AI - Mock Data Generators
  --------------------------------
  These generators are meant to produce realistic-looking data for UI development.
  They intentionally keep shapes stable, while values vary with plausible ranges.
*/

const SYMBOL_POOLS = [
  {
    universe_name: 'tech_stocks',
    symbols: ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN'],
  },
  {
    universe_name: 'mega_cap',
    symbols: ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'BRK.B', 'JPM'],
  },
  {
    universe_name: 'energy',
    symbols: ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY'],
  },
  {
    universe_name: 'crypto_liquid',
    symbols: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'ADA-USD'],
  },
]

const STRATEGY_NAME_PARTS = {
  left: [
    'Emerald',
    'Kestrel',
    'Cobalt',
    'Onyx',
    'Atlas',
    'Vector',
    'Helix',
    'Aegis',
    'Quartz',
    'Nova',
  ],
  right: [
    'SMA-RSI',
    'Regime Filter',
    'Breakout',
    'Mean Reversion',
    'Trend Rider',
    'Vol Guard',
    'Momentum Mix',
    'Chop Filter',
    'Risk Parity',
    'Drawdown Brake',
  ],
}

const TAGS = {
  trend: ['up', 'down', 'sideways'],
  vol_bucket: ['low', 'mid', 'high'],
  chop_bucket: ['trending', 'choppy', 'mixed'],
  drawdown_state: ['at_highs', 'mid_drawdown', 'deep_drawdown'],
}

function randInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function randFloat(min, max, decimals = 4) {
  const n = Math.random() * (max - min) + min
  const m = 10 ** decimals
  return Math.round(n * m) / m
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function pick(arr) {
  return arr[randInt(0, arr.length - 1)]
}

function pickManyUnique(arr, count) {
  const copy = [...arr]
  const out = []
  const n = Math.min(count, copy.length)
  for (let i = 0; i < n; i += 1) {
    const idx = randInt(0, copy.length - 1)
    out.push(copy[idx])
    copy.splice(idx, 1)
  }
  return out
}

function isoDateBetween(startIso, endIso) {
  const start = new Date(startIso).getTime()
  const end = new Date(endIso).getTime()
  const t = randInt(start, end)
  return new Date(t).toISOString()
}

function makeStrategyName() {
  return `${pick(STRATEGY_NAME_PARTS.left)} ${pick(STRATEGY_NAME_PARTS.right)}`
}

function makeUniverse() {
  const pool = pick(SYMBOL_POOLS)
  const symbolCount = randInt(2, Math.min(4, pool.symbols.length))
  const symbols = pickManyUnique(pool.symbols, symbolCount)
  return { symbols, universe_name: pool.universe_name }
}

function makeTimeConfig() {
  // Keep the window reasonably recent but long enough for regime diversity.
  const endYear = randInt(2023, 2025)
  const startYear = endYear - randInt(2, 4)
  const start = `${startYear}-01-01T00:00:00.000Z`
  const end = `${endYear}-12-31T00:00:00.000Z`

  return {
    bar_size: pick(['1d', '4h', '1h']),
    timezone: 'America/New_York',
    date_range: { start, end },
    warmup_bars: randInt(50, 200),
  }
}

function makePerRegimeFitness(baseFitness) {
  const regimes = [
    'up_low_trending',
    'up_high_choppy',
    'down_mid_trending',
    'down_high_choppy',
    'sideways_low_mixed',
    'sideways_high_choppy',
    'shock_high_mixed',
    'grind_mid_trending',
  ]
  const out = {}
  const used = pickManyUnique(regimes, randInt(4, 8))
  used.forEach((r) => {
    // Regime fitness clusters around base fitness with regime-specific noise.
    out[r] = clamp(randFloat(baseFitness - 0.05, baseFitness + 0.06), 0.0, 0.22)
  })
  return out
}

function makePenalties(shouldSurvive) {
  // Survivors tend to have lower penalties; dead strategies skew higher.
  const scale = shouldSurvive ? 0.6 : 1.0
  const drawdown_penalty = randFloat(0.0, 0.06 * scale)
  const dispersion_penalty = randFloat(0.0, 0.05 * scale)
  const churn_penalty = randFloat(0.0, 0.04 * scale)
  const overfit_penalty = randFloat(0.0, 0.06 * scale)

  return {
    drawdown_penalty,
    dispersion_penalty,
    churn_penalty,
    overfit_penalty,
    total_penalty: clamp(
      randFloat(
        drawdown_penalty + dispersion_penalty,
        drawdown_penalty + dispersion_penalty + churn_penalty + overfit_penalty,
      ),
      0,
      0.25,
    ),
  }
}

function makeEpisodeTags({ ensureDifferentFrom } = {}) {
  const candidate = {
    trend: pick(TAGS.trend),
    vol_bucket: pick(TAGS.vol_bucket),
    chop_bucket: pick(TAGS.chop_bucket),
    drawdown_state: pick(TAGS.drawdown_state),
  }

  if (!ensureDifferentFrom) return candidate

  // Make sure we don't accidentally generate identical regimes back-to-back.
  const keys = Object.keys(candidate)
  let same = true
  keys.forEach((k) => {
    if (candidate[k] !== ensureDifferentFrom[k]) same = false
  })
  if (!same) return candidate

  // Force a difference on a random dimension.
  const k = pick(keys)
  const options = TAGS[k].filter((v) => v !== candidate[k])
  return { ...candidate, [k]: pick(options) }
}

function makeEpisodeDebugStats({ baseFitness, difficulty }) {
  const trades = randInt(15, 220)
  const win_rate = clamp(randFloat(0.35, 0.65), 0, 1)
  const avg_hold_days = randFloat(0.5, 7.5)
  const max_drawdown = clamp(randFloat(0.02, 0.22 + difficulty * 0.1), 0.01, 0.35)
  const sharpe = clamp(randFloat(-0.2, 2.4) + (baseFitness - 0.06) * 12, -0.5, 3.2)
  const turnover = clamp(randFloat(0.2, 3.5) + difficulty * 0.4, 0.05, 5.0)
  const slippage_bps = clamp(randFloat(0.5, 12.0) + turnover * 1.2, 0.25, 35)

  return {
    trades,
    win_rate,
    avg_hold_days,
    max_drawdown,
    sharpe,
    turnover,
    slippage_bps,
    exposure_avg: clamp(randFloat(0.2, 1.0), 0, 1),
  }
}

function decideKillVerdict() {
  const roll = Math.random()
  if (roll < 0.25) return 'KILL_LUCKY'
  if (roll < 0.65) return 'KILL_DISPERSION'
  return 'KILL_DRAWDOWN'
}

function sampleFitness(shouldSurvive, verdict) {
  // Survivors cluster higher; dead strategies cluster lower.
  // "Lucky spike" kills are intentionally high-fitness but killed anyway.
  if (shouldSurvive) return randFloat(0.06, 0.15)

  if (verdict === 'KILL_LUCKY') return randFloat(0.12, 0.15)
  if (verdict === 'KILL_DRAWDOWN') return randFloat(0.02, 0.1)
  return randFloat(0.01, 0.09)
}

function makeBlueMemo({ shouldSurvive, verdict, aggregated_fitness }) {
  const strengths = []
  const weaknesses = []
  const next = []

  if (aggregated_fitness >= 0.11) strengths.push('Strong cross-regime performance')
  if (aggregated_fitness >= 0.08) strengths.push('Stable median fitness')
  if (aggregated_fitness < 0.05) weaknesses.push('Low signal quality across regimes')

  if (verdict === 'KILL_DISPERSION') weaknesses.push('High dispersion across episodes')
  if (verdict === 'KILL_DRAWDOWN') weaknesses.push('Drawdown control insufficient')
  if (verdict === 'KILL_LUCKY') weaknesses.push('Suspected lucky spike, low repeatability')

  next.push('Add volatility filter (VIX / ATR) gating exposure')
  next.push('Introduce drawdown-aware position sizing')
  next.push('Add regime detector for choppy vs trending markets')

  return {
    summary: shouldSurvive
      ? 'Passes Phase 3 with acceptable stability and coverage.'
      : 'Fails Phase 3 due to stability / risk issues.',
    verdict_rationale: verdict,
    strengths,
    weaknesses,
    recommended_mutations: pickManyUnique(next, randInt(1, 3)),
  }
}

// 1) generateStrategyGraph(id, generation, parentId = null)
export function generateStrategyGraph(id, generation, parentId = null) {
  const name = makeStrategyName()
  const universe = makeUniverse()
  const time_config = makeTimeConfig()

  // Minor, realistic parameter variability to simulate mutation.
  const smaPeriod = randInt(10, 55)
  const rsiPeriod = randInt(7, 21)
  const compareOp = pick(['>', '<'])
  const signalDirection = pick(['long', 'short'])

  return {
    id: `strat_gen${generation}_${id}`,
    name: `Strategy ${name}`,
    version: '1.0',
    universe,
    time_config,
    nodes: [
      {
        id: 'data',
        type: 'MarketData',
        params: {
          field: 'close',
          symbols: universe.symbols,
          bar_size: time_config.bar_size,
        },
        outputs: ['close'],
      },
      {
        id: 'sma20',
        type: 'SMA',
        params: { period: smaPeriod },
        inputs: { series: 'data.close' },
        outputs: ['sma'],
      },
      {
        id: 'rsi',
        type: 'RSI',
        params: { period: rsiPeriod },
        inputs: { series: 'data.close' },
        outputs: ['rsi'],
      },
      {
        id: 'cmp1',
        type: 'Compare',
        params: { op: compareOp },
        inputs: { left: 'data.close', right: 'sma20.sma' },
        outputs: ['bool'],
      },
      {
        id: 'sig',
        type: 'Signal',
        params: { direction: signalDirection },
        inputs: { condition: 'cmp1.bool' },
        outputs: ['signal'],
      },
      {
        id: 'ord',
        type: 'OrderGenerator',
        params: {
          sizing: pick(['fixed_fraction', 'vol_target', 'risk_parity']),
          max_leverage: randFloat(0.8, 2.0, 2),
        },
        inputs: { signal: 'sig.signal' },
        outputs: ['orders'],
      },
    ],
    metadata: { parent_graph: parentId, generation },
  }
}

// 2) generatePhase3Results(strategyId, shouldSurvive = true)
export function generatePhase3Results(strategyId, shouldSurvive = true) {
  const verdict = shouldSurvive ? 'SURVIVE' : decideKillVerdict()

  const aggregated_fitness = sampleFitness(shouldSurvive, verdict)
  // Keep within the expected envelope: median is typically lower than aggregated.
  const median_fitness = clamp(
    randFloat(aggregated_fitness - 0.06, Math.min(0.12, aggregated_fitness + 0.01)),
    0.02,
    0.12,
  )

  const penalties = makePenalties(shouldSurvive)
  const regime_coverage = {
    unique_regimes: randInt(4, 8),
    years_covered: randFloat(1.5, 3.5, 2),
    per_regime_fitness: makePerRegimeFitness(aggregated_fitness),
  }

  const episodeCount = randInt(5, 8)
  const episodes = []
  let prevTags = null
  const seenRegimes = new Set()
  for (let i = 0; i < episodeCount; i += 1) {
    let tags = null
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const candidate = makeEpisodeTags({ ensureDifferentFrom: prevTags })
      const key = `${candidate.trend}|${candidate.vol_bucket}|${candidate.chop_bucket}|${candidate.drawdown_state}`
      if (!seenRegimes.has(key) || attempt === 11) {
        tags = candidate
        seenRegimes.add(key)
        break
      }
    }
    prevTags = tags

    // Episode fitness should generally track aggregated_fitness but vary by regime difficulty.
    const difficulty = randFloat(0.1, 0.9, 3)
    const regimePenalty = (difficulty - 0.5) * 0.08
    const episodeFitness = clamp(
      randFloat(aggregated_fitness - 0.06, aggregated_fitness + 0.08) - regimePenalty,
      0,
      0.2,
    )

    episodes.push({
      label: `episode_${i + 1}`,
      start_ts: isoDateBetween('2021-01-01T00:00:00.000Z', '2025-12-01T00:00:00.000Z'),
      fitness: episodeFitness,
      tags,
      difficulty,
      debug_stats: makeEpisodeDebugStats({
        baseFitness: aggregated_fitness,
        difficulty,
      }),
    })
  }

  const failures = shouldSurvive ? [] : ['HIGH_DISPERSION']
  if (!shouldSurvive) {
    if (verdict === 'KILL_DRAWDOWN') failures.push('DRAWDOWN_EXCEEDED')
    if (verdict === 'KILL_LUCKY') failures.push('LUCKY_SPIKE')
  }

  return {
    phase3: {
      aggregated_fitness,
      median_fitness,
      penalties,
      regime_coverage,
      episodes,
    },
    red_verdict: {
      verdict,
      failures,
      next_action: shouldSurvive ? 'breed' : 'discard',
    },
    blue_memo: makeBlueMemo({
      shouldSurvive,
      verdict,
      aggregated_fitness,
      strategyId,
    }),
  }
}

function pickSurvivalCount(n) {
  const min = Math.ceil(n * 0.4)
  const max = Math.floor(n * 0.6)
  return randInt(min, Math.max(min, max))
}

function assignStates(strategies) {
  // Mark top survivors as "elite" (1-2), rest as "alive", dead remain "dead".
  const survivors = strategies
    .filter((s) => s.results?.red_verdict?.verdict === 'SURVIVE')
    .sort(
      (a, b) =>
        (b.results?.phase3?.aggregated_fitness ?? 0) -
        (a.results?.phase3?.aggregated_fitness ?? 0),
    )

  const eliteCount = Math.min(2, survivors.length, Math.random() < 0.65 ? 1 : 2)
  const eliteIds = new Set(survivors.slice(0, eliteCount).map((s) => s.id))

  return strategies.map((s) => {
    if (s.results?.red_verdict?.verdict !== 'SURVIVE') return { ...s, state: 'dead' }
    if (eliteIds.has(s.id)) return { ...s, state: 'elite' }
    return { ...s, state: 'alive' }
  })
}

// 3) generateGeneration(genNumber, previousSurvivors = [])
export function generateGeneration(genNumber, previousSurvivors = []) {
  const n = randInt(8, 10)
  const surviveCount = pickSurvivalCount(n)

  // Decide upfront which slots survive to keep per-generation survival rate stable.
  const flags = Array.from({ length: n }, (_, i) => i < surviveCount)
  // Shuffle flags
  for (let i = flags.length - 1; i > 0; i -= 1) {
    const j = randInt(0, i)
    ;[flags[i], flags[j]] = [flags[j], flags[i]]
  }

  const strategies = []

  const prev = previousSurvivors.filter((s) => s && s.id && s.graph)
  const plannedCarry = genNumber === 0 ? 0 : Math.round(n * 0.6)
  const carryCount = Math.min(plannedCarry, prev.length)
  const mutationCount = n - carryCount

  const chosenCarry = genNumber === 0 ? [] : pickManyUnique(prev, carryCount)

  // Carryover strategies: same "genetic material", re-evaluated in new generation.
  chosenCarry.forEach((parent, idx) => {
    const graph = generateStrategyGraph(`carry_${idx}_${parent.id}`, genNumber, parent.graph.id)
    const id = graph.id
    const results = generatePhase3Results(id, flags[strategies.length] ?? true)
    strategies.push({ id, graph, results, state: 'alive' })
  })

  // Mutations: bred from a random survivor (or random if none provided).
  for (let i = 0; i < mutationCount; i += 1) {
    const parent = prev.length ? pick(prev) : null
    const parentId = parent ? parent.graph.id : null
    const graph = generateStrategyGraph(`mut_${i}`, genNumber, parentId)
    const id = graph.id
    const results = generatePhase3Results(id, flags[strategies.length] ?? false)
    strategies.push({ id, graph, results, state: 'alive' })
  }

  return assignStates(strategies)
}

function buildLineage(allStrategies) {
  const edges = []
  const childrenByParent = {}
  const roots = []

  allStrategies.forEach((s) => {
    const parent = s?.graph?.metadata?.parent_graph ?? null
    if (!parent) {
      roots.push(s.id)
      return
    }
    edges.push({ parent, child: s.id })
    if (!childrenByParent[parent]) childrenByParent[parent] = []
    childrenByParent[parent].push(s.id)
  })

  return { roots, edges, childrenByParent }
}

function selectChampion(allStrategies) {
  const viable = allStrategies.filter((s) => s.state === 'alive' || s.state === 'elite')
  const pool = viable.length ? viable : allStrategies
  const sorted = [...pool].sort(
    (a, b) =>
      (b.results?.phase3?.aggregated_fitness ?? 0) -
      (a.results?.phase3?.aggregated_fitness ?? 0),
  )
  return sorted[0] ?? null
}

function computeRunStats(generations) {
  const all = generations.flat()
  const total_strategies = all.length
  const total_survivors = all.filter((s) => s.state === 'alive' || s.state === 'elite').length
  const survival_rate = total_strategies ? randFloat(total_survivors / total_strategies, total_survivors / total_strategies, 4) : 0

  const by_generation = generations.map((gen, idx) => {
    const alive = gen.filter((s) => s.state === 'alive').length
    const elite = gen.filter((s) => s.state === 'elite').length
    const dead = gen.filter((s) => s.state === 'dead').length
    const avgFitness =
      gen.reduce((acc, s) => acc + (s.results?.phase3?.aggregated_fitness ?? 0), 0) /
      Math.max(1, gen.length)

    return {
      generation: idx,
      count: gen.length,
      alive,
      elite,
      dead,
      survival_rate: gen.length ? randFloat((alive + elite) / gen.length, (alive + elite) / gen.length, 4) : 0,
      avg_aggregated_fitness: randFloat(avgFitness, avgFitness, 4),
    }
  })

  return {
    total_strategies,
    total_survivors,
    survival_rate,
    by_generation,
  }
}

// 4) generateEvolutionRun(numGenerations = 5)
export function generateEvolutionRun(numGenerations = 5) {
  const generations = []
  let previousSurvivors = []

  for (let g = 0; g < numGenerations; g += 1) {
    const gen = generateGeneration(g, previousSurvivors)
    generations.push(gen)
    previousSurvivors = gen.filter((s) => s.state === 'alive' || s.state === 'elite')
  }

  const allStrategies = generations.flat()
  const lineage = buildLineage(allStrategies)
  const champion = selectChampion(allStrategies)
  const stats = computeRunStats(generations)

  return {
    run_id: `run_${Date.now()}`,
    generations,
    lineage,
    champion,
    stats,
  }
}

// 5) generateYouComResponse(query)
export function generateYouComResponse(query) {
  const macro = [
    'Fed signals higher-for-longer stance; front-end rates firm',
    'Inflation surprise drives repricing across duration',
    'Credit spreads widen modestly; risk appetite mixed',
  ]
  const equity = [
    'Tech sector down 2-4% amid rate concerns',
    'Momentum factor weakens; defensives outperform',
    'Liquidity conditions tighten; breadth deteriorates',
  ]
  const vol = [
    'VIX volatility index elevated around 20-26',
    'Skew steepens; downside hedging demand rises',
    'Realized vol picks up after macro headline risk',
  ]

  const insights = [
    'Current regime: elevated volatility; prioritize risk controls and filters.',
    'Rate sensitivity is high; favor strategies with lower duration exposure.',
    'Choppy tape likely; reduce overtrading and add confirmation signals.',
  ]

  const mutation_suggestions = [
    'Add volatility filter to reduce exposure when VIX / ATR is high',
    'Implement drawdown-based throttle on position sizing',
    'Use regime classifier (trend vs chop) to switch entry logic',
    'Add stop logic tied to volatility bands rather than fixed %',
  ]

  return {
    query,
    timestamp: new Date().toISOString(),
    results: pickManyUnique([...macro, ...equity, ...vol], 3),
    insights: pickManyUnique(insights, 2),
    mutation_suggestions: pickManyUnique(mutation_suggestions, 2),
  }
}

// 6) generateAPICosts(numGenerations, numStrategies)
export function generateAPICosts(numGenerations, numStrategies) {
  // Rough, plausible per-call costs (USD). Adjust as needed for your app narrative.
  const unit = {
    you: 0.002,
    llm: 0.03,
    validate: 0.008,
  }

  const calls = {
    you_com_searches: randInt(Math.max(3, Math.floor(numGenerations * 1.2)), Math.max(5, Math.floor(numGenerations * 2.5))),
    llm_mutations: randInt(Math.max(6, Math.floor(numStrategies * 0.6)), Math.max(10, Math.floor(numStrategies * 1.1))),
    validation_runs: randInt(Math.max(10, Math.floor(numStrategies * 0.8)), Math.max(15, Math.floor(numStrategies * 1.4))),
  }

  const breakdown = {
    you_com_searches: {
      calls: calls.you_com_searches,
      cost: randFloat(calls.you_com_searches * unit.you, calls.you_com_searches * unit.you, 4),
    },
    llm_mutations: {
      calls: calls.llm_mutations,
      cost: randFloat(calls.llm_mutations * unit.llm, calls.llm_mutations * unit.llm, 4),
    },
    validation_runs: {
      calls: calls.validation_runs,
      cost: randFloat(calls.validation_runs * unit.validate, calls.validation_runs * unit.validate, 4),
    },
  }

  const total_cost = randFloat(
    breakdown.you_com_searches.cost + breakdown.llm_mutations.cost + breakdown.validation_runs.cost,
    breakdown.you_com_searches.cost + breakdown.llm_mutations.cost + breakdown.validation_runs.cost,
    4,
  )

  const cost_per_generation = []
  const running_total = []
  let rt = 0
  for (let g = 0; g < numGenerations; g += 1) {
    const base = total_cost / Math.max(1, numGenerations)
    const jitter = randFloat(-base * 0.25, base * 0.25, 4)
    const c = clamp(randFloat(base + jitter, base + jitter, 4), 0, 9999)
    cost_per_generation.push(c)
    rt = randFloat(rt + c, rt + c, 4)
    running_total.push(rt)
  }

  return {
    total_cost,
    breakdown,
    cost_per_generation,
    running_total,
  }
}

export default {
  generateStrategyGraph,
  generatePhase3Results,
  generateGeneration,
  generateEvolutionRun,
  generateYouComResponse,
  generateAPICosts,
}
