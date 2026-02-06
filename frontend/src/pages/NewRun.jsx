import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const PRESET_UNIVERSES = {
  'FAANG': ['AAPL', 'AMZN', 'META', 'GOOG', 'NFLX'],
  'Tech Giants': ['AAPL', 'MSFT', 'GOOG', 'AMZN'],
  'S&P 500 Top 5': ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA'],
  'Single (AAPL)': ['AAPL'],
  'Single (SPY)': ['SPY'],
}

function NewRun() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    nl_text: `Trade mean reversion on 5-minute bars.

Entry: Buy when RSI(14) drops below 30 (oversold).
Exit: Sell when RSI rises above 70 (overbought).

Use ATR-based risk management:
- Stop loss: 2x ATR below entry
- Take profit: 3x ATR above entry

Position size: $10,000 per trade
Risk limits: Max 5 trades per day, max 2% daily loss`,
    universe_symbols: ['AAPL'],
    timeframe: '5m',
    start_date: '2024-10-01',
    end_date: '2025-01-01',
    depth: 3,
    branching: 3,
    survivors_per_layer: 5,
    max_total_evals: 50,
    robust_mode: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  function handleChange(e) {
    const { name, value, type, checked } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
  }

  function handleSymbolsChange(e) {
    const symbols = e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
    setFormData(prev => ({ ...prev, universe_symbols: symbols }))
  }

  function handlePresetClick(preset) {
    setFormData(prev => ({ ...prev, universe_symbols: PRESET_UNIVERSES[preset] }))
  }

  function handleNumberChange(e) {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: parseInt(value, 10) }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const result = await api.startRun(formData)
      navigate(`/runs/${result.run_id}`)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Start New Darwin Run</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Natural Language Strategy */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Natural Language Strategy
          </label>
          <textarea
            name="nl_text"
            value={formData.nl_text}
            onChange={handleChange}
            rows={12}
            required
            className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Describe your trading strategy in natural language..."
          />
          <p className="text-xs text-gray-500 mt-2">
            Describe entry/exit rules, risk management, position sizing, etc.
          </p>
        </div>

        {/* Universe & Timeframe */}
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Universe (Symbols)
            </label>
            <input
              type="text"
              value={formData.universe_symbols.join(', ')}
              onChange={handleSymbolsChange}
              className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="AAPL, MSFT, GOOG"
            />
            <div className="flex flex-wrap gap-2 mt-2">
              {Object.keys(PRESET_UNIVERSES).map(preset => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handlePresetClick(preset)}
                  className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Timeframe
              </label>
              <select
                name="timeframe"
                value={formData.timeframe}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="1m">1 minute</option>
                <option value="5m">5 minutes</option>
                <option value="15m">15 minutes</option>
                <option value="1h">1 hour</option>
                <option value="1d">1 day</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Start Date
              </label>
              <input
                type="date"
                name="start_date"
                value={formData.start_date}
                onChange={handleChange}
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                End Date
              </label>
              <input
                type="date"
                name="end_date"
                value={formData.end_date}
                onChange={handleChange}
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Evolution Parameters */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Evolution Parameters</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Depth (Generations)
              </label>
              <input
                type="number"
                name="depth"
                value={formData.depth}
                onChange={handleNumberChange}
                min="1"
                max="10"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Branching (Children per Parent)
              </label>
              <input
                type="number"
                name="branching"
                value={formData.branching}
                onChange={handleNumberChange}
                min="1"
                max="10"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Survivors per Layer
              </label>
              <input
                type="number"
                name="survivors_per_layer"
                value={formData.survivors_per_layer}
                onChange={handleNumberChange}
                min="1"
                max="20"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Max Total Evaluations
              </label>
              <input
                type="number"
                name="max_total_evals"
                value={formData.max_total_evals}
                onChange={handleNumberChange}
                min="10"
                max="500"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="flex items-center">
              <input
                type="checkbox"
                name="robust_mode"
                checked={formData.robust_mode}
                onChange={handleChange}
                className="mr-2"
              />
              <span className="text-sm text-gray-700">
                Robust Mode (multi-symbol validation)
              </span>
            </label>
            <p className="text-xs text-gray-500 mt-1 ml-6">
              Evaluate strategies across all symbols to prevent single-ticker overfitting
            </p>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end space-x-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-6 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Starting...' : 'Start Evolution'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default NewRun
