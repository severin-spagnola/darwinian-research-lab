# Darwin Evolution Viewer

Minimal web viewer for browsing Darwin evolution runs and visualizing strategy graphs.

## Features

- **Start New Runs**: Form-based Darwin run configuration
- **Browse Runs**: List all evolution runs with summaries
- **Live Progress**: Real-time SSE streaming with:
  - Event log (auto-scrolling with pause option)
  - Progress bar (evaluations completed)
  - Current generation and best fitness
  - Kill statistics histogram
  - LLM budget tracking
- **Run Details**: View summaries, lineage, and top strategies
- **Graph Visualization**: Interactive react-flow visualization
- **Strategy Inspection**: Evaluation results, metrics, failure labels
- **Patch Viewing**: Mutation operations applied to strategies

## Setup

Install dependencies:

```bash
cd frontend
npm install
```

## Running

1. Start the FastAPI backend (from project root):

```bash
cd backend_api
python main.py
```

Backend runs on `http://localhost:8050`

2. Start the frontend dev server:

```bash
cd frontend
npm run dev
```

Frontend runs on `http://localhost:5173`

3. Open browser to `http://localhost:5173`

## Pages

- `/` - List all evolution runs with "+ New Run" button
- `/new-run` - Form to configure and start a new Darwin run
- `/runs/:runId` - Run details with live progress (if running) or results
- `/runs/:runId/strategy/:graphId` - Strategy graph visualization and evaluation

## Tech Stack

- React 18
- React Router 6
- React Flow 11 (graph visualization)
- Tailwind CSS
- Vite
- Axios (API client)

## API Endpoints

The frontend consumes these FastAPI endpoints:

- `GET /api/runs` - List all runs
- `GET /api/runs/:runId` - Get run details
- `GET /api/runs/:runId/lineage` - Get lineage
- `GET /api/runs/:runId/graphs/:graphId` - Get strategy graph
- `GET /api/runs/:runId/evals/:graphId` - Get evaluation
- `POST /api/run` - Start a new run
- `GET /api/run/:runId/events` - SSE stream for run progress

### Helper endpoints
- `POST /api/presence/heartbeat`, `GET /api/presence/history`, `GET /api/repos/context` - placeholder responses for
  workspace tooling that polls `localhost:8050/api`.
- `GET /api/conflict-signals` and `/api/conflict-signals/active` - return empty lists so external monitors can poll without
  hitting 404s.
- `GET /api/debug/requests` and `/api/debug/errors` - expose the most recent requests/errors captured by the backend.

## Notes

- This is a viewer-first implementation (no editing yet)
- No drag/drop graph editing
- No mutation buttons in UI initially
- Just run + browse + view
