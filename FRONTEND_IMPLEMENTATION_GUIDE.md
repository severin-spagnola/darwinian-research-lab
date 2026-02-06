# Frontend Implementation Guide - Research Layer

**For:** Frontend Engineers
**Date:** 2026-02-06
**Backend Version:** Research Layer v1.0

---

## Overview

The backend has added four new **additive** endpoints for the Research Pack + Blue Memo + Red Verdict layer. All existing endpoints and payloads remain unchanged.

This guide shows you how to integrate these new features into the frontend UI for a hackathon-ready demo.

---

## New Endpoints

### 1. POST /api/research/packs

**Purpose:** Create a research pack from a query, URL, or title.

**Request:**
```typescript
interface CreatePackRequest {
  query?: string;
  paper_url?: string;
  title?: string;
  n_results?: number; // default: 5
}
```

**Example Request:**
```json
POST /api/research/packs
Content-Type: application/json

{
  "query": "mean reversion trading strategies",
  "n_results": 5
}
```

**Response:**
```typescript
interface CreatePackResponse {
  ok: boolean;
  pack: ResearchPack;
}

interface ResearchPack {
  id: string;
  created_at: string;
  query: string;
  provider: "youcom";
  sources: ResearchSource[];
  extracted: ResearchExtraction;
  raw?: Record<string, any>;
  fingerprint: string;
}

interface ResearchSource {
  title: string;
  url: string;
  snippet?: string;
  provider_rank?: number;
  published_date?: string;
}

interface ResearchExtraction {
  assumptions: string[];
  knobs: string[];
  known_failure_modes: string[];
  suggested_tests: string[];
}
```

**Example Response:**
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
        "title": "Mean Reversion Explained",
        "url": "https://example.com/article",
        "snippet": "Mean reversion strategies assume prices return to mean...",
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
        "Cross-regime performance evaluation"
      ]
    },
    "fingerprint": "sha256:abcd..."
  }
}
```

---

### 2. GET /api/research/packs/{packId}

**Purpose:** Retrieve a research pack by ID.

**Response:** Same as POST response above.

**Example:**
```typescript
GET /api/research/packs/abc123def456

// Returns: { ok: true, pack: {...} }
```

---

### 3. GET /api/runs/{runId}/memos/{graphId}

**Purpose:** Get Blue Memo (self-advocacy) for a specific graph.

**Response:**
```typescript
interface BlueMemoResponse {
  ok: boolean;
  memo: BlueMemo;
}

interface BlueMemo {
  run_id: string;
  graph_id: string;
  parent_graph_id: string | null;
  generation: number | null;
  mutation_patch_summary: string[];
  claim: string;
  expected_improvement: string[];
  risks: string[];
  created_at: string;
}
```

**Example Response:**
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

**404 Response (if memo doesn't exist):**
```json
{
  "detail": "Blue Memo not found"
}
```

---

### 4. GET /api/runs/{runId}/verdicts/{graphId}

**Purpose:** Get Red Verdict (overseer judgment) for a specific graph.

**Response:**
```typescript
interface RedVerdictResponse {
  ok: boolean;
  verdict: RedVerdict;
}

interface RedVerdict {
  run_id: string;
  graph_id: string;
  verdict: "SURVIVE" | "KILL";
  top_failures: FailureEvidence[];
  strongest_evidence: string[];
  next_action: NextAction;
  metrics_summary: MetricsSummary;
  created_at: string;
}

interface FailureEvidence {
  code: string;
  severity: number; // 0.0-1.0
  evidence: string;
}

interface NextAction {
  type: "MUTATE" | "STOP_BRANCH" | "RESEARCH_TRIGGER" | "NONE";
  suggestion: string;
}

interface MetricsSummary {
  episodes_count: number;
  years_covered: number[];
  lucky_spike_triggered: boolean;
  median_return: number | null;
  dispersion: number | null;
  regime_count: number;
}
```

**Example Response:**
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

**404 Response (if verdict doesn't exist):**
```json
{
  "detail": "Red Verdict not found"
}
```

---

## UI Integration Plan

### Recommended Components

#### 1. Research Pack Creation (Optional Pre-Run Step)

**Component:** `ResearchPackCreator.tsx`

**Location:** New tab or modal before launching a run

**Features:**
- Text input for query/URL/title
- "Create Research Pack" button
- Display sources + extracted insights
- Save `pack.id` to launch a run with `research_pack_id`

**State:**
```typescript
const [packQuery, setPackQuery] = useState("");
const [loading, setLoading] = useState(false);
const [pack, setPack] = useState<ResearchPack | null>(null);

const createPack = async () => {
  setLoading(true);
  const response = await fetch("/api/research/packs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: packQuery, n_results: 5 }),
  });
  const data = await response.json();
  setPack(data.pack);
  setLoading(false);
};
```

**UI Elements:**
- Show sources as a list with title + URL + snippet
- Show extracted assumptions/knobs/failure modes/tests as collapsible sections
- "Use this pack for next run" button → saves `pack.id` to run config

---

#### 2. Node Detail Panel Enhancement

**Component:** `NodeDetailPanel.tsx` (existing - enhance)

**Current State:** Shows Phase3 report for selected node

**New Additions:**
Add two new tabs:
- **"Phase 3 Report"** (existing)
- **"Blue Memo"** (new)
- **"Red Verdict"** (new)

**Fetching Logic:**
```typescript
interface NodeArtifacts {
  phase3?: any; // existing
  blueMemo?: BlueMemo;
  redVerdict?: RedVerdict;
}

const [artifacts, setArtifacts] = useState<NodeArtifacts>({});
const [loading, setLoading] = useState(false);

const fetchArtifacts = async (runId: string, graphId: string) => {
  setLoading(true);

  // Fetch all three in parallel
  const [phase3Res, memoRes, verdictRes] = await Promise.all([
    fetch(`/api/runs/${runId}/phase3/${graphId}`).catch(() => null),
    fetch(`/api/runs/${runId}/memos/${graphId}`).catch(() => null),
    fetch(`/api/runs/${runId}/verdicts/${graphId}`).catch(() => null),
  ]);

  const phase3 = phase3Res?.ok ? await phase3Res.json() : null;
  const memo = memoRes?.ok ? (await memoRes.json()).memo : null;
  const verdict = verdictRes?.ok ? (await verdictRes.json()).verdict : null;

  setArtifacts({ phase3, blueMemo: memo, redVerdict: verdict });
  setLoading(false);
};
```

---

#### 3. Blue Memo Panel

**Component:** `BlueMemoPanel.tsx`

**Props:** `{ memo: BlueMemo | null }`

**UI Elements:**
- **Claim:** Large text block showing `memo.claim`
- **Mutation Summary:** Bullet list of `memo.mutation_patch_summary`
- **Expected Improvements:** Green-highlighted list of `memo.expected_improvement`
- **Risks:** Orange-highlighted list of `memo.risks`
- **Metadata:** Small text showing generation + parent graph ID

**Empty State:**
```tsx
{!memo && <p>No Blue Memo available for this graph (older run or not generated)</p>}
```

---

#### 4. Red Verdict Panel

**Component:** `RedVerdictPanel.tsx`

**Props:** `{ verdict: RedVerdict | null }`

**UI Elements:**
- **Verdict Badge:** Large badge showing "SURVIVE" (green) or "KILL" (red)
- **Top Failures:** List of failures with severity bars and evidence
- **Strongest Evidence:** Highlighted text blocks
- **Next Action:** Card showing recommended action + suggestion
- **Metrics Summary:** Grid showing episodes count, years covered, spike triggered, etc.

**Example:**
```tsx
<div>
  <Badge color={verdict.verdict === "SURVIVE" ? "green" : "red"}>
    {verdict.verdict}
  </Badge>

  <h3>Top Failures</h3>
  {verdict.top_failures.map(f => (
    <div key={f.code}>
      <strong>{f.code}</strong>
      <ProgressBar value={f.severity * 100} color="red" />
      <p>{f.evidence}</p>
    </div>
  ))}

  <h3>Next Action: {verdict.next_action.type}</h3>
  <p>{verdict.next_action.suggestion}</p>
</div>
```

**Empty State:**
```tsx
{!verdict && <p>No Red Verdict available for this graph</p>}
```

---

## Caching Suggestions

### Client-Side Cache

Cache fetched artifacts by `runId + graphId`:

```typescript
const artifactCache = new Map<string, NodeArtifacts>();

const getCachedOrFetch = async (runId: string, graphId: string) => {
  const key = `${runId}:${graphId}`;
  if (artifactCache.has(key)) {
    return artifactCache.get(key);
  }

  const artifacts = await fetchArtifacts(runId, graphId);
  artifactCache.set(key, artifacts);
  return artifacts;
};
```

### When to Invalidate

- **Never** - artifacts are immutable once created
- On page refresh: clear cache or persist to localStorage

---

## Empty/Loading/Error States

### Loading

```tsx
{loading && <Spinner />}
```

### 404 (Artifact Not Found)

```tsx
{!loading && !memo && <EmptyState message="No Blue Memo for this strategy" />}
```

This is **expected** for:
- Older runs (before research layer deployed)
- Runs where `generate_memos_verdicts=False`

### API Error

```tsx
{error && <ErrorBanner message={error.message} />}
```

---

## Minimal Hackathon Demo Flow

### Step 1: (Optional) Create Research Pack

1. User enters query: "momentum trading strategies"
2. Click "Create Research Pack"
3. Backend fetches from You.com (or cache)
4. Display sources + extracted insights
5. User clicks "Use for next run" → saves `pack.id`

### Step 2: Launch Run (Existing Flow)

- User clicks "Start Evolution"
- Backend runs Darwin with Phase3 enabled
- **No changes to this flow**

### Step 3: View Node Artifacts

1. User clicks on a node in the lineage graph
2. Frontend fetches:
   - Phase3 report (existing)
   - Blue Memo (new)
   - Red Verdict (new)
3. Display all three in tabbed interface:
   - **Phase 3 Tab:** Episode fitness, regime tags, penalties
   - **Blue Memo Tab:** Self-advocacy, claims, expected improvements, risks
   - **Red Verdict Tab:** Verdict, top failures, next action, metrics

---

## Backwards Compatibility

### Handling Older Runs

Older runs (before research layer) will return **404** for:
- `/api/runs/{runId}/memos/{graphId}`
- `/api/runs/{runId}/verdicts/{graphId}`

**Solution:** Gracefully handle 404s and show empty states:

```typescript
const memo = memoRes?.ok ? (await memoRes.json()).memo : null;
// If 404, memo is null → show "No Blue Memo available"
```

### Existing Endpoints

All existing endpoints remain unchanged:
- `GET /api/runs`
- `GET /api/runs/{runId}`
- `GET /api/runs/{runId}/phase3/{graphId}` (unchanged payload)
- `GET /api/runs/{runId}/evals/{graphId}`
- etc.

---

## Example React Hooks

### useResearchPack

```typescript
const useResearchPack = (packId: string | null) => {
  const [pack, setPack] = useState<ResearchPack | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!packId) return;

    setLoading(true);
    fetch(`/api/research/packs/${packId}`)
      .then(res => res.json())
      .then(data => setPack(data.pack))
      .finally(() => setLoading(false));
  }, [packId]);

  return { pack, loading };
};
```

### useNodeArtifacts

```typescript
const useNodeArtifacts = (runId: string, graphId: string) => {
  const [artifacts, setArtifacts] = useState<NodeArtifacts>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch Artifacts = async () => {
      setLoading(true);

      const [phase3Res, memoRes, verdictRes] = await Promise.all([
        fetch(`/api/runs/${runId}/phase3/${graphId}`).catch(() => null),
        fetch(`/api/runs/${runId}/memos/${graphId}`).catch(() => null),
        fetch(`/api/runs/${runId}/verdicts/${graphId}`).catch(() => null),
      ]);

      const phase3 = phase3Res?.ok ? await phase3Res.json() : null;
      const memo = memoRes?.ok ? (await memoRes.json()).memo : null;
      const verdict = verdictRes?.ok ? (await verdictRes.json()).verdict : null;

      setArtifacts({ phase3, blueMemo: memo, redVerdict: verdict });
      setLoading(false);
    };

    fetchArtifacts();
  }, [runId, graphId]);

  return { artifacts, loading };
};
```

---

## Notes on Triggered Research (Advanced)

If the backend enables `research_budget_per_generation > 0` and `research_on_kill_reasons`, you can optionally add a button to manually trigger research:

**Endpoint:** `POST /api/runs/{runId}/research/{graphId}` (not yet implemented - future feature)

For the hackathon, **ignore this** - it's an advanced feature.

---

## Testing Checklist

- [ ] Can create research pack with query
- [ ] Can create research pack with URL
- [ ] Research pack displays sources + extracted insights
- [ ] Can fetch Blue Memo for a graph
- [ ] Can fetch Red Verdict for a graph
- [ ] Gracefully handles 404 for missing memos/verdicts (older runs)
- [ ] Loading states work correctly
- [ ] Caching prevents duplicate fetches for same graph
- [ ] All three artifacts (phase3, memo, verdict) display in node detail panel

---

## Summary

**What to Build:**

1. **ResearchPackCreator** component (optional pre-run step)
2. **BlueMemoPanel** component (new tab in node detail)
3. **RedVerdictPanel** component (new tab in node detail)
4. **Fetch logic** for all three artifacts in parallel
5. **Empty/loading states** for graceful degradation

**What NOT to Change:**

- Existing Phase3 report rendering
- Existing run/eval endpoints
- Existing lineage graph visualization

**Integration Points:**

- Node click → fetch artifacts → display in tabs
- Research pack creation (optional) → save `pack.id` → reference in run config

---

## Support

For questions or issues:
- Backend repo: `agentic_quant/`
- Backend docs: `docs/HACKATHON_RESEARCH_LAYER.md`
- Frontend contact: [your contact info]
