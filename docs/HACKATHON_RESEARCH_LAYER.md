# Hackathon Research Layer - Backend Guide

**Date:** 2026-02-06
**Status:** Production Ready
**Scope:** Backend only - no frontend changes

---

## Overview

The Research Layer adds three key capabilities to the Darwinian quant research backend:

1. **Research Packs** - Run-level grounding using You.com for algorithmic trading research (citations + assumptions)
2. **Blue Memos** - Per-child self-advocacy artifacts (deterministic, no LLM)
3. **Red Verdicts** - Global overseer judgments with failure scoring (deterministic, no LLM)

All artifacts are deterministic by default and fully cached/mockable for tests.

---

## Environment Setup

### Required Environment Variable

```bash
export YOUCOM_API_KEY="your_youcom_api_key_here"
```

If not set, research pack creation will fail with a 400 error. All other features work without this key.

### Optional Configuration

Add to Phase3Config when launching a Darwin run:

```python
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    # ... existing config ...

    # Research layer (additive - no breaking changes)
    research_pack_id="abc123def456",  # Optional: reference a research pack
    research_budget_per_generation=0,  # Default: 0 (disabled)
    research_on_kill_reasons=["LUCKY_SPIKE", "DRAWDOWN_FAIL"],  # Optional
    generate_memos_verdicts=True,  # Default: True
)
```

---

## Artifact Paths

All artifacts are stored under `results/`:

```
results/
├── research_packs/          # Global (shared across runs)
│   └── {pack_id}.json
├── research_cache/          # You.com API response cache
│   └── {sha256_hash}.json
└── runs/{run_id}/
    ├── blue_memos/          # Per-child self-advocacy
    │   └── {graph_id}.json
    ├── red_verdicts/        # Per-child overseer judgment
    │   └── {graph_id}.json
    └── triggered_research/  # (Optional) Kill-triggered research
        └── {graph_id}.json
```

---

## API Endpoints

### 1. Create Research Pack

**POST** `/api/research/packs`

Request body (JSON):
```json
{
  "query": "mean reversion trading strategies",
  "n_results": 5
}
```

OR:

```json
{
  "paper_url": "https://arxiv.org/abs/1234.5678",
  "n_results": 5
}
```

OR:

```json
{
  "title": "momentum strategies quantitative",
  "n_results": 5
}
```

Response:
```json
{
  "ok": true,
  "pack": {
    "id": "abc123def456",
    "created_at": "2026-02-06T12:00:00",
    "query": "mean reversion trading strategies",
    "provider": "youcom",
    "sources": [
      {
        "title": "Mean Reversion Trading Explained",
        "url": "https://example.com/article",
        "snippet": "Mean reversion strategies assume...",
        "provider_rank": 1,
        "published_date": "2024-01-15"
      }
    ],
    "extracted": {
      "assumptions": [
        "Assumes price returns follow known statistical properties",
        "Assumes trends persist over signal window"
      ],
      "knobs": [
        "Lookback period / window size",
        "Signal threshold levels"
      ],
      "known_failure_modes": [
        "Overfitting to historical patterns",
        "Regime change / non-stationarity"
      ],
      "suggested_tests": [
        "Walk-forward out-of-sample validation",
        "Cross-regime performance evaluation",
        "Parameter sensitivity analysis"
      ]
    },
    "fingerprint": "sha256:abcd1234..."
  }
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8050/api/research/packs \
  -H "Content-Type: application/json" \
  -d '{"query": "momentum trading strategies", "n_results": 5}'
```

---

### 2. Get Research Pack

**GET** `/api/research/packs/{packId}`

Response:
```json
{
  "ok": true,
  "pack": { /* same structure as above */ }
}
```

**cURL Example:**
```bash
curl http://localhost:8050/api/research/packs/abc123def456
```

---

### 3. Get Blue Memo (Self-Advocacy)

**GET** `/api/runs/{runId}/memos/{graphId}`

Response:
```json
{
  "ok": true,
  "memo": {
    "run_id": "20260206_120000",
    "graph_id": "child_gen1_001",
    "parent_graph_id": "adam",
    "generation": 1,
    "mutation_patch_summary": [
      "add_node: RSI",
      "modify_param: sma.period = 20"
    ],
    "claim": "Applied mutations: add_node: RSI; modify_param: sma.period = 20",
    "expected_improvement": [
      "Reduce fitness dispersion across episodes",
      "Better performance during drawdown regimes"
    ],
    "risks": [
      "Increased complexity may reduce robustness",
      "Parameter sensitivity to lookback periods"
    ],
    "created_at": "2026-02-06T12:05:30"
  }
}
```

**cURL Example:**
```bash
curl http://localhost:8050/api/runs/20260206_120000/memos/child_gen1_001
```

---

### 4. Get Red Verdict (Overseer Judgment)

**GET** `/api/runs/{runId}/verdicts/{graphId}`

Response:
```json
{
  "ok": true,
  "verdict": {
    "run_id": "20260206_120000",
    "graph_id": "child_gen1_001",
    "verdict": "KILL",
    "top_failures": [
      {
        "code": "LUCKY_SPIKE",
        "severity": 0.9,
        "evidence": "Best episode dominates: penalty=0.20"
      },
      {
        "code": "HIGH_DISPERSION",
        "severity": 0.6,
        "evidence": "High variance: worst=-0.300, median=0.100, penalty=0.30"
      }
    ],
    "strongest_evidence": [
      "Best episode dominates: penalty=0.20",
      "High variance: worst=-0.300, median=0.100, penalty=0.30"
    ],
    "next_action": {
      "type": "RESEARCH_TRIGGER",
      "suggestion": "Consider targeted research on lucky spike solutions"
    },
    "metrics_summary": {
      "episodes_count": 8,
      "years_covered": [2020, 2021, 2022],
      "lucky_spike_triggered": true,
      "median_return": 0.1,
      "dispersion": 0.25,
      "regime_count": 5
    },
    "created_at": "2026-02-06T12:05:30"
  }
}
```

**cURL Example:**
```bash
curl http://localhost:8050/api/runs/20260206_120000/verdicts/child_gen1_001
```

---

## Determinism Notes

### Caching

- **You.com API responses** are cached in `results/research_cache/` keyed by `sha256(normalized_query + params)`
- Cache hits return identical JSON (byte-for-byte reproducible)
- No network calls on cache hits

### Fingerprints

- **ResearchPack.fingerprint** = `sha256(query + normalized sources)`
- Same query + same sources → same fingerprint (deterministic)

### Blue Memo & Red Verdict

- **No LLM calls** - all text generation is template-based
- Mutation summaries derived from PatchSet ops (deterministic)
- Failure scoring uses fixed thresholds and penalty weights (deterministic)
- Same evaluation result → same memo + verdict (reproducible)

---

## Configuration Toggles

### Disable Memo/Verdict Generation

```python
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    generate_memos_verdicts=False,  # Disable Blue Memo + Red Verdict
)
```

### Enable Triggered Research (Advanced)

```python
phase3_config = Phase3Config(
    enabled=True,
    mode="episodes",
    research_budget_per_generation=2,  # Allow 2 triggered queries per gen
    research_on_kill_reasons=["LUCKY_SPIKE", "DRAWDOWN_FAIL"],
)
```

When a strategy is killed with one of these failure codes, Darwin will:
1. Check the Red Verdict for the top failure
2. If it matches a trigger code, generate a targeted research query
3. Save results to `results/runs/{run_id}/triggered_research/{graph_id}.json`

---

## Backwards Compatibility

- All new config fields have defaults (no breaking changes)
- Existing endpoints unchanged
- New endpoints are additive
- Older runs without memos/verdicts return 404 (graceful degradation)

---

## Testing Without Network

All tests mock the You.com HTTP client:

```python
from unittest.mock import Mock
from research.youcom import search_with_cache

mock_client = Mock()
mock_client.search.return_value = {"hits": [...]}

sources = search_with_cache("query", n_results=5, client=mock_client)
# No network call - uses mock
```

---

## Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Missing YOUCOM_API_KEY | 400 | `{"detail": "YOUCOM_API_KEY not set"}` |
| Invalid request body | 400 | `{"detail": "Invalid JSON body"}` |
| Research pack not found | 404 | `{"detail": "Research pack not found"}` |
| Blue Memo not found | 404 | `{"detail": "Blue Memo not found"}` |
| Red Verdict not found | 404 | `{"detail": "Red Verdict not found"}` |
| You.com API failure | 500 | `{"detail": "Research pack creation failed"}` |

---

## Example Workflow

1. **Create research pack** (optional):
   ```bash
   curl -X POST http://localhost:8050/api/research/packs \
     -H "Content-Type: application/json" \
     -d '{"query": "momentum strategies"}'
   # Returns: {"ok": true, "pack": {"id": "abc123", ...}}
   ```

2. **Launch Darwin run** with Phase3 enabled (existing flow - no changes)

3. **Fetch artifacts** for a specific graph:
   ```bash
   # Phase3 report (existing)
   curl http://localhost:8050/api/runs/20260206_120000/phase3/child_gen1_001

   # Blue Memo (new)
   curl http://localhost:8050/api/runs/20260206_120000/memos/child_gen1_001

   # Red Verdict (new)
   curl http://localhost:8050/api/runs/20260206_120000/verdicts/child_gen1_001
   ```

---

## Performance Notes

- **You.com API calls**: ~500-1000ms (first call only, then cached)
- **Memo/Verdict generation**: <10ms (pure Python, no LLM)
- **Artifact writes**: Atomic (temp → rename) to prevent corruption
- **No triggered research by default**: `research_budget_per_generation=0`

---

## Support

For issues or questions:
- Backend repo: `agentic_quant/`
- Research layer code: `research/` directory
- Tests: `tests/test_research_layer.py`
