/*
  Darwin AI - Pre-scripted demo scenarios (presentation-safe)
  ---------------------------------------------------------
  These scenarios are deterministic (no randomness) so demos look the same every time.
  Shapes match the rest of the frontend mock schema:
    - evolution run: { run_id, generations, lineage, champion, stats, ...extras }
    - strategy: { id, name?, graph, results, state }
*/

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function makeGraph({
  gen,
  key,
  name,
  parentGraph = null,
  universe = { symbols: ['AAPL', 'MSFT'], universe_name: 'tech_stocks' },
  bar_size = '1d',
}) {
  const id = `strat_gen${gen}_${key}`
  return {
    id,
    name,
    version: '1.0',
    universe,
    time_config: {
      bar_size,
      timezone: 'America/New_York',
      date_range: { start: '2021-01-01T00:00:00.000Z', end: '2024-12-31T00:00:00.000Z' },
      warmup_bars: 120,
    },
    nodes: [
      {
        id: 'data',
        type: 'MarketData',
        params: {
          field: 'close',
          symbols: universe.symbols,
          bar_size,
        },
        outputs: ['close'],
      },
      {
        id: 'sma20',
        type: 'SMA',
        params: { period: 20 },
        inputs: { series: 'data.close' },
        outputs: ['sma'],
      },
      {
        id: 'rsi',
        type: 'RSI',
        params: { period: 14 },
        inputs: { series: 'data.close' },
        outputs: ['rsi'],
      },
      {
        id: 'cmp1',
        type: 'Compare',
        params: { op: '>' },
        inputs: { left: 'data.close', right: 'sma20.sma' },
        outputs: ['bool'],
      },
      {
        id: 'sig',
        type: 'Signal',
        params: { direction: 'long' },
        inputs: { condition: 'cmp1.bool' },
        outputs: ['signal'],
      },
      {
        id: 'ord',
        type: 'OrderGenerator',
        params: { sizing: 'vol_target', max_leverage: 1.4 },
        inputs: { signal: 'sig.signal' },
        outputs: ['orders'],
      },
    ],
    metadata: { parent_graph: parentGraph, generation: gen },
  }
}

function makeEpisode({ label, start_ts, fitness, tags, difficulty, debug_stats }) {
  return {
    label,
    start_ts,
    fitness,
    tags,
    difficulty,
    debug_stats: {
      trades: debug_stats?.trades ?? 52,
      bars: debug_stats?.bars ?? 220,
      fills: debug_stats?.fills ?? 61,
      sharpe: debug_stats?.sharpe ?? 1.4,
      max_drawdown: debug_stats?.max_drawdown ?? 0.12,
      win_rate: debug_stats?.win_rate ?? 0.56,
      slippage_bps: debug_stats?.slippage_bps ?? 6.2,
    },
  }
}

function makePhase3({
  aggregated_fitness,
  median_fitness,
  unique_regimes = 6,
  years_covered = 2.8,
  penalties = {},
  per_regime_fitness = null,
  episodes = [],
}) {
  const defaultPerRegime = per_regime_fitness ?? {
    up_low_trending: 0.12,
    down_mid_trending: 0.08,
    sideways_high_choppy: 0.06,
    shock_high_mixed: 0.05,
    grind_mid_trending: 0.10,
    down_high_choppy: 0.04,
  }

  return {
    aggregated_fitness,
    median_fitness,
    penalties: {
      drawdown_penalty: penalties.drawdown_penalty ?? 0.01,
      dispersion_penalty: penalties.dispersion_penalty ?? 0.02,
      churn_penalty: penalties.churn_penalty ?? 0.01,
      overfit_penalty: penalties.overfit_penalty ?? 0.01,
      total_penalty: penalties.total_penalty ?? 0.05,
    },
    regime_coverage: {
      unique_regimes,
      years_covered,
      per_regime_fitness: defaultPerRegime,
    },
    episodes,
  }
}

function makeResults({
  phase3,
  verdict,
  failures = [],
  next_action,
  blue_memo = {},
}) {
  return {
    phase3,
    red_verdict: {
      verdict,
      failures,
      next_action: next_action ?? (verdict === 'SURVIVE' ? 'breed' : 'discard'),
    },
    blue_memo: {
      summary: blue_memo.summary ?? (verdict === 'SURVIVE' ? 'Passes Phase 3.' : 'Fails Phase 3.'),
      verdict_rationale: blue_memo.verdict_rationale ?? verdict,
      strengths: blue_memo.strengths ?? [],
      weaknesses: blue_memo.weaknesses ?? [],
      recommended_mutations: blue_memo.recommended_mutations ?? [],
    },
  }
}

function makeStrategy({
  gen,
  key,
  name,
  parentGraph = null,
  state,
  aggregated,
  median,
  verdict,
  failures = [],
  episodes,
  penalties,
  unique_regimes,
  years_covered,
  universe,
}) {
  const graph = makeGraph({
    gen,
    key,
    name: name ?? `Strategy ${key}`,
    parentGraph,
    universe,
  })

  const phase3 = makePhase3({
    aggregated_fitness: aggregated,
    median_fitness: median,
    penalties,
    unique_regimes,
    years_covered,
    episodes,
  })

  const results = makeResults({
    phase3,
    verdict,
    failures,
    blue_memo: {
      strengths: aggregated >= 0.1 ? ['Strong cross-regime performance'] : ['Clear signal, but needs stabilization'],
      weaknesses:
        verdict === 'KILL_LUCKY'
          ? ['Suspected lucky spike; low repeatability']
          : verdict === 'KILL_DISPERSION'
            ? ['High dispersion across regimes']
            : verdict === 'KILL_DRAWDOWN'
              ? ['Drawdown control insufficient']
              : [],
      recommended_mutations:
        verdict === 'SURVIVE'
          ? ['Add volatility gate for choppy regimes']
          : ['Reduce exposure after consecutive losses', 'Add regime filter (trend vs chop)'],
    },
  })

  return {
    id: graph.id,
    name: graph.name,
    graph,
    results,
    state,
  }
}

function buildLineage(generations) {
  const all = generations.flat()
  const edges = []
  const roots = []

  all.forEach((s) => {
    const parent = s?.graph?.metadata?.parent_graph ?? null
    if (!parent) {
      roots.push(s.id)
      return
    }
    edges.push({ parent, child: s.id })
  })

  return { roots, edges }
}

function computeStats(generations) {
  const all = generations.flat()
  const total_strategies = all.length
  const total_survivors = all.filter((s) => s.state === 'alive' || s.state === 'elite').length
  const survival_rate = total_strategies ? total_survivors / total_strategies : 0

  const by_generation = generations.map((gen, idx) => {
    const alive = gen.filter((s) => s.state === 'alive').length
    const elite = gen.filter((s) => s.state === 'elite').length
    const dead = gen.filter((s) => s.state === 'dead').length
    const avgFitness =
      gen.reduce((acc, s) => acc + safeNumber(s?.results?.phase3?.aggregated_fitness, 0), 0) /
      Math.max(1, gen.length)
    return {
      generation: idx,
      count: gen.length,
      alive,
      elite,
      dead,
      survival_rate: gen.length ? (alive + elite) / gen.length : 0,
      avg_aggregated_fitness: Number(avgFitness.toFixed(4)),
    }
  })

  return {
    total_strategies,
    total_survivors,
    survival_rate: Number(survival_rate.toFixed(4)),
    by_generation,
  }
}

function pickChampion(generations, preferredId = null) {
  const all = generations.flat()
  if (preferredId) {
    const hit = all.find((s) => s?.id === preferredId) ?? null
    if (hit) return hit
  }
  const viable = all.filter((s) => s.state === 'alive' || s.state === 'elite')
  const pool = viable.length ? viable : all
  const sorted = [...pool].sort(
    (a, b) =>
      safeNumber(b?.results?.phase3?.aggregated_fitness, 0) -
      safeNumber(a?.results?.phase3?.aggregated_fitness, 0),
  )
  return sorted[0] ?? null
}

function makeYouComTimeline(entries) {
  return entries.map((e, i) => ({
    id: e.id ?? `you_${i}`,
    generation: e.generation ?? 0,
    phase: e.phase ?? 'youcom',
    at_s: e.at_s ?? i * 8,
    query: e.query,
    results: e.results ?? [],
    insights: e.insights ?? [],
    mutation_suggestions: e.mutation_suggestions ?? [],
    presenter_note: e.presenter_note ?? null,
  }))
}

function makeApiCosts({
  total_cost,
  breakdown,
  cost_per_generation,
  running_total,
  presenter_note,
}) {
  return {
    total_cost,
    breakdown,
    cost_per_generation,
    running_total,
    presenter_note: presenter_note ?? null,
  }
}

function standardEvolutionScenario() {
  // Fixed episode template (varied tags) for demo readability.
  const EP = [
    {
      tags: { trend: 'down', vol_bucket: 'high', chop_bucket: 'mixed', drawdown_state: 'deep_drawdown' },
      difficulty: 0.78,
      stats: { trades: 34, bars: 210, fills: 41, sharpe: 1.1, max_drawdown: 0.18, win_rate: 0.52, slippage_bps: 9.3 },
    },
    {
      tags: { trend: 'up', vol_bucket: 'mid', chop_bucket: 'trending', drawdown_state: 'mid_drawdown' },
      difficulty: 0.42,
      stats: { trades: 58, bars: 260, fills: 66, sharpe: 1.8, max_drawdown: 0.11, win_rate: 0.59, slippage_bps: 6.1 },
    },
    {
      tags: { trend: 'sideways', vol_bucket: 'high', chop_bucket: 'choppy', drawdown_state: 'mid_drawdown' },
      difficulty: 0.66,
      stats: { trades: 79, bars: 190, fills: 92, sharpe: 0.9, max_drawdown: 0.16, win_rate: 0.48, slippage_bps: 11.6 },
    },
    {
      tags: { trend: 'up', vol_bucket: 'low', chop_bucket: 'trending', drawdown_state: 'at_highs' },
      difficulty: 0.26,
      stats: { trades: 46, bars: 240, fills: 51, sharpe: 2.2, max_drawdown: 0.07, win_rate: 0.62, slippage_bps: 4.8 },
    },
    {
      tags: { trend: 'down', vol_bucket: 'mid', chop_bucket: 'trending', drawdown_state: 'mid_drawdown' },
      difficulty: 0.51,
      stats: { trades: 62, bars: 230, fills: 70, sharpe: 1.4, max_drawdown: 0.13, win_rate: 0.55, slippage_bps: 6.9 },
    },
    {
      tags: { trend: 'sideways', vol_bucket: 'low', chop_bucket: 'mixed', drawdown_state: 'at_highs' },
      difficulty: 0.31,
      stats: { trades: 41, bars: 200, fills: 48, sharpe: 1.7, max_drawdown: 0.09, win_rate: 0.57, slippage_bps: 5.5 },
    },
    {
      tags: { trend: 'up', vol_bucket: 'high', chop_bucket: 'mixed', drawdown_state: 'mid_drawdown' },
      difficulty: 0.73,
      stats: { trades: 29, bars: 175, fills: 33, sharpe: 1.0, max_drawdown: 0.17, win_rate: 0.51, slippage_bps: 12.4 },
    },
    {
      tags: { trend: 'down', vol_bucket: 'low', chop_bucket: 'choppy', drawdown_state: 'mid_drawdown' },
      difficulty: 0.58,
      stats: { trades: 88, bars: 215, fills: 104, sharpe: 0.8, max_drawdown: 0.15, win_rate: 0.46, slippage_bps: 10.2 },
    },
  ]

  const makeEpisodes = (baseDate, fitnesses) =>
    fitnesses.map((f, idx) =>
      makeEpisode({
        label: `episode_${idx + 1}`,
        start_ts: new Date(new Date(baseDate).getTime() + idx * 45 * 24 * 3600 * 1000).toISOString(),
        fitness: f,
        tags: EP[idx % EP.length].tags,
        difficulty: EP[idx % EP.length].difficulty,
        debug_stats: EP[idx % EP.length].stats,
      }),
    )

  // Gen 0: 8 strategies, 5 survive.
  const g0 = [
    makeStrategy({ gen: 0, key: 'A', name: 'Strategy A', state: 'alive', aggregated: 0.074, median: 0.058, verdict: 'SURVIVE', episodes: makeEpisodes('2020-02-01T00:00:00.000Z', [0.06, 0.08, 0.05, 0.09, 0.07, 0.06]) }),
    makeStrategy({ gen: 0, key: 'B', name: 'Strategy B', state: 'dead', aggregated: 0.031, median: 0.028, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2020-02-15T00:00:00.000Z', [0.01, 0.09, 0.00, 0.08, 0.02, 0.03]) }),
    makeStrategy({ gen: 0, key: 'C', name: 'Strategy C', state: 'alive', aggregated: 0.082, median: 0.064, verdict: 'SURVIVE', episodes: makeEpisodes('2020-03-01T00:00:00.000Z', [0.07, 0.10, 0.06, 0.08, 0.05, 0.07]) }),
    makeStrategy({ gen: 0, key: 'D', name: 'Strategy D', state: 'dead', aggregated: 0.128, median: 0.041, verdict: 'KILL_LUCKY', failures: ['LUCKY_SPIKE'], episodes: makeEpisodes('2020-03-15T00:00:00.000Z', [0.20, 0.01, 0.02, 0.00, 0.03, 0.02]) }),
    makeStrategy({ gen: 0, key: 'E', name: 'Strategy E', state: 'alive', aggregated: 0.066, median: 0.052, verdict: 'SURVIVE', episodes: makeEpisodes('2020-04-01T00:00:00.000Z', [0.05, 0.06, 0.06, 0.07, 0.04, 0.06]) }),
    makeStrategy({ gen: 0, key: 'F', name: 'Strategy F', state: 'elite', aggregated: 0.093, median: 0.075, verdict: 'SURVIVE', episodes: makeEpisodes('2020-04-15T00:00:00.000Z', [0.08, 0.10, 0.07, 0.09, 0.06, 0.08]) }),
    makeStrategy({ gen: 0, key: 'G', name: 'Strategy G', state: 'alive', aggregated: 0.071, median: 0.056, verdict: 'SURVIVE', episodes: makeEpisodes('2020-05-01T00:00:00.000Z', [0.05, 0.08, 0.06, 0.07, 0.05, 0.06]) }),
    makeStrategy({ gen: 0, key: 'H', name: 'Strategy H', state: 'dead', aggregated: 0.024, median: 0.022, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: makeEpisodes('2020-05-15T00:00:00.000Z', [0.01, 0.03, 0.02, 0.01, 0.00, 0.02]) }),
  ]

  // Gen 1: 5 parents + 3 mutations, 4 survive.
  const g1 = [
    makeStrategy({ gen: 1, key: 'A1', name: 'Strategy A1', parentGraph: g0[0].id, state: 'alive', aggregated: 0.078, median: 0.061, verdict: 'SURVIVE', episodes: makeEpisodes('2021-02-01T00:00:00.000Z', [0.06, 0.09, 0.05, 0.08, 0.07, 0.06]) }),
    makeStrategy({ gen: 1, key: 'C1', name: 'Strategy C1', parentGraph: g0[2].id, state: 'dead', aggregated: 0.042, median: 0.034, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2021-02-12T00:00:00.000Z', [0.00, 0.10, 0.01, 0.07, 0.02, 0.03]) }),
    makeStrategy({ gen: 1, key: 'E1', name: 'Strategy E1', parentGraph: g0[4].id, state: 'alive', aggregated: 0.069, median: 0.055, verdict: 'SURVIVE', episodes: makeEpisodes('2021-02-20T00:00:00.000Z', [0.05, 0.07, 0.06, 0.08, 0.04, 0.05]) }),
    makeStrategy({ gen: 1, key: 'F1', name: 'Strategy F1', parentGraph: g0[5].id, state: 'elite', aggregated: 0.101, median: 0.081, verdict: 'SURVIVE', episodes: makeEpisodes('2021-03-01T00:00:00.000Z', [0.09, 0.11, 0.08, 0.10, 0.07, 0.09]) }),
    makeStrategy({ gen: 1, key: 'G1', name: 'Strategy G1', parentGraph: g0[6].id, state: 'dead', aggregated: 0.033, median: 0.028, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: makeEpisodes('2021-03-10T00:00:00.000Z', [0.01, 0.04, 0.02, 0.01, 0.00, 0.02]) }),
    makeStrategy({ gen: 1, key: 'A2', name: 'Strategy A2', parentGraph: g0[0].id, state: 'dead', aggregated: 0.122, median: 0.043, verdict: 'KILL_LUCKY', failures: ['LUCKY_SPIKE'], episodes: makeEpisodes('2021-03-18T00:00:00.000Z', [0.18, 0.02, 0.01, 0.00, 0.04, 0.02]) }),
    makeStrategy({ gen: 1, key: 'C2', name: 'Strategy C2', parentGraph: g0[2].id, state: 'dead', aggregated: 0.038, median: 0.032, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2021-03-25T00:00:00.000Z', [0.02, 0.07, 0.01, 0.05, 0.03, 0.02]) }),
    makeStrategy({ gen: 1, key: 'E2', name: 'Strategy E2', parentGraph: g0[4].id, state: 'alive', aggregated: 0.073, median: 0.058, verdict: 'SURVIVE', episodes: makeEpisodes('2021-04-02T00:00:00.000Z', [0.06, 0.08, 0.05, 0.07, 0.06, 0.05]) }),
  ]

  // Gen 2: 6 survive (improving), champion A2.1 = 0.127.
  const g2 = [
    makeStrategy({ gen: 2, key: 'A2_1', name: 'Strategy A2.1', parentGraph: g1[0].id, state: 'elite', aggregated: 0.127, median: 0.105, verdict: 'SURVIVE', episodes: makeEpisodes('2022-02-01T00:00:00.000Z', [0.09, 0.14, 0.08, 0.13, 0.10, 0.12, 0.07, 0.11]) }),
    makeStrategy({ gen: 2, key: 'F2', name: 'Strategy F2', parentGraph: g1[3].id, state: 'alive', aggregated: 0.112, median: 0.090, verdict: 'SURVIVE', episodes: makeEpisodes('2022-02-12T00:00:00.000Z', [0.08, 0.12, 0.07, 0.11, 0.09, 0.10, 0.06]) }),
    makeStrategy({ gen: 2, key: 'E3', name: 'Strategy E3', parentGraph: g1[2].id, state: 'alive', aggregated: 0.089, median: 0.070, verdict: 'SURVIVE', episodes: makeEpisodes('2022-02-22T00:00:00.000Z', [0.06, 0.09, 0.05, 0.10, 0.07, 0.06]) }),
    makeStrategy({ gen: 2, key: 'E3b', name: 'Strategy E3b', parentGraph: g1[7].id, state: 'alive', aggregated: 0.081, median: 0.065, verdict: 'SURVIVE', episodes: makeEpisodes('2022-03-01T00:00:00.000Z', [0.06, 0.08, 0.05, 0.09, 0.07, 0.06]) }),
    makeStrategy({ gen: 2, key: 'A3', name: 'Strategy A3', parentGraph: g1[0].id, state: 'alive', aggregated: 0.096, median: 0.078, verdict: 'SURVIVE', episodes: makeEpisodes('2022-03-10T00:00:00.000Z', [0.07, 0.10, 0.06, 0.11, 0.08, 0.07]) }),
    makeStrategy({ gen: 2, key: 'C3', name: 'Strategy C3', parentGraph: g1[1].id, state: 'dead', aggregated: 0.047, median: 0.038, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2022-03-18T00:00:00.000Z', [0.01, 0.09, 0.02, 0.08, 0.00, 0.03]) }),
    makeStrategy({ gen: 2, key: 'G2', name: 'Strategy G2', parentGraph: g1[4].id, state: 'dead', aggregated: 0.034, median: 0.028, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: makeEpisodes('2022-03-25T00:00:00.000Z', [0.01, 0.04, 0.02, 0.01, 0.02, 0.01]) }),
    makeStrategy({ gen: 2, key: 'A3b', name: 'Strategy A3b', parentGraph: g1[5].id, state: 'alive', aggregated: 0.077, median: 0.061, verdict: 'SURVIVE', episodes: makeEpisodes('2022-04-01T00:00:00.000Z', [0.06, 0.08, 0.05, 0.07, 0.06, 0.05]) }),
  ]

  // Gen 3: 5 survive.
  const g3 = [
    makeStrategy({ gen: 3, key: 'A2_1a', name: 'Strategy A2.1a', parentGraph: g2[0].id, state: 'elite', aggregated: 0.121, median: 0.099, verdict: 'SURVIVE', episodes: makeEpisodes('2023-02-01T00:00:00.000Z', [0.09, 0.13, 0.07, 0.12, 0.09, 0.10, 0.06]) }),
    makeStrategy({ gen: 3, key: 'F3', name: 'Strategy F3', parentGraph: g2[1].id, state: 'alive', aggregated: 0.103, median: 0.083, verdict: 'SURVIVE', episodes: makeEpisodes('2023-02-10T00:00:00.000Z', [0.08, 0.11, 0.07, 0.10, 0.08, 0.09]) }),
    makeStrategy({ gen: 3, key: 'E4', name: 'Strategy E4', parentGraph: g2[2].id, state: 'dead', aggregated: 0.044, median: 0.036, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2023-02-18T00:00:00.000Z', [0.02, 0.07, 0.01, 0.06, 0.03, 0.02]) }),
    makeStrategy({ gen: 3, key: 'A4', name: 'Strategy A4', parentGraph: g2[4].id, state: 'alive', aggregated: 0.091, median: 0.074, verdict: 'SURVIVE', episodes: makeEpisodes('2023-02-26T00:00:00.000Z', [0.07, 0.10, 0.06, 0.09, 0.07, 0.06]) }),
    makeStrategy({ gen: 3, key: 'A4b', name: 'Strategy A4b', parentGraph: g2[4].id, state: 'dead', aggregated: 0.118, median: 0.041, verdict: 'KILL_LUCKY', failures: ['LUCKY_SPIKE'], episodes: makeEpisodes('2023-03-05T00:00:00.000Z', [0.17, 0.01, 0.02, 0.00, 0.03, 0.02]) }),
    makeStrategy({ gen: 3, key: 'E5', name: 'Strategy E5', parentGraph: g2[3].id, state: 'alive', aggregated: 0.084, median: 0.067, verdict: 'SURVIVE', episodes: makeEpisodes('2023-03-12T00:00:00.000Z', [0.06, 0.09, 0.05, 0.08, 0.07, 0.06]) }),
    makeStrategy({ gen: 3, key: 'G3', name: 'Strategy G3', parentGraph: g2[6].id, state: 'dead', aggregated: 0.035, median: 0.028, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: makeEpisodes('2023-03-20T00:00:00.000Z', [0.01, 0.04, 0.02, 0.01, 0.02, 0.01]) }),
    makeStrategy({ gen: 3, key: 'F3b', name: 'Strategy F3b', parentGraph: g2[1].id, state: 'dead', aggregated: 0.041, median: 0.034, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: makeEpisodes('2023-03-28T00:00:00.000Z', [0.00, 0.08, 0.02, 0.07, 0.01, 0.03]) }),
  ]

  // Gen 4: 7 survive (highly adapted).
  const g4 = [
    makeStrategy({ gen: 4, key: 'A2_1b', name: 'Strategy A2.1b', parentGraph: g3[0].id, state: 'elite', aggregated: 0.124, median: 0.101, verdict: 'SURVIVE', episodes: makeEpisodes('2024-02-01T00:00:00.000Z', [0.10, 0.13, 0.08, 0.12, 0.10, 0.11, 0.08]) }),
    makeStrategy({ gen: 4, key: 'F4', name: 'Strategy F4', parentGraph: g3[1].id, state: 'alive', aggregated: 0.109, median: 0.088, verdict: 'SURVIVE', episodes: makeEpisodes('2024-02-10T00:00:00.000Z', [0.09, 0.12, 0.07, 0.11, 0.09, 0.10]) }),
    makeStrategy({ gen: 4, key: 'A5', name: 'Strategy A5', parentGraph: g3[3].id, state: 'alive', aggregated: 0.097, median: 0.079, verdict: 'SURVIVE', episodes: makeEpisodes('2024-02-18T00:00:00.000Z', [0.08, 0.10, 0.06, 0.11, 0.08, 0.07]) }),
    makeStrategy({ gen: 4, key: 'E6', name: 'Strategy E6', parentGraph: g3[5].id, state: 'alive', aggregated: 0.086, median: 0.069, verdict: 'SURVIVE', episodes: makeEpisodes('2024-02-26T00:00:00.000Z', [0.06, 0.09, 0.06, 0.08, 0.07, 0.06]) }),
    makeStrategy({ gen: 4, key: 'F4b', name: 'Strategy F4b', parentGraph: g3[1].id, state: 'alive', aggregated: 0.093, median: 0.076, verdict: 'SURVIVE', episodes: makeEpisodes('2024-03-05T00:00:00.000Z', [0.07, 0.10, 0.06, 0.09, 0.08, 0.07]) }),
    makeStrategy({ gen: 4, key: 'A5b', name: 'Strategy A5b', parentGraph: g3[0].id, state: 'alive', aggregated: 0.090, median: 0.072, verdict: 'SURVIVE', episodes: makeEpisodes('2024-03-12T00:00:00.000Z', [0.07, 0.09, 0.06, 0.08, 0.07, 0.06]) }),
    makeStrategy({ gen: 4, key: 'E6b', name: 'Strategy E6b', parentGraph: g3[5].id, state: 'alive', aggregated: 0.081, median: 0.064, verdict: 'SURVIVE', episodes: makeEpisodes('2024-03-20T00:00:00.000Z', [0.06, 0.08, 0.05, 0.08, 0.06, 0.05]) }),
    makeStrategy({ gen: 4, key: 'G4', name: 'Strategy G4', parentGraph: g3[6].id, state: 'dead', aggregated: 0.036, median: 0.028, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: makeEpisodes('2024-03-28T00:00:00.000Z', [0.01, 0.04, 0.02, 0.01, 0.02, 0.01]) }),
  ]

  const generations = [g0, g1, g2, g3, g4]
  const lineage = buildLineage(generations)
  const champion = pickChampion(generations, g2[0].id)
  const stats = computeStats(generations)

  const youcom_timeline = makeYouComTimeline([
    {
      generation: 0,
      at_s: 12,
      query: 'gen 0: current market conditions, volatility regime, Fed policy outlook 2026',
      results: ['VIX elevated; risk premia rising', 'Macro headline risk driving dispersion', 'Choppy tape: mean reversion edges fragile'],
      insights: ['Current regime: Elevated volatility; defensive positioning favored.'],
      mutation_suggestions: ['Add volatility filter (VIX/ATR) to gate entries during high vol'],
      presenter_note: 'Set the scene: why robustness matters early.',
    },
    {
      generation: 2,
      at_s: 32,
      query: 'gen 2: sector performance 2026: tech vs defensives vs energy',
      results: ['Defensives outperform in high vol', 'Tech beta unstable around rate repricing', 'Energy relative strength notable'],
      insights: ['Favor robustness filters and position sizing that adapts to volatility.'],
      mutation_suggestions: ['Implement defensive rotation overlay when volatility spikes'],
      presenter_note: 'Explain why A2.1 wins: stable across regimes.',
    },
  ])

  const api_costs = makeApiCosts({
    total_cost: 15.5,
    breakdown: {
      you_com_searches: { calls: 12, cost: 0.024 },
      llm_mutations: { calls: 96, cost: 2.88 },
      validation_runs: { calls: 40, cost: 0.32 },
    },
    cost_per_generation: [2.7, 2.9, 3.1, 3.2, 3.6],
    running_total: [2.7, 5.6, 8.7, 11.9, 15.5],
    presenter_note: 'Costs are moderate and trend upward as exploration expands.',
  })

  return {
    scenario_name: 'Standard Evolution',
    scenario_id: 'standard_evolution',
    run_id: `demo_standard_${Date.now()}`,
    generations,
    lineage,
    champion,
    stats,
    youcom_timeline,
    api_costs,
    key_moments: [
      {
        at: { generation: 0, phase: 'validation', strategy: g0[3].id },
        title: 'Lucky Spike Kill',
        note: 'High fitness but killed: demonstrates robustness gating.',
      },
      {
        at: { generation: 2, phase: 'validation', strategy: g2[0].id },
        title: 'Champion Emerges',
        note: 'Strategy A2.1 becomes elite at fitness 0.127.',
      },
      {
        at: { generation: 4, phase: 'intro' },
        title: 'Highly Adapted Population',
        note: 'Survival rate reaches 88% (7/8).',
      },
    ],
    timing_hints: {
      recommended_speed: 2,
      presenter_cues: [
        'Gen 0: call out initial diversity and early culling.',
        'Gen 2: highlight A2.1 as stable across regimes.',
        'Gen 4: close with high survival and controlled cost growth.',
      ],
    },
  }
}

function youComSavesTheDayScenario() {
  const epWeak = [
    makeEpisode({
      label: 'episode_1',
      start_ts: '2021-03-15T00:00:00.000Z',
      fitness: 0.01,
      tags: { trend: 'sideways', vol_bucket: 'high', chop_bucket: 'choppy', drawdown_state: 'mid_drawdown' },
      difficulty: 0.72,
      debug_stats: { trades: 96, bars: 195, fills: 112, sharpe: 0.2, max_drawdown: 0.24, win_rate: 0.44, slippage_bps: 12.7 },
    }),
    makeEpisode({
      label: 'episode_2',
      start_ts: '2021-06-01T00:00:00.000Z',
      fitness: 0.06,
      tags: { trend: 'up', vol_bucket: 'mid', chop_bucket: 'mixed', drawdown_state: 'at_highs' },
      difficulty: 0.38,
      debug_stats: { trades: 58, bars: 240, fills: 64, sharpe: 1.2, max_drawdown: 0.12, win_rate: 0.53, slippage_bps: 6.8 },
    }),
    makeEpisode({
      label: 'episode_3',
      start_ts: '2021-09-10T00:00:00.000Z',
      fitness: 0.02,
      tags: { trend: 'down', vol_bucket: 'high', chop_bucket: 'mixed', drawdown_state: 'deep_drawdown' },
      difficulty: 0.81,
      debug_stats: { trades: 41, bars: 210, fills: 48, sharpe: 0.0, max_drawdown: 0.29, win_rate: 0.41, slippage_bps: 13.2 },
    }),
    makeEpisode({
      label: 'episode_4',
      start_ts: '2022-01-18T00:00:00.000Z',
      fitness: 0.03,
      tags: { trend: 'sideways', vol_bucket: 'mid', chop_bucket: 'choppy', drawdown_state: 'mid_drawdown' },
      difficulty: 0.62,
      debug_stats: { trades: 84, bars: 205, fills: 96, sharpe: 0.4, max_drawdown: 0.21, win_rate: 0.46, slippage_bps: 9.8 },
    }),
  ]

  const epRescued = [
    makeEpisode({
      label: 'episode_1',
      start_ts: '2022-03-20T00:00:00.000Z',
      fitness: 0.07,
      tags: { trend: 'down', vol_bucket: 'high', chop_bucket: 'mixed', drawdown_state: 'mid_drawdown' },
      difficulty: 0.76,
      debug_stats: { trades: 38, bars: 205, fills: 44, sharpe: 1.0, max_drawdown: 0.17, win_rate: 0.52, slippage_bps: 10.6 },
    }),
    makeEpisode({
      label: 'episode_2',
      start_ts: '2022-06-15T00:00:00.000Z',
      fitness: 0.11,
      tags: { trend: 'up', vol_bucket: 'mid', chop_bucket: 'trending', drawdown_state: 'at_highs' },
      difficulty: 0.44,
      debug_stats: { trades: 56, bars: 260, fills: 62, sharpe: 1.9, max_drawdown: 0.10, win_rate: 0.60, slippage_bps: 6.0 },
    }),
    makeEpisode({
      label: 'episode_3',
      start_ts: '2022-09-08T00:00:00.000Z',
      fitness: 0.08,
      tags: { trend: 'sideways', vol_bucket: 'high', chop_bucket: 'choppy', drawdown_state: 'mid_drawdown' },
      difficulty: 0.69,
      debug_stats: { trades: 44, bars: 190, fills: 50, sharpe: 1.2, max_drawdown: 0.14, win_rate: 0.54, slippage_bps: 9.9 },
    }),
    makeEpisode({
      label: 'episode_4',
      start_ts: '2023-01-25T00:00:00.000Z',
      fitness: 0.10,
      tags: { trend: 'up', vol_bucket: 'low', chop_bucket: 'trending', drawdown_state: 'at_highs' },
      difficulty: 0.28,
      debug_stats: { trades: 47, bars: 240, fills: 53, sharpe: 2.1, max_drawdown: 0.07, win_rate: 0.62, slippage_bps: 4.6 },
    }),
  ]

  const g0 = [
    makeStrategy({ gen: 0, key: 'A', name: 'Strategy A', state: 'alive', aggregated: 0.066, median: 0.052, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 0, key: 'B', name: 'Strategy B', state: 'alive', aggregated: 0.058, median: 0.044, verdict: 'SURVIVE', episodes: epWeak }),
    makeStrategy({ gen: 0, key: 'C', name: 'Strategy C', state: 'dead', aggregated: 0.031, median: 0.026, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: epWeak }),
    makeStrategy({ gen: 0, key: 'D', name: 'Strategy D', state: 'dead', aggregated: 0.121, median: 0.039, verdict: 'KILL_LUCKY', failures: ['LUCKY_SPIKE'], episodes: epWeak }),
    makeStrategy({ gen: 0, key: 'E', name: 'Strategy E', state: 'alive', aggregated: 0.071, median: 0.056, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 0, key: 'F', name: 'Strategy F', state: 'elite', aggregated: 0.095, median: 0.078, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 0, key: 'G', name: 'Strategy G', state: 'dead', aggregated: 0.028, median: 0.024, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: epWeak }),
    makeStrategy({ gen: 0, key: 'H', name: 'Strategy H', state: 'dead', aggregated: 0.024, median: 0.022, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: epWeak }),
  ]

  // Gen 1: Strategy B looks weak (fitness 0.04).
  const g1 = [
    makeStrategy({ gen: 1, key: 'A1', name: 'Strategy A1', parentGraph: g0[0].id, state: 'alive', aggregated: 0.074, median: 0.058, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 1, key: 'B', name: 'Strategy B', parentGraph: g0[1].id, state: 'dead', aggregated: 0.040, median: 0.033, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: epWeak }),
    makeStrategy({ gen: 1, key: 'E1', name: 'Strategy E1', parentGraph: g0[4].id, state: 'alive', aggregated: 0.078, median: 0.061, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 1, key: 'F1', name: 'Strategy F1', parentGraph: g0[5].id, state: 'elite', aggregated: 0.101, median: 0.082, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 1, key: 'A2', name: 'Strategy A2', parentGraph: g0[0].id, state: 'dead', aggregated: 0.036, median: 0.030, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: epWeak }),
    makeStrategy({ gen: 1, key: 'E2', name: 'Strategy E2', parentGraph: g0[4].id, state: 'alive', aggregated: 0.070, median: 0.055, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 1, key: 'X1', name: 'Strategy X1', parentGraph: g0[1].id, state: 'dead', aggregated: 0.122, median: 0.041, verdict: 'KILL_LUCKY', failures: ['LUCKY_SPIKE'], episodes: epWeak }),
    makeStrategy({ gen: 1, key: 'Y1', name: 'Strategy Y1', parentGraph: g0[1].id, state: 'dead', aggregated: 0.030, median: 0.025, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: epWeak }),
  ]

  // Gen 2: Mutation adds volatility filter; B1 survives with 0.09.
  const universeVol = { symbols: ['SPY', 'QQQ', 'IWM'], universe_name: 'us_index_mix' }
  const g2 = [
    makeStrategy({ gen: 2, key: 'B1', name: 'Strategy B1 (Vol Filter)', parentGraph: g1[1].id, state: 'alive', aggregated: 0.090, median: 0.072, verdict: 'SURVIVE', episodes: epRescued, universe: universeVol }),
    makeStrategy({ gen: 2, key: 'F2', name: 'Strategy F2', parentGraph: g1[3].id, state: 'elite', aggregated: 0.112, median: 0.090, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 2, key: 'E3', name: 'Strategy E3', parentGraph: g1[2].id, state: 'alive', aggregated: 0.084, median: 0.067, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 2, key: 'A3', name: 'Strategy A3', parentGraph: g1[0].id, state: 'alive', aggregated: 0.079, median: 0.062, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 2, key: 'E3b', name: 'Strategy E3b', parentGraph: g1[5].id, state: 'alive', aggregated: 0.072, median: 0.056, verdict: 'SURVIVE', episodes: epRescued }),
    makeStrategy({ gen: 2, key: 'Z2', name: 'Strategy Z2', parentGraph: g1[1].id, state: 'dead', aggregated: 0.035, median: 0.028, verdict: 'KILL_DRAWDOWN', failures: ['DRAWDOWN_EXCEEDED'], episodes: epWeak }),
    makeStrategy({ gen: 2, key: 'K2', name: 'Strategy K2', parentGraph: g1[3].id, state: 'dead', aggregated: 0.043, median: 0.035, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: epWeak }),
    makeStrategy({ gen: 2, key: 'M2', name: 'Strategy M2', parentGraph: g1[2].id, state: 'dead', aggregated: 0.040, median: 0.032, verdict: 'KILL_DISPERSION', failures: ['HIGH_DISPERSION'], episodes: epWeak }),
  ]

  const generations = [g0, g1, g2]
  const lineage = buildLineage(generations)
  const champion = pickChampion(generations, g2[1].id)
  const stats = computeStats(generations)

  const youcom_timeline = makeYouComTimeline([
    {
      generation: 1,
      at_s: 18,
      query: 'high volatility regime detection: VIX, realized vol, market microstructure',
      results: ['VIX elevated; spikes around macro events', 'Realized volatility rising; dispersion in tech', 'Liquidity thinner; risk-off rotation'],
      insights: ['Current regime: High volatility; defensive positioning favored.'],
      mutation_suggestions: ['Add volatility filter to reduce exposure in high VIX', 'Reduce position sizing when volatility spikes'],
      presenter_note: 'Narrator line: You.com intelligence prevented extinction.',
    },
  ])

  const api_costs = makeApiCosts({
    total_cost: 9.8,
    breakdown: {
      you_com_searches: { calls: 8, cost: 0.016 },
      llm_mutations: { calls: 42, cost: 1.26 },
      validation_runs: { calls: 24, cost: 0.192 },
    },
    cost_per_generation: [3.1, 3.2, 3.5],
    running_total: [3.1, 6.3, 9.8],
    presenter_note: 'Focused search + one key mutation. Lower cost, big impact.',
  })

  return {
    scenario_name: 'You.com Saves The Day',
    scenario_id: 'youcom_saves_the_day',
    run_id: `demo_youcom_${Date.now()}`,
    generations,
    lineage,
    champion,
    stats,
    youcom_timeline,
    api_costs,
    key_moments: [
      {
        at: { generation: 1, phase: 'validation', strategy: g1[1].id },
        title: 'Near-extinction Risk',
        note: 'Strategy B looks weak (fitness 0.04) and gets killed for dispersion.',
      },
      {
        at: { generation: 1, phase: 'youcom' },
        title: 'You.com Intelligence',
        note: 'Detects high volatility regime and suggests gating exposure.',
      },
      {
        at: { generation: 2, phase: 'validation', strategy: g2[0].id },
        title: 'Rescue Mutation',
        note: 'B1 adds volatility filter and survives at 0.09 fitness.',
      },
    ],
    timing_hints: {
      recommended_speed: 2,
      presenter_cues: [
        'Pause briefly on Gen 1 Strategy B: low fitness but plausible idea.',
        'Narrate the You.com insight as the turning point.',
        'Show Gen 2 B1: survives after adding volatility gating.',
      ],
      narrator_line: 'You.com intelligence prevented extinction.',
    },
  }
}

function rapidEvolutionScenario() {
  // 10 generations, simple upward trend in survival and fitness.
  const generations = []
  const roots = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

  // Gen 0 baseline
  const g0 = roots.map((k, idx) =>
    makeStrategy({
      gen: 0,
      key: k,
      name: `Strategy ${k}`,
      state: idx < 3 ? 'dead' : idx === 7 ? 'elite' : 'alive',
      aggregated: idx < 3 ? 0.028 + idx * 0.004 : 0.055 + idx * 0.006,
      median: idx < 3 ? 0.022 + idx * 0.003 : 0.043 + idx * 0.004,
      verdict: idx < 3 ? (idx === 1 ? 'KILL_LUCKY' : 'KILL_DISPERSION') : 'SURVIVE',
      failures: idx < 3 ? ['HIGH_DISPERSION'] : [],
      episodes: [
        makeEpisode({
          label: 'episode_1',
          start_ts: '2020-02-01T00:00:00.000Z',
          fitness: idx < 3 ? 0.01 : 0.07,
          tags: { trend: idx % 2 ? 'up' : 'sideways', vol_bucket: 'mid', chop_bucket: 'mixed', drawdown_state: 'mid_drawdown' },
          difficulty: 0.52,
          debug_stats: { trades: 64, bars: 240, fills: 73, sharpe: idx < 3 ? 0.3 : 1.2, max_drawdown: idx < 3 ? 0.25 : 0.15, win_rate: idx < 3 ? 0.44 : 0.55, slippage_bps: 8.8 },
        }),
        makeEpisode({
          label: 'episode_2',
          start_ts: '2020-06-01T00:00:00.000Z',
          fitness: idx < 3 ? 0.02 : 0.09,
          tags: { trend: 'up', vol_bucket: 'low', chop_bucket: 'trending', drawdown_state: 'at_highs' },
          difficulty: 0.30,
          debug_stats: { trades: 49, bars: 260, fills: 55, sharpe: idx < 3 ? 0.6 : 1.9, max_drawdown: idx < 3 ? 0.22 : 0.10, win_rate: idx < 3 ? 0.47 : 0.60, slippage_bps: 5.1 },
        }),
      ],
    }),
  )
  generations.push(g0)

  // Subsequent generations: survivors improve; final champion much stronger.
  let parentPool = g0.filter((s) => s.state !== 'dead')
  for (let gen = 1; gen < 10; gen += 1) {
    const surviveTarget = Math.min(8, 4 + Math.floor(gen * 0.35)) // increases over time
    const next = []

    // Carry parents (first 5 or fewer)
    for (let i = 0; i < Math.min(5, parentPool.length); i += 1) {
      const p = parentPool[i]
      const agg = Number((safeNumber(p.results.phase3.aggregated_fitness, 0.06) + 0.005 + gen * 0.0015).toFixed(3))
      next.push(
        makeStrategy({
          gen,
          key: `${p.graph.id.split('_').slice(-1)[0]}${gen}`,
          name: `Strategy ${p.name?.replace('Strategy ', '')}${gen}`,
          parentGraph: p.id,
          state: 'alive',
          aggregated: agg,
          median: Number((agg - 0.02).toFixed(3)),
          verdict: 'SURVIVE',
          episodes: p.results.phase3.episodes,
        }),
      )
    }

    // Mutations
    while (next.length < 8) {
      const parent = parentPool[next.length % parentPool.length]
      const isBreakthrough = gen >= 7 && next.length === 7
      const agg = isBreakthrough ? 0.148 : Number((0.060 + gen * 0.006 + next.length * 0.001).toFixed(3))
      next.push(
        makeStrategy({
          gen,
          key: `M${gen}_${next.length}`,
          name: isBreakthrough ? `Strategy Omega${gen}` : `Strategy M${gen}.${next.length}`,
          parentGraph: parent?.id ?? null,
          state: 'alive',
          aggregated: agg,
          median: Number((agg - 0.025).toFixed(3)),
          verdict: 'SURVIVE',
          episodes: parent?.results?.phase3?.episodes ?? g0[0].results.phase3.episodes,
        }),
      )
    }

    // Mark some dead to hit survival trend target; keep 1 elite every few gens.
    next
      .slice()
      .sort((a, b) => safeNumber(b.results.phase3.aggregated_fitness, 0) - safeNumber(a.results.phase3.aggregated_fitness, 0))
      .forEach((s, idx) => {
        if (idx === 0 && gen % 2 === 0) s.state = 'elite'
        if (idx >= surviveTarget) {
          s.state = 'dead'
          s.results.red_verdict.verdict = idx === surviveTarget ? 'KILL_LUCKY' : 'KILL_DISPERSION'
          s.results.red_verdict.failures = ['HIGH_DISPERSION']
          s.results.red_verdict.next_action = 'discard'
        }
      })

    generations.push(next)
    parentPool = next.filter((s) => s.state !== 'dead')
  }

  const lineage = buildLineage(generations)
  const champion = pickChampion(generations, generations[9][7].id)
  const stats = computeStats(generations)

  const youcom_timeline = makeYouComTimeline(
    [0, 2, 4, 6, 8].map((g) => ({
      generation: g,
      at_s: g * 6,
      query: `gen ${g}: rapid demo intelligence checkpoint (volatility, regime, positioning)`,
      results: ['Regime evolving: volatility clusters observed', 'Best strategies add gating and throttles', 'Avoid overtrading in choppy tape'],
      insights: ['Use regime-aware filters; increase robustness, reduce tail risk.'],
      mutation_suggestions: ['Add volatility gate', 'Throttle risk after drawdown', 'Require trend confirmation'],
      presenter_note: g === 0 ? 'Start fast; explain what to watch.' : null,
    })),
  )

  const api_costs = makeApiCosts({
    total_cost: 28.4,
    breakdown: {
      you_com_searches: { calls: 28, cost: 0.056 },
      llm_mutations: { calls: 280, cost: 8.4 },
      validation_runs: { calls: 80, cost: 0.64 },
    },
    cost_per_generation: [1.8, 2.0, 2.2, 2.3, 2.6, 2.8, 3.0, 3.2, 3.6, 4.9],
    running_total: [1.8, 3.8, 6.0, 8.3, 10.9, 13.7, 16.7, 19.9, 23.5, 28.4],
    presenter_note: 'Costs escalate with 10 generations; show why budgets matter at speed.',
  })

  return {
    scenario_name: 'Rapid Evolution',
    scenario_id: 'rapid_evolution',
    run_id: `demo_rapid_${Date.now()}`,
    generations,
    lineage,
    champion,
    stats,
    youcom_timeline,
    api_costs,
    key_moments: [
      {
        at: { generation: 0, phase: 'intro' },
        title: 'Baseline',
        note: 'Gen 0 is noisy and fragile; survivorship is modest.',
      },
      {
        at: { generation: 6, phase: 'intro' },
        title: 'Momentum Shift',
        note: 'Survival trend is clearly upward; elites appear more often.',
      },
      {
        at: { generation: 9, phase: 'validation', strategy: champion?.id },
        title: 'Breakthrough Champion',
        note: 'Final champion is dramatically better than Gen 0.',
      },
    ],
    timing_hints: {
      recommended_speed: 10,
      target_runtime_seconds: 60,
      presenter_cues: [
        'Run at 10x speed; point at survival trend + champion improving.',
        'Call out cost escalation as a real-world constraint.',
      ],
    },
  }
}

export const DEMO_SCENARIOS = {
  'Standard Evolution': standardEvolutionScenario,
  'You.com Saves The Day': youComSavesTheDayScenario,
  'Rapid Evolution': rapidEvolutionScenario,
}

export function loadScenario(name) {
  const key = String(name ?? '').trim()
  const fn = DEMO_SCENARIOS[key] ?? null
  if (!fn) {
    const available = Object.keys(DEMO_SCENARIOS)
    throw new Error(`Unknown scenario "${key}". Available: ${available.join(', ')}`)
  }
  return fn()
}

export function listScenarios() {
  return Object.keys(DEMO_SCENARIOS)
}

export default {
  DEMO_SCENARIOS,
  loadScenario,
  listScenarios,
}

