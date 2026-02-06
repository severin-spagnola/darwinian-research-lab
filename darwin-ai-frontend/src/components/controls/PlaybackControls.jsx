import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { Pause, Play, SkipForward, Timer } from 'lucide-react'

const SPEEDS = [1, 2, 5, 10]
const MotionDiv = motion.div

function clamp(n, min, max) {
  return Math.min(max, Math.max(min, n))
}

function phaseLabel(phase) {
  const p = String(phase ?? '')
  if (p === 'intro') return 'Introducing generation...'
  if (p === 'validation') return 'Validating strategies...'
  if (p === 'youcom') return 'You.com intelligence...'
  if (p === 'mutation') return 'Breeding mutations...'
  if (p === 'complete') return 'Run complete.'
  return '—'
}

export default function PlaybackControls({
  isPlaying,
  onPlayPause,
  playbackSpeed,
  onSpeedChange,
  currentGeneration,
  totalGenerations,
  currentPhase,
  onNextGeneration,
}) {
  const gen = Math.max(0, Math.round(Number(currentGeneration) || 0))
  const total = Math.max(1, Math.round(Number(totalGenerations) || 1))

  const percent = useMemo(() => {
    // Mirror the UX in the spec example: gen 2 / 5 => 40%.
    return clamp((gen / total) * 100, 0, 100)
  }, [gen, total])

  const playTone = isPlaying
    ? 'bg-primary-500/14 text-primary-200 ring-primary-500/25 hover:bg-primary-500/18'
    : 'bg-warning-500/14 text-warning-200 ring-warning-500/25 hover:bg-warning-500/18'

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onPlayPause}
          className={[
            'relative inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition',
            'focus:outline-none focus:ring-2 focus:ring-primary-500/30',
            'ring-1 ring-inset',
            playTone,
          ].join(' ')}
          aria-pressed={isPlaying}
        >
          {isPlaying ? (
            <>
              <Pause className="h-4 w-4" />
              Pause
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Play
            </>
          )}
          {isPlaying ? (
            <MotionDiv
              aria-hidden="true"
              className="absolute -inset-0.5 rounded-[18px] ring-2 ring-primary-500/10"
              animate={{ opacity: [0.3, 0.9, 0.3] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
            />
          ) : null}
        </button>

        <button
          type="button"
          onClick={onNextGeneration}
          disabled={!onNextGeneration}
          className={[
            'inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition',
            'focus:outline-none focus:ring-2 focus:ring-info-500/25',
            'ring-1 ring-inset ring-border/70',
            onNextGeneration ? 'bg-panel-elevated text-text hover:bg-white/5' : 'bg-panel text-text-subtle opacity-60',
          ].join(' ')}
          title="Next generation"
        >
          <SkipForward className="h-4 w-4" />
          Next
        </button>

        <div className="flex items-center gap-2 rounded-2xl bg-panel-elevated p-1 ring-1 ring-inset ring-border/70">
          {SPEEDS.map((s) => {
            const active = Number(playbackSpeed) === s
            return (
              <button
                key={s}
                type="button"
                onClick={() => onSpeedChange?.(s)}
                className={[
                  'rounded-xl px-3 py-2 text-xs font-semibold transition',
                  active
                    ? 'bg-info-500/14 text-info-200 ring-1 ring-inset ring-info-500/25'
                    : 'text-text-muted hover:bg-white/5 hover:text-text',
                ].join(' ')}
                aria-pressed={active}
              >
                {s}x
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex w-full flex-col gap-2 md:w-[420px]">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <div>
            Generation <span className="text-text">{gen}</span> /{' '}
            <span className="text-text">{total}</span>
          </div>
          <div className="inline-flex items-center gap-2">
            <Timer className="h-3.5 w-3.5 text-text-subtle" />
            <span>{phaseLabel(currentPhase)}</span>
          </div>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-panel-elevated ring-1 ring-inset ring-border/70">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary-400 via-info-400 to-primary-300 transition-[width] duration-200"
            style={{ width: `${percent}%` }}
            aria-label={`Progress ${Math.round(percent)}%`}
          />
        </div>
      </div>
    </div>
  )
}

