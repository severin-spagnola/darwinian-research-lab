import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { generateYouComResponse } from '../data/mockDataGenerator.js'
import { makeGenerationQueries, searchYouCom } from '../utils/youcomAPI.js'

const SPEEDS = [1, 2, 5, 10]

const BASE_MS = {
  generationIntro: 1500,
  perStrategyValidation: 1200,
  perEpisodeDisplay: 300,
  verdictReveal: 600,
  showResults: 1200,
  youComSearch: 1500,
  insightParse: 1000,
  mutationCreationPerChild: 800,
}

const COST_UNIT = {
  you_com_searches: 0.002,
  llm_mutations: 0.03,
  validation_runs: 0.008,
}

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function safeNumber(n, fallback = 0) {
  const v = Number(n)
  return Number.isFinite(v) ? v : fallback
}

function makeId(prefix = 'evt') {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function emptyCosts(totalGenerations) {
  const tg = Math.max(1, Math.round(safeNumber(totalGenerations, 5)))
  return {
    total_cost: 0,
    breakdown: {
      you_com_searches: { calls: 0, cost: 0 },
      llm_mutations: { calls: 0, cost: 0 },
      validation_runs: { calls: 0, cost: 0 },
    },
    cost_per_generation: Array.from({ length: tg }, () => 0),
    running_total: Array.from({ length: tg }, () => 0),
  }
}

function recomputeRunningTotal(cost_per_generation) {
  const out = []
  let rt = 0
  for (let i = 0; i < cost_per_generation.length; i += 1) {
    rt += safeNumber(cost_per_generation[i], 0)
    out.push(Number(rt.toFixed(4)))
  }
  return out
}

function addCost(prev, { key, generation, calls = 1 }) {
  const k = String(key)
  const unit = COST_UNIT[k] ?? 0
  const g = Math.max(0, Math.round(safeNumber(generation, 0)))

  const breakdown = {
    ...prev.breakdown,
    [k]: {
      calls: Math.max(0, Math.round(safeNumber(prev.breakdown?.[k]?.calls, 0) + calls)),
      cost: Number((safeNumber(prev.breakdown?.[k]?.cost, 0) + unit * calls).toFixed(4)),
    },
  }

  const cost_per_generation = prev.cost_per_generation.slice()
  if (cost_per_generation.length) {
    const idx = clamp(g, 0, cost_per_generation.length - 1)
    cost_per_generation[idx] = Number(
      (safeNumber(cost_per_generation[idx], 0) + unit * calls).toFixed(4),
    )
  }

  const running_total = recomputeRunningTotal(cost_per_generation)
  const total_cost = Number(
    Object.values(breakdown).reduce((acc, row) => acc + safeNumber(row.cost, 0), 0).toFixed(4),
  )

  return { ...prev, total_cost, breakdown, cost_per_generation, running_total }
}

function skeletonResultsFromFinal(finalStrategy) {
  const final = finalStrategy?.results ?? null
  const phase3 = final?.phase3 ?? {}
  return {
    phase3: {
      aggregated_fitness: 0,
      median_fitness: 0,
      penalties: phase3?.penalties ?? {},
      regime_coverage: phase3?.regime_coverage ?? {},
      episodes: [],
    },
    red_verdict: {
      verdict: null,
      failures: [],
      next_action: null,
    },
    blue_memo: final?.blue_memo ?? {},
  }
}

function liveFromFinal(finalStrategy) {
  return {
    ...finalStrategy,
    state: 'alive',
    results: skeletonResultsFromFinal(finalStrategy),
    validation_progress: 0,
  }
}

function applyEpisodeProgress(strategy, { episodes, episodeIndex, total }) {
  const p = total > 0 ? clamp((episodeIndex + 1) / total, 0, 1) : 0
  return {
    ...strategy,
    validation_progress: p,
    results: {
      ...strategy.results,
      phase3: {
        ...strategy.results?.phase3,
        episodes,
      },
    },
  }
}

function revealFinal(strategy, finalStrategy) {
  return {
    ...strategy,
    state: finalStrategy?.state ?? strategy?.state ?? 'alive',
    results: finalStrategy?.results ?? strategy?.results,
    validation_progress: 1,
  }
}

async function sleepMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export default function useEvolutionPlayback(evolutionData, options) {
  const totalGenerations = useMemo(() => {
    const gens = evolutionData?.generations
    return Array.isArray(gens) ? gens.length : 0
  }, [evolutionData])

  const [playbackSeed, setPlaybackSeed] = useState(0)
  const [isPlaying, setIsPlaying] = useState(() => {
    const v = options?.initialIsPlaying
    return v === undefined ? true : Boolean(v)
  })
  const [playbackSpeed, setPlaybackSpeed] = useState(2)

  const [currentGeneration, setCurrentGeneration] = useState(0)
  const [currentPhase, setCurrentPhase] = useState('intro')
  const [validatingStrategyIndex, setValidatingStrategyIndex] = useState(null)
  const [testingEpisodeIndex, setTestingEpisodeIndex] = useState(null)

  const [strategies, setStrategies] = useState([])
  const [selectedId, setSelectedId] = useState(null)

  const [youComActivity, setYouComActivity] = useState([])
  const [apiCosts, setApiCosts] = useState(() => emptyCosts(totalGenerations || 5))

  const isPlayingRef = useRef(isPlaying)
  const speedRef = useRef(playbackSpeed)
  const runTokenRef = useRef(0)
  const userSelectedRef = useRef(false)
  const optionsRef = useRef(options ?? null)

  useEffect(() => {
    optionsRef.current = options ?? null
  }, [options])

  useEffect(() => {
    isPlayingRef.current = isPlaying
  }, [isPlaying])

  useEffect(() => {
    speedRef.current = playbackSpeed
  }, [playbackSpeed])

  const selectedStrategy = useMemo(() => {
    if (!selectedId) return null
    const list = Array.isArray(strategies) ? strategies : []
    return list.find((s) => s?.id === selectedId) ?? null
  }, [selectedId, strategies])

  const play = useCallback(() => setIsPlaying(true), [])
  const pause = useCallback(() => setIsPlaying(false), [])

  const setSpeed = useCallback((multiplier) => {
    const v = Number(multiplier)
    const next = SPEEDS.includes(v) ? v : 1
    setPlaybackSpeed(next)
  }, [])

  const selectStrategy = useCallback((id) => {
    const next = id ? String(id) : null
    userSelectedRef.current = true
    setSelectedId(next)
  }, [])

  const reset = useCallback(() => {
    runTokenRef.current += 1
    userSelectedRef.current = false
    setCurrentGeneration(0)
    setCurrentPhase('intro')
    setValidatingStrategyIndex(null)
    setTestingEpisodeIndex(null)
    setStrategies([])
    setSelectedId(null)
    setYouComActivity([])
    setApiCosts(emptyCosts(totalGenerations || 5))
    setIsPlaying(true)
    setPlaybackSeed((s) => s + 1)
  }, [totalGenerations])

  const nextGeneration = useCallback(() => {
    const tg = Math.max(0, totalGenerations - 1)
    const next = clamp(currentGeneration + 1, 0, tg)
    runTokenRef.current += 1
    userSelectedRef.current = false
    setCurrentGeneration(next)
    setCurrentPhase('intro')
    setValidatingStrategyIndex(null)
    setTestingEpisodeIndex(null)
    setStrategies([])
    setSelectedId(null)
    setYouComActivity([])
    setIsPlaying(true)
    setPlaybackSeed((s) => s + 1)
  }, [currentGeneration, totalGenerations])

  const waitBase = useCallback(async (baseMs, token) => {
    // Wait in "base time units" while accounting for pause + dynamic speed changes.
    let remainingBase = Math.max(0, Math.round(safeNumber(baseMs, 0)))
    const stepWall = 50

    while (remainingBase > 0) {
      if (token !== runTokenRef.current) throw new Error('ABORTED')

      await sleepMs(Math.min(stepWall, 120))

      if (!isPlayingRef.current) continue

      const speed = Math.max(1, safeNumber(speedRef.current, 1))
      remainingBase -= stepWall * speed
    }
  }, [])

  useEffect(() => {
    if (!evolutionData || !Array.isArray(evolutionData.generations) || evolutionData.generations.length === 0) {
      setStrategies([])
      setCurrentPhase('complete')
      return undefined
    }

    const gens = evolutionData.generations
    const startGen = clamp(currentGeneration, 0, gens.length - 1)

    const token = runTokenRef.current + 1
    runTokenRef.current = token

    const fire = (name, payload) => {
      const fn = optionsRef.current?.[name]
      if (typeof fn === 'function') fn(payload)
    }

    const loadGenerationInstant = async (g) => {
      const finalGen = gens[g] ?? []
      const live = finalGen.map((s) => liveFromFinal(s))

      setCurrentGeneration(g)
      setCurrentPhase('intro')
      setValidatingStrategyIndex(null)
      setTestingEpisodeIndex(null)
      setStrategies(live)

      fire('onGenerationStart', { generation: g, strategies: live })

      // Auto-select best (unless user selected).
      if (!userSelectedRef.current) {
        const best = [...finalGen]
          .slice()
          .sort(
            (a, b) =>
              safeNumber(b?.results?.phase3?.aggregated_fitness, 0) -
              safeNumber(a?.results?.phase3?.aggregated_fitness, 0),
          )[0]
        setSelectedId(best?.id ?? live[0]?.id ?? null)
      }
    }

    const validateGenerationSequential = async (g) => {
      const finalGen = gens[g] ?? []
      const finalById = new Map(finalGen.map((s) => [s.id, s]))

      setCurrentPhase('validation')

      for (let i = 0; i < finalGen.length; i += 1) {
        if (token !== runTokenRef.current) throw new Error('ABORTED')

        setValidatingStrategyIndex(i)
        setTestingEpisodeIndex(null)

        const id = finalGen[i]?.id
        if (!id) continue

        fire('onStrategyValidationStart', { generation: g, index: i, strategyId: id })

        // Mark as testing + clear episodes.
        setStrategies((prev) =>
          prev.map((s) =>
            s.id === id
              ? {
                  ...s,
                  state: 'testing',
                  results: skeletonResultsFromFinal(finalById.get(id)),
                  validation_progress: 0,
                }
              : s,
          ),
        )

        if (!userSelectedRef.current) setSelectedId(id)

        // Validation runtime (before episodes stream in).
        await waitBase(BASE_MS.perStrategyValidation, token)

        // Count a "validation run" cost per strategy.
        setApiCosts((prev) => addCost(prev, { key: 'validation_runs', generation: g, calls: 1 }))

        const final = finalById.get(id)
        const episodes = Array.isArray(final?.results?.phase3?.episodes) ? final.results.phase3.episodes : []

        for (let e = 0; e < episodes.length; e += 1) {
          if (token !== runTokenRef.current) throw new Error('ABORTED')
          setTestingEpisodeIndex(e)

          const shown = episodes.slice(0, e + 1)
          setStrategies((prev) =>
            prev.map((s) =>
              s.id === id
                ? applyEpisodeProgress(s, { episodes: shown, episodeIndex: e, total: episodes.length })
                : s,
            ),
          )

          await waitBase(BASE_MS.perEpisodeDisplay, token)
        }

        // Verdict reveal delay.
        await waitBase(BASE_MS.verdictReveal, token)

        // Reveal final verdict/results + final state (alive/dead/elite).
        const verdict = final?.results?.red_verdict?.verdict ?? null
        setStrategies((prev) => prev.map((s) => (s.id === id ? revealFinal(s, final) : s)))

        if (verdict && String(verdict).startsWith('KILL')) {
          fire('onStrategyKilled', { generation: g, index: i, strategyId: id, verdict })
        } else {
          fire('onStrategySurvived', { generation: g, index: i, strategyId: id, verdict: verdict ?? 'SURVIVE' })
        }
      }

      setValidatingStrategyIndex(null)
      setTestingEpisodeIndex(null)
    }

    const youcomPhase = async (g) => {
      setCurrentPhase('youcom')

      const queries = makeGenerationQueries(g)
      const query = queries[0] ?? `gen ${g}: market regime analysis`
      const entryId = makeId('you')
      const startTs = new Date().toISOString()

      setYouComActivity((prev) =>
        [
          ...(Array.isArray(prev) ? prev : []),
          {
            id: entryId,
            query,
            timestamp: startTs,
            status: 'loading',
            results: [],
            insights: [],
            mutation_suggestions: [],
            error: null,
          },
        ].slice(-30),
      )

      fire('onYouComSearch', { generation: g, query })

      // Search runtime (UI loading).
      await waitBase(BASE_MS.youComSearch, token)

      // Charge 1 You.com search call.
      setApiCosts((prev) => addCost(prev, { key: 'you_com_searches', generation: g, calls: 1 }))

      let response = null
      let status = 'live'
      let errorMsg = null

      try {
        // Always route through backend proxy (has YOUCOM_API_KEY on server)
        const { searchYouCom: backendSearch } = await import('../api/client.js')
        const resp = await backendSearch(query, { count: 8 })
        response = {
          query,
          timestamp: resp.timestamp,
          results: resp.results ?? [],
          insights: [],
          mutation_suggestions: [],
        }
        status = 'live'
      } catch (err) {
        // Fallback to mock if backend proxy fails
        errorMsg = err instanceof Error ? err.message : String(err)
        response = generateYouComResponse(query)
        status = 'cached'
      }

      setYouComActivity((prev) =>
        (Array.isArray(prev) ? prev : []).map((e) =>
          e.id === entryId
            ? {
                ...e,
                timestamp: response?.timestamp ?? startTs,
                status,
                results: response?.results ?? [],
                error: errorMsg,
              }
            : e,
        ),
      )

      // Insight parsing runtime.
      await waitBase(BASE_MS.insightParse, token)

      // Generate insights from results or use mock fallback for insight text
      const mockInsights = generateYouComResponse(query)
      const withInsights =
        response?.insights?.length && response?.mutation_suggestions?.length
          ? response
          : { ...response, insights: mockInsights?.insights ?? [], mutation_suggestions: mockInsights?.mutation_suggestions ?? [] }

      setYouComActivity((prev) =>
        (Array.isArray(prev) ? prev : []).map((e) =>
          e.id === entryId
            ? {
                ...e,
                insights: withInsights?.insights ?? [],
                mutation_suggestions: withInsights?.mutation_suggestions ?? [],
              }
            : e,
        ),
      )
    }

    const mutateToNextGeneration = async (nextGen) => {
      setCurrentPhase('mutation')

      const finalGen = gens[nextGen] ?? []
      const live = []

      setCurrentGeneration(nextGen)
      setStrategies([])
      setValidatingStrategyIndex(null)
      setTestingEpisodeIndex(null)

      fire('onMutationCreated', { generation: nextGen, count: finalGen.length })

      for (let i = 0; i < finalGen.length; i += 1) {
        if (token !== runTokenRef.current) throw new Error('ABORTED')

        const s = liveFromFinal(finalGen[i])
        live.push(s)
        setStrategies(live.slice())

        // Charge 1 "mutation" call per created strategy (LLM).
        setApiCosts((prev) => addCost(prev, { key: 'llm_mutations', generation: nextGen, calls: 1 }))

        await waitBase(BASE_MS.mutationCreationPerChild, token)
      }

      // Let the user see the fresh population briefly before validation begins.
      setCurrentPhase('intro')
      fire('onGenerationStart', { generation: nextGen, strategies: live })

      if (!userSelectedRef.current) {
        setSelectedId(live[0]?.id ?? null)
      }
    }

    let mounted = true

    const run = async () => {
      // Initialize costs for this run.
      setApiCosts(emptyCosts(gens.length))
      setYouComActivity([])
      userSelectedRef.current = false

      let g = startGen
      await loadGenerationInstant(g)

      // Loop from start generation until completion.
      while (mounted) {
        if (token !== runTokenRef.current) throw new Error('ABORTED')

        // Intro (show population)
        await waitBase(BASE_MS.generationIntro, token)

        // Validation
        await validateGenerationSequential(g)

        // Post-validation: show results
        await waitBase(BASE_MS.showResults, token)

        fire('onGenerationComplete', { generation: g })

        // You.com
        await youcomPhase(g)

        if (g >= gens.length - 1) break

        // Mutation to next generation
        await mutateToNextGeneration(g + 1)
        g += 1
      }

      if (token === runTokenRef.current) {
        setCurrentPhase('complete')
        setValidatingStrategyIndex(null)
        setTestingEpisodeIndex(null)
      }
    }

    run().catch((err) => {
      if (String(err?.message ?? err) === 'ABORTED') return
      // Best-effort: stop playback on unexpected errors.
      console.error('useEvolutionPlayback error:', err)
      setIsPlaying(false)
    })

    return () => {
      mounted = false
      // Abort any in-flight waits in StrictMode (mount/unmount) and on unmount.
      runTokenRef.current += 1
    }
    // Intentionally do not depend on isPlaying/playbackSpeed; the runner uses refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evolutionData, playbackSeed, waitBase])

  return {
    currentGeneration,
    currentPhase,
    validatingStrategyIndex,
    testingEpisodeIndex,
    isPlaying,
    playbackSpeed,
    strategies,
    selectedStrategy,
    youComActivity,
    apiCosts,
    play,
    pause,
    setSpeed,
    selectStrategy,
    nextGeneration,
    reset,
  }
}
