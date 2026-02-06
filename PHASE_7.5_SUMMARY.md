# Phase 7.5 Summary: Live Progress & New Run Form

Phase 7.5 adds real-time monitoring and run creation capabilities to the Darwin Evolution Viewer.

## Implemented Features

### 1. Standardized SSE Event Schema

**Backend** ([backend_api/main.py](backend_api/main.py)):
- Structured event emission with `type` field
- Event types:
  - `run_started` - Evolution begins
  - `log` - Generic log messages
  - `status` - Status updates with progress data
  - `run_finished` - Evolution complete
  - `error` - Errors during execution
- Progress tracking: `evals_completed`, `max_total_evals`, `current_generation`, `best_fitness`, `kill_stats`
- Events flushed as they occur (1-second polling)

**Event Structure:**
```json
{
  "type": "status",
  "timestamp": "2025-01-28T12:34:56.789Z",
  "status": "running",
  "progress": {
    "evals_completed": 15,
    "max_total_evals": 50,
    "current_generation": 1,
    "best_fitness": 0.456,
    "kill_stats": {
      "negative_fitness": 3,
      "severe_holdout_degradation": 2
    }
  }
}
```

### 2. Live Progress Component

**Frontend** ([frontend/src/components/LiveProgress.jsx](frontend/src/components/LiveProgress.jsx)):
- Native `EventSource` SSE subscription
- Real-time event log with timestamps
- Progress bar (evaluations completed / max)
- Current generation display
- Best fitness tracking
- Kill statistics histogram (top 6 reasons)
- Auto-scroll with pause/resume toggle
- Color-coded event types (error=red, success=green, log=gray, info=blue)
- Status badge (connecting, running, completed, failed)
- Auto-cleanup on unmount

### 3. Run Detail Integration

**Updated** ([frontend/src/pages/RunDetail.jsx](frontend/src/pages/RunDetail.jsx)):
- Detects if run is in progress (no summary file yet)
- Shows live progress component for running jobs
- Automatically reloads data when run completes
- Falls back to results view for completed runs

### 4. New Run Form

**Frontend** ([frontend/src/pages/NewRun.jsx](frontend/src/pages/NewRun.jsx)):

#### Form Fields:
- **Natural Language Strategy** - Multiline textarea with example strategy
- **Universe Symbols** - Comma-separated input with presets:
  - FAANG (AAPL, AMZN, META, GOOG, NFLX)
  - Tech Giants (AAPL, MSFT, GOOG, AMZN)
  - S&P 500 Top 5 (AAPL, MSFT, GOOG, AMZN, NVDA)
  - Single (AAPL)
  - Single (SPY)
- **Timeframe** - Dropdown (1m, 5m, 15m, 1h, 1d)
- **Date Range** - Start/end date pickers
- **Evolution Parameters:**
  - Depth (generations): 1-10
  - Branching (children per parent): 1-10
  - Survivors per layer: 1-20
  - Max total evaluations: 10-500
- **Robust Mode** - Checkbox for multi-symbol validation

#### Behavior:
- Form validation (required fields)
- Submitting state with disabled button
- Error display
- Redirects to `/runs/:runId` on success
- Cancel button returns to runs list

### 5. Updated Navigation

**App** ([frontend/src/App.jsx](frontend/src/App.jsx)):
- Clickable header logo (returns to home)
- "+ New Run" button on homepage
- New route: `/new-run`
- Conditional button display (only on homepage)

## API Changes

### Backend Endpoints

No new endpoints - enhanced existing:

- `POST /api/run` - Now fully integrated with frontend form
- `GET /api/run/:runId/events` - Enhanced with structured events and progress tracking

### Event Emission

Added `emit_event()` helper function:
```python
def emit_event(run_id: str, event_type: str, data: Dict[str, Any] = None):
    """Emit a structured event for a run."""
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        **(data or {})
    }
    running_jobs[run_id]["events"].append(event)
```

Added `run_darwin_with_events()` wrapper:
- Wraps `run_darwin()` for future instrumentation
- Currently emits start/end events
- Foundation for deeper integration with Darwin evolution loop

## File Changes

### New Files:
- `frontend/src/components/LiveProgress.jsx` (180 lines) - Live progress component
- `frontend/src/pages/NewRun.jsx` (260 lines) - New run form page
- `PHASE_7.5_SUMMARY.md` (this file)

### Modified Files:
- `backend_api/main.py` - Added event emission, structured progress tracking
- `frontend/src/App.jsx` - Added navigation, routing for /new-run
- `frontend/src/pages/RunDetail.jsx` - Integrated live progress component
- `frontend/README.md` - Updated feature list
- `SETUP_FRONTEND.md` - Updated page descriptions
- `README.md` - Updated Phase 7 roadmap

## Usage

### Starting a New Run

1. Navigate to homepage
2. Click "+ New Run" button
3. Fill in strategy description and parameters
4. Click "Start Evolution"
5. Redirected to live progress page
6. Watch real-time event log and progress updates
7. Page auto-refreshes when complete

### Monitoring Progress

- Event log shows all activity with timestamps
- Progress bar updates as evaluations complete
- Best fitness updates in real-time
- Kill stats show most common failure reasons
- Pause scroll button to inspect specific events
- Status badge shows current state

## Technical Notes

### SSE Implementation

- Native `EventSource` API (browser built-in)
- Automatic reconnection on disconnect
- JSON parsing with error handling
- Clean teardown in `useEffect` cleanup

### Event Flow

1. Frontend calls `POST /api/run`
2. Backend starts Darwin in background task
3. Backend emits events to `running_jobs[run_id]["events"]`
4. Frontend connects to `GET /api/run/:runId/events`
5. SSE endpoint streams new events every second
6. Frontend updates UI in real-time
7. Connection closes when run completes/fails

### State Management

- No global state library needed
- Local component state with React hooks
- `useEffect` for SSE subscription lifecycle
- `useRef` for scroll management and EventSource

## Future Enhancements

Phase 7.5 provides foundation for:
- Budget tracking display (calls, tokens, cost)
- More granular Darwin events (compilation, mutation, evaluation per strategy)
- Pause/resume/cancel run controls
- Real-time graph updates during evolution
- WebSocket alternative to SSE for bidirectional communication

## Limitations

### Current:
- Darwin doesn't emit detailed per-evaluation events yet
- Budget not displayed in live progress (backend tracks it)
- No pause/cancel functionality
- No run history persistence for in-progress jobs (lost on backend restart)

### Not Included (as requested):
- No graph editing in viewer
- No mutation buttons
- No manual strategy creation/modification

## Testing

To test Phase 7.5:

1. Start backend: `cd backend_api && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:5173`
4. Click "+ New Run"
5. Fill form with default values or modify
6. Click "Start Evolution"
7. Observe live progress updates
8. Wait for completion or check another run
9. Verify completed run shows results instead of live progress

## Status

Phase 7.5 complete! All requested features implemented:
- ✅ SSE live progress with event log
- ✅ Progress counters (evals, generation, fitness)
- ✅ Kill label histogram
- ✅ Auto-scroll with pause
- ✅ New run form with presets
- ✅ Robust mode toggle
- ✅ Standardized event schema

Viewer-first approach maintained - no graph editing or mutation buttons yet.
