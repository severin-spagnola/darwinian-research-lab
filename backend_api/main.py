"""FastAPI backend for Darwin evolution viewer."""

from collections import deque, Counter
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
from pathlib import Path
from datetime import datetime
import logging
import traceback

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from graph.schema import UniverseSpec, TimeConfig, DateRange
from data.polygon_client import PolygonClient
from evolution.darwin import run_darwin
from validation.evaluation import Phase3Config
from graph.gene_pool import get_registry
from graph.gene_pool import get_registry
from llm.cache import get_budget, reset_budget, get_global_budget, LLMBudget
from llm.transcripts import list_transcripts as list_llm_transcripts, read_transcript as read_llm_transcript
import hashlib
from starlette.exceptions import HTTPException as StarletteHTTPException
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REQUEST_LOG_SIZE = 250
ERROR_LOG_SIZE = 50
request_history = deque(maxlen=REQUEST_LOG_SIZE)
error_history = deque(maxlen=ERROR_LOG_SIZE)


def _record_error(entry: Dict[str, Any]):
    """Keep a bounded history of recent backend errors."""
    error_history.append(entry)


app = FastAPI(title="Darwin Evolution API", version="1.0.0")

# Seed demo fixtures into results directory on startup
import shutil
_demo_fixtures_dir = Path(__file__).parent / "demo_fixtures"
_demo_target = config.RESULTS_DIR / "runs" / "demo_gap_and_go"
if _demo_fixtures_dir.exists() and not _demo_target.exists():
    _demo_target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_demo_fixtures_dir / "demo_gap_and_go", _demo_target, dirs_exist_ok=True)
    logger.info("Seeded demo_gap_and_go fixture into results directory")

# CORS middleware for local development and production
# Use allow_origin_regex for wildcard Vercel domains
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_details(request: Request, call_next):
    """Record metadata about every request (errors logged at INFO)."""
    start_time = time.monotonic()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration = time.monotonic() - start_time
        status_code = response.status_code if response else status.HTTP_500_INTERNAL_SERVER_ERROR
        client_host = request.client.host if request.client else "unknown"
        query_string = f"?{request.url.query}" if request.url.query else ""
        record = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query": request.url.query,
            "status_code": status_code,
            "duration": round(duration, 3),
            "client": client_host,
            "user_agent": request.headers.get("user-agent"),
        }
        request_history.append(record)
        if status_code >= 400:
            logger.info(
                f"HTTP {status_code} {request.method} {request.url.path}{query_string} "
                f"from {client_host} (UA={record['user_agent']}) in {duration:.3f}s"
            )

# Track running jobs with event queues
running_jobs: Dict[str, Dict[str, Any]] = {}


def _get_run_dir(run_id: str) -> Path:
    run_dir = config.RESULTS_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

FINGERPRINT_NODE_DIMENSIONS = sorted(get_registry().get_all_types())[:18]


def emit_event(run_id: str, event_type: str, data: Dict[str, Any] = None):
    """Emit a structured event for a run."""
    if run_id not in running_jobs:
        return

    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        **(data or {})
    }
    running_jobs[run_id]["events"].append(event)


class RunRequest(BaseModel):
    """Request to start a Darwin run."""
    nl_text: str
    universe_symbols: List[str]
    timeframe: str
    start_date: str
    end_date: str
    depth: int = 3
    branching: int = 3
    survivors_per_layer: int = 5
    max_total_evals: int = 50
    robust_mode: bool = False


@app.get("/api/runs")
async def list_runs():
    """List all run IDs and their summaries."""
    runs_dir = config.RESULTS_DIR / "runs"

    if not runs_dir.exists():
        return {"runs": []}

    runs = []
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if run_dir.is_dir():
            summary_file = run_dir / "summary.json"
            if summary_file.exists():
                with open(summary_file) as f:
                    summary = json.load(f)
                runs.append({
                    "run_id": run_dir.name,
                    "summary": summary
                })

    return {"runs": runs}


class CreateRunRequest(BaseModel):
    seed_prompt: str
    universe: Dict[str, Any]
    time_config: Dict[str, Any]
    generations: int = 2
    survivors_per_gen: int = 3
    children_per_survivor: int = 2
    phase3_config: Optional[Dict[str, Any]] = None
    demo_mode: bool = False


def _run_darwin_task(
    seed_prompt: str,
    universe: UniverseSpec,
    time_config: TimeConfig,
    depth: int,
    branching: int,
    survivors_per_layer: int,
    phase3_config: Optional[Phase3Config],
    run_id: str,
):
    """Background task: fetch market data, then run Darwin."""
    try:
        logger.info(f"[{run_id}] Fetching market data...")
        client = PolygonClient()
        symbols = universe.resolve_symbols()
        dr = time_config.date_range

        # Fetch data for first symbol (Darwin operates per-symbol)
        data = None
        for sym in symbols:
            try:
                df = client.get_bars(
                    symbol=sym,
                    timeframe=time_config.timeframe,
                    start=dr.start,
                    end=dr.end,
                )
                if df is not None and not df.empty:
                    logger.info(f"[{run_id}] Fetched {len(df)} bars for {sym}")
                    if data is None:
                        data = df  # Use first successful symbol
                        logger.info(f"[{run_id}] Using {sym} as primary data source")
            except Exception as e:
                logger.warning(f"[{run_id}] Failed to fetch {sym}: {e}")

        if data is None:
            logger.error(f"[{run_id}] No data fetched for any symbol!")
            return

        logger.info(f"[{run_id}] Starting Darwin evolution with {len(data)} bars...")
        summary = run_darwin(
            data=data,
            universe=universe,
            time_config=time_config,
            nl_text=seed_prompt,
            depth=depth,
            branching=branching,
            survivors_per_layer=survivors_per_layer,
            phase3_config=phase3_config,
            run_id=run_id,
            rescue_mode=True,
        )
        logger.info(f"[{run_id}] Darwin run complete!")

    except Exception as e:
        logger.error(f"[{run_id}] Darwin run failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


@app.post("/api/runs")
async def create_run(request: CreateRunRequest, background_tasks: BackgroundTasks):
    """Create a new Darwin evolution run in the background."""
    # Demo mode: return pre-baked Gap & Go results instantly
    if request.demo_mode:
        demo_dir = config.RESULTS_DIR / "runs" / "demo_gap_and_go"
        if demo_dir.exists():
            return {
                "run_id": "demo_gap_and_go",
                "status": "completed",
                "message": "Demo run loaded with pre-computed Gap & Go results."
            }
        else:
            raise HTTPException(status_code=404, detail="Demo data not found. Run the Gap & Go strategy locally first.")

    try:
        # Parse config
        universe = UniverseSpec(**request.universe)

        # Handle time_config with date_range
        time_dict = request.time_config.copy()
        if 'date_range' in time_dict and time_dict['date_range']:
            dr = time_dict['date_range']
            time_dict['date_range'] = DateRange(
                start=dr['start'][:10] if isinstance(dr['start'], str) else dr['start'].strftime('%Y-%m-%d'),
                end=dr['end'][:10] if isinstance(dr['end'], str) else dr['end'].strftime('%Y-%m-%d')
            )
        time_config = TimeConfig(**time_dict)

        # Parse phase3_config if provided
        phase3_config = None
        if request.phase3_config:
            phase3_config = Phase3Config(**request.phase3_config)

        # Generate run ID
        import uuid
        run_id = f"run_{uuid.uuid4().hex[:8]}"

        # Start Darwin in background (maps frontend names to run_darwin params)
        background_tasks.add_task(
            _run_darwin_task,
            seed_prompt=request.seed_prompt,
            universe=universe,
            time_config=time_config,
            depth=request.generations,
            branching=request.children_per_survivor,
            survivors_per_layer=request.survivors_per_gen,
            phase3_config=phase3_config,
            run_id=run_id,
        )

        return {
            "run_id": run_id,
            "status": "started",
            "message": f"Darwin run {run_id} started in background. Check /api/runs/{run_id} for progress."
        }

    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get run summary and config."""
    run_dir = config.RESULTS_DIR / "runs" / run_id

    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    summary_file = run_dir / "summary.json"
    config_file = run_dir / "run_config.json"

    result = {"run_id": run_id}

    if summary_file.exists():
        with open(summary_file) as f:
            result["summary"] = json.load(f)

    if config_file.exists():
        with open(config_file) as f:
            result["config"] = json.load(f)

    return result


@app.get("/api/runs/{run_id}/playback")
async def get_run_playback(run_id: str):
    """Return run data in the frontend playback format.

    Reconstructs the {generations, lineage} structure the frontend
    useEvolutionPlayback hook expects from stored graphs + evals.
    """
    run_dir = config.RESULTS_DIR / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    graphs_dir = run_dir / "graphs"
    evals_dir = run_dir / "evals"
    summary_file = run_dir / "summary.json"

    # Load all graphs and evals
    strategies = []
    if graphs_dir.exists():
        for gf in sorted(graphs_dir.glob("*.json")):
            graph_id = gf.stem
            graph = json.loads(gf.read_text())

            # Load matching eval
            eval_file = evals_dir / f"{graph_id}.json"
            eval_data = json.loads(eval_file.read_text()) if eval_file.exists() else {}

            # Determine state from eval decision
            decision = eval_data.get("decision", "survive")
            if decision == "survive":
                state = "alive"
            elif decision == "kill":
                state = "dead"
            else:
                state = "alive"

            # Build results in mock-compatible format
            val_report = eval_data.get("validation_report", {})
            fitness = eval_data.get("fitness", val_report.get("fitness", 0))
            train = val_report.get("train_metrics", {})
            holdout = val_report.get("holdout_metrics", {})
            penalties = val_report.get("penalties", {})
            failures = val_report.get("failure_labels", [])

            results = {
                "phase3": {
                    "aggregated_fitness": fitness,
                    "median_fitness": fitness,
                    "penalties": penalties,
                    "regime_coverage": {
                        "unique_regimes": 1,
                        "years_covered": 0.33,
                        "per_regime_fitness": {},
                    },
                    "episodes": [
                        {
                            "label": "full_period",
                            "start_ts": graph.get("time", {}).get("date_range", {}).get("start", "2024-10-01"),
                            "fitness": fitness,
                            "tags": {
                                "trend": "bull" if holdout.get("return_pct", 0) > 0 else "bear",
                                "vol_bucket": "medium",
                                "chop_bucket": "medium",
                                "drawdown_state": "normal",
                            },
                            "difficulty": 0.5,
                            "debug_stats": {
                                "return_pct": holdout.get("return_pct", 0),
                                "sharpe": holdout.get("sharpe", 0),
                                "max_dd_pct": holdout.get("max_dd_pct", 0),
                                "trades": holdout.get("trades", 0),
                                "win_rate": holdout.get("win_rate", 0),
                            },
                        }
                    ],
                },
                "red_verdict": {
                    "verdict": "SURVIVE" if decision == "survive" else "KILL",
                    "failures": failures,
                    "next_action": "breed" if decision == "survive" else "discard",
                },
                "fitness": fitness,
            }

            # Ensure graph has metadata.generation
            if "metadata" not in graph:
                graph["metadata"] = {}
            if "generation" not in graph["metadata"]:
                graph["metadata"]["generation"] = 0

            strategies.append({
                "id": graph.get("graph_id", graph_id),
                "graph": graph,
                "results": results,
                "state": state,
            })

    # Mark top strategy as elite
    if strategies:
        strategies.sort(key=lambda s: s["results"].get("fitness", 0), reverse=True)
        strategies[0]["state"] = "elite"

    # Build generations array (group by metadata.generation)
    gen_map = {}
    for s in strategies:
        gen = s["graph"].get("metadata", {}).get("generation", 0)
        gen_map.setdefault(gen, []).append(s)

    max_gen = max(gen_map.keys()) if gen_map else 0
    generations = [gen_map.get(g, []) for g in range(max_gen + 1)]

    # Build lineage
    lineage = {"roots": [], "edges": []}
    for s in strategies:
        parent = s["graph"].get("metadata", {}).get("parent_graph")
        if parent:
            lineage["edges"].append({"parent": parent, "child": s["id"]})
        else:
            lineage["roots"].append(s["id"])

    # Load summary for stats
    summary = {}
    if summary_file.exists():
        summary = json.loads(summary_file.read_text())

    return {
        "run_id": run_id,
        "generations": generations,
        "lineage": lineage,
        "champion": strategies[0] if strategies else None,
        "stats": {
            "total_strategies": len(strategies),
            "total_survivors": sum(1 for s in strategies if s["state"] in ("alive", "elite")),
            "survival_rate": sum(1 for s in strategies if s["state"] in ("alive", "elite")) / max(len(strategies), 1),
            "best_fitness": summary.get("best_fitness", 0),
        },
    }


@app.get("/api/runs/{run_id}/lineage")
async def get_lineage(run_id: str):
    """Get lineage for a run."""
    run_dir = config.RESULTS_DIR / "runs" / run_id
    lineage_file = run_dir / "lineage.jsonl"

    if not lineage_file.exists():
        return {"lineage": []}

    lineage = []
    with open(lineage_file) as f:
        for line in f:
            if line.strip():
                lineage.append(json.loads(line))

    return {"lineage": lineage}


@app.get("/api/runs/{run_id}/lineage_graph")
async def get_lineage_graph(run_id: str):
    """Get lineage graph metadata (nodes + edges + best strategy)."""
    run_dir = config.RESULTS_DIR / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    result = _build_lineage_graph(run_dir)
    return result


def _load_eval_metadata(run_dir: Path, graph_id: str):
    eval_file = run_dir / "evals" / f"{graph_id}.json"
    if not eval_file.exists():
        return {}

    try:
        with open(eval_file) as f:
            data = json.load(f)
        return {
            "fitness": data.get("fitness"),
            "decision": data.get("decision"),
            "graph_id": graph_id,
        }
    except Exception:
        return {}


def _read_lineage_entries(run_dir: Path):
    lineage_path = run_dir / "lineage.jsonl"
    if not lineage_path.exists():
        return []

    entries = []
    with open(lineage_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed lineage entry")
    return entries


def _build_lineage_graph(run_dir: Path):
    entries = _read_lineage_entries(run_dir)

    graph_ids = set()
    parents = set()
    children = set()
    adjacency = defaultdict(list)
    child_gen = {}

    for entry in entries:
        parent_id = entry.get("parent_id")
        child_id = entry.get("child_id")
        depth = entry.get("depth")
        if parent_id:
            graph_ids.add(parent_id)
            parents.add(parent_id)
        if child_id:
            graph_ids.add(child_id)
            children.add(child_id)
        if parent_id and child_id:
            adjacency[parent_id].append(child_id)
            generation = depth if isinstance(depth, int) else None
            if generation is not None:
                child_gen[child_id] = generation

    graphs_dir = run_dir / "graphs"
    if graphs_dir.exists():
        graph_ids.update(p.stem for p in graphs_dir.glob("*.json"))

    generation_map = {}
    roots = list(graph_ids - children)
    queue = deque()
    for root_id in roots:
        generation_map[root_id] = 0
        queue.append(root_id)

    while queue:
        node = queue.popleft()
        base_gen = generation_map.get(node, 0)
        for child in adjacency.get(node, []):
            child_generation = max(child_gen.get(child, base_gen + 1), base_gen + 1)
            if child not in generation_map or child_generation < generation_map[child]:
                generation_map[child] = child_generation
            if child not in queue:
                queue.append(child)

    # Ensure adam-like nodes default to zero
    for gid in graph_ids:
        generation_map.setdefault(gid, 0)

    nodes = []
    for graph_id in sorted(graph_ids):
        metadata = _load_eval_metadata(run_dir, graph_id)
        nodes.append({
            "id": graph_id,
            "label": graph_id,
            "fitness": metadata.get("fitness"),
            "decision": metadata.get("decision"),
            "generation": generation_map.get(graph_id, 0),
        })

    edges = []
    for parent_id, targets in adjacency.items():
        for target in targets:
            edges.append({
                "source": parent_id,
                "target": target,
                "generation": generation_map.get(target),
            })

    summary_file = run_dir / "summary.json"
    best_id = None
    if summary_file.exists():
        try:
            with open(summary_file) as f:
                summary = json.load(f)
            best_id = summary.get("best_strategy", {}).get("graph_id")
        except Exception:
            pass

    if not best_id and nodes:
        best_fit = max(
            (n for n in nodes if isinstance(n.get("fitness"), (int, float))),
            key=lambda n: (n.get("fitness") or 0),
            default=None,
        )
        best_id = best_fit["id"] if best_fit else nodes[0]["id"]

    return {"nodes": nodes, "edges": edges, "best_id": best_id}


def _build_graph_fingerprint(run_dir: Path, graph_id: str):
    """Build a deterministic fingerprint for a strategy graph."""
    graph_file = run_dir / "graphs" / f"{graph_id}.json"
    if not graph_file.exists():
        raise HTTPException(status_code=404, detail="Graph not found")

    with open(graph_file) as f:
        graph = json.load(f)

    node_type_counts = Counter()
    edge_count = 0
    param_count = 0

    for node in graph.get("nodes", []):
        node_type = node.get("type") or node.get("node_type")
        if node_type:
            node_type_counts[node_type] += 1

        params = node.get("params") or {}
        if isinstance(params, dict):
            param_count += len(params)

        inputs = node.get("inputs") or {}
        edge_count += len(inputs)

    vector = [node_type_counts.get(node_type, 0) for node_type in FINGERPRINT_NODE_DIMENSIONS]
    others = sum(
        count
        for node_type, count in node_type_counts.items()
        if node_type not in FINGERPRINT_NODE_DIMENSIONS
    )
    vector.extend([others, edge_count, param_count])

    dimension_labels = [
        f"count_{node_type}" for node_type in FINGERPRINT_NODE_DIMENSIONS
    ] + ["count_others", "edge_count", "param_count"]

    fingerprint_payload = {
        "graph_id": graph_id,
        "node_type_counts": dict(node_type_counts),
        "edge_count": edge_count,
        "param_count": param_count,
        "vector": vector,
        "labels": dimension_labels,
    }

    fingerprint_hash = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True).encode()
    ).hexdigest()

    return {
        "graph_id": graph_id,
        "node_type_counts": dict(node_type_counts),
        "edge_count": edge_count,
        "param_count": param_count,
        "dimension_labels": dimension_labels,
        "fingerprint_vector": vector,
        "fingerprint_hash": f"sha256:{fingerprint_hash}",
    }


@app.get("/api/runs/{run_id}/graphs/{graph_id}")
async def get_graph(run_id: str, graph_id: str):
    """Get a strategy graph."""
    graph_file = config.RESULTS_DIR / "runs" / run_id / "graphs" / f"{graph_id}.json"

    if not graph_file.exists():
        raise HTTPException(status_code=404, detail="Graph not found")

    with open(graph_file) as f:
        return json.load(f)


@app.get("/api/runs/{run_id}/graphs/{graph_id}/fingerprint")
async def get_graph_fingerprint(run_id: str, graph_id: str):
    """Get a deterministic fingerprint for a strategy."""
    run_dir = config.RESULTS_DIR / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    return _build_graph_fingerprint(run_dir, graph_id)


@app.get("/api/runs/{run_id}/evals/{graph_id}")
async def get_eval(run_id: str, graph_id: str):
    """Get evaluation result for a graph."""
    eval_file = config.RESULTS_DIR / "runs" / run_id / "evals" / f"{graph_id}.json"

    if not eval_file.exists():
        raise HTTPException(status_code=404, detail="Evaluation not found")

    with open(eval_file) as f:
        return json.load(f)


@app.get("/api/runs/{run_id}/phase3/{graph_id}")
async def get_phase3_report(run_id: str, graph_id: str):
    """Get Phase 3 robustness report for a graph."""
    report_file = config.RESULTS_DIR / "runs" / run_id / "phase3_reports" / f"{graph_id}.json"

    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Phase 3 report not found")

    with open(report_file) as f:
        return json.load(f)


# ============================================================================
# Research Pack + Blue Memo + Red Verdict Endpoints
# ============================================================================

@app.post("/api/research/packs")
async def create_research_pack(request: Request):
    """Create a research pack from query or URL.

    Request body: {
        query?: string,
        paper_url?: string,
        title?: string,
        n_results?: number (default 5)
    }

    Returns: { ok: true, pack: ResearchPackSummary }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    query = body.get("query")
    paper_url = body.get("paper_url")
    title = body.get("title")
    n_results = body.get("n_results", 5)

    # Build query from inputs
    if query:
        final_query = query
    elif paper_url:
        final_query = f"algorithmic trading strategies {paper_url}"
    elif title:
        final_query = f"algorithmic trading {title}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one of: query, paper_url, title",
        )

    # Create research pack
    try:
        from research.youcom import create_research_pack
        from research.storage import ResearchStorage

        pack = create_research_pack(final_query, n_results=n_results)
        storage = ResearchStorage()
        storage.save_research_pack(pack)

        return {"ok": True, "pack": pack.model_dump()}

    except ValueError as e:
        # API key missing or validation error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create research pack: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Research pack creation failed")


@app.get("/api/research/packs/{pack_id}")
async def get_research_pack(pack_id: str):
    """Get research pack by ID.

    Returns: { ok: true, pack: ResearchPack }
    """
    from research.storage import ResearchStorage

    storage = ResearchStorage()
    pack = storage.load_research_pack(pack_id)

    if not pack:
        raise HTTPException(status_code=404, detail="Research pack not found")

    return {"ok": True, "pack": pack.model_dump()}


@app.post("/api/research/search")
async def search_youcom(request: Request):
    """Proxy endpoint for You.com searches (keeps API key secret).

    Request body: {
        query: string,
        n_results?: number (default 5)
    }

    Returns: { ok: true, results: [...] }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    query = body.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    n_results = body.get("n_results", 5)

    try:
        from research.youcom import search_with_cache
        sources = search_with_cache(query, n_results=n_results)
        # Convert ResearchSource objects to dicts
        results = [s.model_dump() if hasattr(s, 'model_dump') else s for s in sources]
        return {"ok": True, "results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"You.com search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/api/runs/{run_id}/memos/{graph_id}")
async def get_blue_memo(run_id: str, graph_id: str):
    """Get Blue Memo (self-advocacy) for a graph.

    Returns: { ok: true, memo: BlueMemo }
    """
    from research.storage import ResearchStorage

    storage = ResearchStorage(run_id=run_id)
    memo = storage.load_blue_memo(graph_id)

    if not memo:
        raise HTTPException(status_code=404, detail="Blue Memo not found")

    return {"ok": True, "memo": memo.model_dump()}


@app.get("/api/runs/{run_id}/verdicts/{graph_id}")
async def get_red_verdict(run_id: str, graph_id: str):
    """Get Red Verdict (overseer judgment) for a graph.

    Returns: { ok: true, verdict: RedVerdict }
    """
    from research.storage import ResearchStorage

    storage = ResearchStorage(run_id=run_id)
    verdict = storage.load_red_verdict(graph_id)

    if not verdict:
        raise HTTPException(status_code=404, detail="Red Verdict not found")

    return {"ok": True, "verdict": verdict.model_dump()}


@app.get("/api/runs/{run_id}/llm/list")
async def list_run_llm_transcripts(run_id: str):
    """List stored LLM transcripts for a run."""
    _get_run_dir(run_id)
    transcripts = list_llm_transcripts(run_id)
    return {"transcripts": transcripts}


@app.get("/api/runs/{run_id}/llm/{filename}")
async def get_run_llm_transcript(run_id: str, filename: str):
    """Return a specific LLM transcript file for a run."""
    transcript = read_llm_transcript(run_id, filename)
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return transcript


@app.post("/api/run")
async def start_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Start a Darwin evolution run."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info(f"Received request to start run {run_id}")
    logger.info(f"Request: nl_text length={len(request.nl_text)}, symbols={request.universe_symbols}, "
                f"timeframe={request.timeframe}, dates={request.start_date} to {request.end_date}, "
                f"depth={request.depth}, branching={request.branching}, max_evals={request.max_total_evals}")

    # Initialize job tracking
    running_jobs[run_id] = {
        "status": "starting",
        "events": [],
        "started_at": datetime.now().isoformat(),
    }

    logger.info(f"Initialized job tracking for {run_id}")

    # Start run in background
    background_tasks.add_task(_run_darwin_job, run_id, request)
    logger.info(f"Added background task for {run_id}")

    return {"run_id": run_id, "status": "started"}


def run_darwin_with_events(run_id: str, emit_fn, **darwin_kwargs):
    """Wrapper around run_darwin that emits structured events.

    This is a simplified implementation that emits periodic budget updates.
    A full implementation would require modifying darwin.py to accept callbacks.
    """
    logger.info(f"[{run_id}] run_darwin_with_events called with kwargs: {list(darwin_kwargs.keys())}")

    # Extract run_id_param and rename it to run_id for darwin
    run_id_param = darwin_kwargs.pop('run_id_param', None)
    if run_id_param:
        darwin_kwargs['run_id'] = run_id_param

    # For now, just call run_darwin directly
    # Full event integration would require modifying darwin.py
    emit_fn("log", {"message": "Compiling initial strategy from natural language..."})
    logger.info(f"[{run_id}] Calling run_darwin")

    try:
        result = run_darwin(**darwin_kwargs)
        logger.info(f"[{run_id}] run_darwin returned successfully")
        emit_fn("log", {"message": f"Evolution complete: {result.total_evaluations} evaluations"})
        return result
    except Exception as e:
        logger.error(f"[{run_id}] run_darwin failed: {e}", exc_info=True)
        raise


async def _run_darwin_job(run_id: str, request: RunRequest):
    """Run Darwin evolution in background with structured events."""
    logger.info(f"Starting Darwin job {run_id}")
    logger.info(f"Request params: symbols={request.universe_symbols}, timeframe={request.timeframe}, depth={request.depth}")
    run_dir = _get_run_dir(run_id)
    _persist_budget_snapshot(run_id, run_dir)

    try:
        # Emit run_started event
        running_jobs[run_id]["status"] = "fetching_data"
        emit_event(run_id, "run_started", {
            "depth": request.depth,
            "branching": request.branching,
            "max_total_evals": request.max_total_evals,
            "symbols": request.universe_symbols,
        })
        logger.info(f"[{run_id}] Emitted run_started event")

        # Fetch data
        logger.info(f"[{run_id}] Initializing Polygon client")
        client = PolygonClient()
        data_dict = {}

        for symbol in request.universe_symbols:
            logger.info(f"[{run_id}] Fetching data for {symbol}")
            emit_event(run_id, "log", {"message": f"Fetching {symbol} data..."})

            try:
                data = client.get_bars(
                    symbol=symbol,
                    timeframe=request.timeframe,
                    start=request.start_date,
                    end=request.end_date
                )
                data_dict[symbol] = data
                logger.info(f"[{run_id}] Successfully fetched {len(data)} bars for {symbol}")
                emit_event(run_id, "log", {"message": f"Fetched {len(data)} bars for {symbol}"})
            except Exception as fetch_error:
                logger.error(f"[{run_id}] Failed to fetch data for {symbol}: {fetch_error}")
                raise

        # Use first symbol's data
        data = data_dict[request.universe_symbols[0]]
        logger.info(f"[{run_id}] Using {request.universe_symbols[0]} data for evolution")

        running_jobs[run_id]["status"] = "running"
        running_jobs[run_id]["progress"] = {
            "evals_completed": 0,
            "max_total_evals": request.max_total_evals,
            "current_generation": 0,
            "best_fitness": None,
            "kill_stats": {},
        }

        # Reset budget
        logger.info(f"[{run_id}] Resetting LLM budget")
        reset_budget()

        # Create locked params
        universe = UniverseSpec(type="explicit", symbols=request.universe_symbols)
        time_config = TimeConfig(
            timeframe=request.timeframe,
            date_range=DateRange(start=request.start_date, end=request.end_date)
        )
        logger.info(f"[{run_id}] Created universe and time config")

        # Configure Phase 3 robust evaluation
        phase3_config = None
        if request.robust_mode:
            logger.info(f"[{run_id}] Enabling Phase 3 multi-episode evaluation")
            phase3_config = Phase3Config(
                enabled=True,
                mode="episodes",
                n_episodes=8,  # Test on 8 different time windows
                min_months=6,
                max_months=12,
                min_bars=120,
                sampling_mode="uniform_random",  # Better temporal coverage
                min_trades_per_episode=3,
                regime_penalty_weight=0.3,
                abort_on_all_episode_failures=True,
            )
            emit_event(run_id, "log", {"message": "Phase 3 enabled: 8 episodes, 6-12 months each, uniform sampling"})
        else:
            logger.info(f"[{run_id}] Using Phase 2 train/holdout validation")
            emit_event(run_id, "log", {"message": "Using standard train/holdout validation"})

        # Run Darwin with event callback
        logger.info(f"[{run_id}] Starting Darwin evolution")
        emit_event(run_id, "log", {"message": "Starting Darwin evolution..."})

        summary = run_darwin_with_events(
            run_id=run_id,
            emit_fn=lambda event_type, data: emit_event(run_id, event_type, data),
            data=data,
            universe=universe,
            time_config=time_config,
            nl_text=request.nl_text,
            depth=request.depth,
            branching=request.branching,
            survivors_per_layer=request.survivors_per_layer,
            max_total_evals=request.max_total_evals,
            run_id_param=run_id,  # Pass run_id to darwin
            phase3_config=phase3_config,  # PHASE 3 ACTIVATED! 🚀
        )

        logger.info(f"[{run_id}] Darwin evolution completed. Total evals: {summary.total_evaluations}")

        # Get budget
        budget = get_budget()
        logger.info(f"[{run_id}] Budget: {budget.total_calls} calls, {budget.total_tokens} tokens")

        running_jobs[run_id]["status"] = "completed"
        running_jobs[run_id]["summary"] = {
            "best_fitness": summary.best_strategy.fitness,
            "total_evaluations": summary.total_evaluations,
            "budget": budget.to_dict(),
        }
        emit_event(run_id, "run_finished", {
            "best_fitness": summary.best_strategy.fitness,
            "total_evaluations": summary.total_evaluations,
            "budget": budget.to_dict(),
        })
        logger.info(f"[{run_id}] Job completed successfully. Best fitness: {summary.best_strategy.fitness:.3f}")
        try:
            _persist_budget_snapshot(run_id, run_dir)
        except Exception as persist_err:
            logger.warning(f"[{run_id}] Failed to persist budget snapshot: {persist_err}")

    except Exception as e:
        logger.error(f"[{run_id}] Job failed with error: {e}", exc_info=True)
        running_jobs[run_id]["status"] = "failed"
        running_jobs[run_id]["error"] = str(e)

        # Get full traceback
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"[{run_id}] Full traceback:\n{error_detail}")

        emit_event(run_id, "error", {"message": str(e)})
        try:
            _persist_budget_snapshot(run_id, run_dir)
        except Exception as persist_err:
            logger.warning(f"[{run_id}] Failed to persist budget snapshot on error: {persist_err}")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Log structured info for HTTP errors (including 404s)."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "status_code": exc.status_code,
        "detail": exc.detail,
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "client": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent"),
    }
    _record_error(entry)
    logger.warning(
        f"HTTP {exc.status_code} {request.method} {request.url.path}"
        f"{f'?{request.url.query}' if request.url.query else ''} -> {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for uncaught exceptions to expose stack traces during debugging."""
    tb = traceback.format_exc()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "detail": str(exc),
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "client": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent"),
        "traceback": tb,
    }
    _record_error(entry)
    logger.error(
        f"Unhandled exception during {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def _persist_budget_snapshot(run_id: str, run_dir: Path = None):
    """Write the current LLMBudget to results/runs/<run_id>/budget.json."""
    try:
        if run_dir is None:
            run_dir = _get_run_dir(run_id)
        budget = get_budget().to_dict()
        budget_path = run_dir / "budget.json"
        with open(budget_path, "w") as f:
            json.dump(budget, f, indent=2)
    except Exception as err:
        logger.warning(f"[{run_id}] Failed to persist budget: {err}")


def _read_budget(run_id: str):
    run_dir = _get_run_dir(run_id)
    budget_path = run_dir / "budget.json"
    usage = LLMBudget().to_dict()
    if budget_path.exists():
        try:
            with open(budget_path) as f:
                data = json.load(f)
            usage.update(data)
        except Exception:
            pass

    stage_counts = Counter()
    for transcript in list_llm_transcripts(run_id):
        stage = transcript.get("stage") or "unknown"
        stage_counts[stage] += 1

    usage["by_stage"] = {
        stage: {"count": count}
        for stage, count in stage_counts.items()
    }

    return usage


def _add_event(run_id: str, level: str, message: str):
    """Add event to job."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message
    }
    running_jobs[run_id]["events"].append(event)


@app.get("/api/run/{run_id}/events")
async def stream_events(run_id: str):
    """Stream SSE events for a running job."""
    if run_id not in running_jobs:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_event_idx = 0

        while True:
            job = running_jobs.get(run_id)
            if not job:
                break

            # Send new events
            events = job["events"][last_event_idx:]
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                last_event_idx += 1

            # Send status update with progress
            status_event = {
                "type": "status",
                "status": job["status"],
                "timestamp": datetime.now().isoformat(),
                "progress": job.get("progress", {})
            }
            yield f"data: {json.dumps(status_event)}\n\n"

            # If completed or failed, send final event and close
            if job["status"] in ["completed", "failed"]:
                if "summary" in job:
                    final_event = {
                        "type": "run_finished" if job["status"] == "completed" else "error",
                        "timestamp": datetime.now().isoformat(),
                        **(job["summary"] if job["status"] == "completed" else {"message": job.get("error", "Unknown error")})
                    }
                    yield f"data: {json.dumps(final_event)}\n\n"
                break

            await asyncio.sleep(1)  # Poll every second for better responsiveness

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/presence/heartbeat")
async def presence_heartbeat(
    request: Request,
    workspace_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    device_id: Optional[str] = None,
):
    """Heartbeat stub to satisfy external tooling."""
    logger.debug(
        "Presence heartbeat",
        extra={
            "workspace_id": workspace_id,
            "repo_id": repo_id,
            "device_id": device_id,
            "client": request.client.host if request.client else "unknown",
        },
    )
    return {"status": "ok", "workspace_id": workspace_id, "repo_id": repo_id}


@app.get("/api/presence/history")
async def presence_history(workspace_id: Optional[str] = None, repo_id: Optional[str] = None):
    """Return empty presence history (placeholder)."""
    return {"workspace_id": workspace_id, "repo_id": repo_id, "history": []}


@app.get("/api/repos/context")
async def repos_context(workspace_id: Optional[str] = None, repo_id: Optional[str] = None):
    """Return placeholder repository context."""
    return {
        "workspace_id": workspace_id,
        "repo_id": repo_id,
        "context": {},
    }


@app.get("/api/conflict-signals")
async def conflict_signals(
    workspace_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    device_id: Optional[str] = None,
    fresh_seconds: Optional[int] = None,
):
    """Return placeholder conflict signals."""
    return {
        "workspace_id": workspace_id,
        "repo_id": repo_id,
        "device_id": device_id,
        "fresh_seconds": fresh_seconds,
        "signals": [],
    }


@app.get("/api/conflict-signals/active")
async def conflict_signals_active(
    workspace_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    limit: Optional[int] = 10,
):
    """Return placeholder active conflict signals."""
    return {
        "workspace_id": workspace_id,
        "repo_id": repo_id,
        "limit": limit,
        "active_signals": [],
    }


@app.get("/api/debug/requests")
async def debug_requests():
    """Return recent request metadata (for troubleshooting)."""
    return {"requests": list(request_history)}


@app.get("/api/debug/errors")
async def debug_errors():
    """Return recent error logs (for troubleshooting)."""
    return {"errors": list(error_history)}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/runs/{run_id}/llm/usage")
async def get_run_llm_usage(run_id: str):
    usage = _read_budget(run_id)
    return usage


@app.get("/api/llm/usage")
async def get_global_llm_usage():
    budget = get_global_budget()
    return budget.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
