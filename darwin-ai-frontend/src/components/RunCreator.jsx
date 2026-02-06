import { useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Loader2, Sparkles } from 'lucide-react'

const MotionDiv = motion.div

export default function RunCreator({ onRunCreated, demoMode = true }) {
  const [prompt, setPrompt] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState(null)

  // Load Gap & Go prompt as default
  const loadGapAndGo = () => {
    setPrompt(`# Gap & Go Momentum Strategy

Create a gap-and-go momentum trading strategy:

**Universe:** TSLA, NVDA, AAPL, AMD, COIN, PLTR, META, MSFT

**Core Logic:**
1. Gap Detection: Compare market open (9:30 AM) to previous close
2. Entry: Gap up ≥2%, enter on 3rd consecutive green 5-min candle
3. Volume confirmation: Entry candle volume > 20-period average
4. RSI filter: RSI(14) between 50-70 (not overbought)

**Exit Rules:**
- Profit target: 2.5% gain from entry
- Stop loss: 1% below entry
- Time stop: Close after 60 minutes if neither target hit

**Time Window:** Only trade 9:30 AM - 11:00 AM ET

**Risk Management:**
- Max 1 position per ticker per day
- Only enter if ATR(14) > 1.5 (sufficient volatility)`)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!prompt.trim()) {
      setError('Please enter a strategy prompt')
      return
    }

    setIsCreating(true)
    setError(null)

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          seed_prompt: prompt,
          universe: {
            type: 'explicit',
            symbols: ['TSLA', 'NVDA', 'AAPL', 'AMD', 'COIN']
          },
          time_config: {
            timeframe: '5m',
            lookback_days: 90,
            date_range: {
              start: '2024-10-01',
              end: '2025-01-31'
            }
          },
          generations: 2,
          survivors_per_gen: 3,
          children_per_survivor: 2,
          phase3_config: {
            n_episodes: 5,
            min_months: 1,
            max_months: 2,
            sampling_mode: 'uniform_random'
          },
          demo_mode: demoMode
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        throw new Error(errorData?.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()

      if (onRunCreated) {
        onRunCreated(data.run_id)
      }

      setPrompt('')
      setIsCreating(false)
    } catch (err) {
      console.error('Failed to create run:', err)
      setError(err.message || 'Failed to create run. Check backend connection.')
      setIsCreating(false)
    }
  }

  return (
    <MotionDiv
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-4xl mx-auto p-6"
    >
      <div className="bg-panel border border-border rounded-2xl p-6 shadow-lg">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-primary-500/10 rounded-lg">
            <Sparkles className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-text">
              Create Darwin Run
            </h2>
            <p className="text-sm text-text-muted">
              Describe your strategy and let Darwin evolve it
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-text">
                Strategy Prompt
              </label>
              <button
                type="button"
                onClick={loadGapAndGo}
                className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
              >
                Load Gap & Go Template
              </button>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your trading strategy in natural language..."
              className="w-full h-64 px-4 py-3 bg-bg border border-border rounded-xl text-text placeholder:text-text-subtle focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none font-mono text-sm"
              disabled={isCreating}
            />
          </div>

          {error && (
            <div className="p-4 bg-error-500/10 border border-error-500/30 rounded-xl">
              <p className="text-sm text-error-300">{error}</p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isCreating || !prompt.trim()}
              className="flex items-center gap-2 px-6 py-3 bg-primary-500 hover:bg-primary-600 disabled:bg-primary-500/50 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-colors"
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating Run...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Evolution
                </>
              )}
            </button>

            {isCreating && (
              <p className="text-sm text-text-muted">
                {demoMode
                  ? 'Loading pre-computed results...'
                  : 'This will take 10-15 minutes. Darwin is compiling strategies, fetching data, and running Phase 3 validation...'}
              </p>
            )}
          </div>

          <div className="p-4 bg-info-500/10 border border-info-500/30 rounded-xl">
            <p className="text-xs text-info-300">
              <strong>Configuration:</strong> 2 generations • 3 survivors per gen • 5 Phase 3 episodes with event tagging • 5m timeframe • Oct 2024 - Jan 2025
            </p>
          </div>
        </form>
      </div>
    </MotionDiv>
  )
}
