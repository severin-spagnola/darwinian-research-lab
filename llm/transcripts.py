"""Utilities for storing per-run LLM transcripts."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import config


def _run_transcripts_dir(run_id: str) -> Path:
    path = config.RESULTS_DIR / "runs" / run_id / "llm_transcripts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def record_transcript(
    run_id: Optional[str],
    stage: str,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    raw_response_text: str,
    parsed_json: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    suffix: Optional[str] = None,
    artifact: Optional[str] = None,
    cached: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[Path]:
    if not run_id:
        return None

    llm_dir = _run_transcripts_dir(run_id)
    name = stage
    if suffix:
        name = f"{name}_{suffix}"
    filename = f"{name}.json"
    transcript_path = llm_dir / filename

    payload: Dict[str, Any] = {
        "stage": stage,
        "provider": provider,
        "model": model,
        "artifact": artifact,
        "cached": cached,
        "timestamp": datetime.now().isoformat(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response_text": raw_response_text,
        "parsed_json": parsed_json,
        "error": error,
    }
    if extra:
        payload["extra"] = extra

    with open(transcript_path, "w") as f:
        json.dump(payload, f, indent=2)

    return transcript_path


def list_transcripts(run_id: str) -> List[Dict[str, Any]]:
    llm_dir = config.RESULTS_DIR / "runs" / run_id / "llm_transcripts"
    if not llm_dir.exists():
        return []

    transcripts = []
    for path in sorted(llm_dir.iterdir()):
        if path.is_file() and path.suffix == ".json":
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                continue
            transcripts.append({
                "filename": path.name,
                "stage": data.get("stage"),
                "timestamp": data.get("timestamp"),
                "provider": data.get("provider"),
                "artifact": data.get("artifact"),
                "cached": data.get("cached", False),
            })
    return transcripts


def read_transcript(run_id: str, filename: str) -> Optional[Dict[str, Any]]:
    llm_dir = config.RESULTS_DIR / "runs" / run_id / "llm_transcripts"
    if not llm_dir.exists():
        return None

    safe_name = Path(filename).name
    transcript_path = llm_dir / safe_name
    if not transcript_path.exists():
        return None

    with open(transcript_path) as f:
        return json.load(f)
