# Frontend Setup Guide

Complete guide for setting up and running the Darwin Evolution web viewer.

## Prerequisites

- Node.js 18+ and npm
- Python 3.11+ (for backend)
- Darwin evolution runs in `results/runs/` directory (run `demo_darwin.py` first)

## Installation

### 1. Install Backend Dependencies

```bash
# From project root
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

This installs:
- React 18
- React Router 6
- React Flow 11 (graph visualization)
- Tailwind CSS
- Vite (dev server)
- Axios (API client)

## Running the Application

### Terminal 1: Start Backend

```bash
cd backend_api
python main.py
```

Or use the start script:

```bash
cd backend_api
./start.sh
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8050
```

Backend is now running at `http://localhost:8050`

### Terminal 2: Start Frontend

```bash
cd frontend
npm run dev
```

You should see:
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

Frontend is now running at `http://localhost:5173`

### 3. Open Browser

Navigate to `http://localhost:5173`

## Application Structure

### Backend API (http://localhost:8050)

- `GET /api/runs` - List all evolution runs
- `GET /api/runs/:runId` - Get run details
- `GET /api/runs/:runId/lineage` - Get lineage tree
- `GET /api/runs/:runId/graphs/:graphId` - Get strategy graph JSON
- `GET /api/runs/:runId/evals/:graphId` - Get evaluation results
- `POST /api/run` - Start a new Darwin run (exposed in `/new-run` page)
- `GET /api/run/:runId/events` - SSE stream for real-time run progress
- `GET /api/health` - Health check

### Frontend Pages

1. **Runs List (`/`)**
   - Shows all evolution runs
   - Displays run ID, best fitness, total evaluations
   - "+ New Run" button to start new evolution
   - Click to view run details

2. **New Run (`/new-run`)**
   - Natural language strategy textarea
   - Universe configuration (symbols + presets)
   - Timeframe and date range selection
   - Evolution parameters (depth, branching, survivors, max evals)
   - Robust mode toggle
   - Start evolution button (redirects to run detail page)

3. **Run Detail (`/runs/:runId`)**
   - **Live Progress (if running):**
     - Real-time event log with SSE streaming
     - Progress bar (evals completed / max)
     - Current generation and best fitness
     - Kill statistics histogram
     - Auto-scroll with pause option
   - **Results (if complete):**
     - Run summary (evaluations, best fitness, config)
     - Top strategies list (click to view details)
     - Kill statistics (reasons for strategy elimination)
     - Lineage tree (parent → child relationships)

4. **Strategy Detail (`/runs/:runId/strategy/:graphId`)**
   - Evaluation metrics (fitness, decision, kill reasons)
   - Performance metrics (train/holdout return, Sharpe)
   - Interactive graph visualization (react-flow)
   - Node details (type, parameters, inputs)
   - Patch info (mutation operations applied)

## Graph Visualization

The strategy graph viewer uses react-flow with:

- **Node Colors** (by category):
  - Blue: Data sources
  - Purple: Indicators
  - Cyan: Transforms
  - Amber: Signals
  - Red: Risk management
  - Green: Position sizing
  - Pink: Strategy nodes
  - Gray: Other

- **Interactive Features**:
  - Pan and zoom
  - Minimap navigation
  - Auto-layout on load
  - Edge labels showing input connections

## Development

### Hot Reload

Both backend and frontend support hot reload:

- Backend: FastAPI auto-reloads on file changes
- Frontend: Vite HMR for instant updates

### Build for Production

```bash
cd frontend
npm run build
```

This creates an optimized build in `frontend/dist/`

To preview production build:

```bash
npm run preview
```

## Troubleshooting

### Backend won't start

**Error: `ModuleNotFoundError: No module named 'fastapi'`**

Solution: Install backend dependencies
```bash
pip install -r requirements.txt
```

**Error: `POLYGON_API_KEY not set`**

Solution: Create `.env` file in project root with your API keys
```bash
POLYGON_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Frontend won't start

**Error: `command not found: npm`**

Solution: Install Node.js 18+ from https://nodejs.org

**Error: `Cannot find module 'react'`**

Solution: Install frontend dependencies
```bash
cd frontend
npm install
```

### No runs showing

**Empty list on homepage**

Solution: Run Darwin evolution first to generate data
```bash
python demo_darwin.py
```

This creates run directories in `results/runs/`

### Port already in use

**Backend Error: `Address already in use: 8050`**

Solution: Kill existing process or change port in `backend_api/main.py`
```bash
# Find and kill process on port 8050
lsof -ti:8050 | xargs kill -9

# Or change port in main.py
uvicorn.run(app, host="0.0.0.0", port=8001)
```

**Frontend Error: `Port 5173 is in use`**

Solution: Kill existing process or Vite will auto-increment port
```bash
lsof -ti:5173 | xargs kill -9
```

### CORS errors

**Error: `Access-Control-Allow-Origin`**

This should not happen due to backend CORS middleware. If it does:

1. Verify backend is running on port 8050
2. Check `backend_api/main.py` CORS configuration includes `http://localhost:5173`
3. Clear browser cache and reload

### Graph not rendering

**Blank graph viewer**

Possible causes:
1. Strategy has no nodes (check JSON)
2. React Flow CSS not loaded (check console for 404s)
3. Invalid node structure

Check browser console for errors.

## Next Steps

### Start a Run from UI (Future)

Currently runs must be started via Python scripts. Future versions will support:
- Run configuration form
- Real-time progress monitoring
- SSE event streaming display

### Graph Editing (Future)

Currently the viewer is read-only. Future versions will support:
- Drag-and-drop node editing
- Add/remove nodes
- Mutation buttons
- Parameter tuning

## API Testing

Test backend endpoints directly:

```bash
# List runs
curl http://localhost:8050/api/runs

# Get run details
curl http://localhost:8050/api/runs/20250128_123456

# Health check
curl http://localhost:8050/api/health
```

## File Locations

- Backend: `backend_api/main.py`
- Frontend source: `frontend/src/`
- Run artifacts: `results/runs/<run_id>/`
- LLM cache: `results/llm_cache/`
- LLM logs: `results/llm_logs/`

## Support

For issues:
1. Check this troubleshooting guide
2. Review browser console for errors
3. Check backend logs in terminal
4. Verify run artifacts exist in `results/runs/`
