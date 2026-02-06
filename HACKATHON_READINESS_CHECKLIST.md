# Hackathon Readiness Checklist

**Date:** 2026-02-06
**Status:** Pre-Demo Review Complete

---

## 🚨 Critical Issues (Must Fix Before Demo)

### 1. ❌ **No "New Run" UI**
**Severity:** CRITICAL
**Impact:** Cannot start Phase 3 runs from frontend

**Current State:**
- `startRun()` API exists but no UI to call it
- No way to set `robust_mode: true` from frontend
- Can only view historical runs

**Quick Fix Options:**

**Option A: Make Phase 3 Default (5 min)**
```python
# In backend_api/main.py, line 693
phase3_config = Phase3Config(
    enabled=True,  # Always on
    mode="episodes",
    n_episodes=8,
    # ... rest of config
)
# Remove the "if request.robust_mode:" check
```

**Option B: Add Simple Run Button (30 min)**
```jsx
// In App.jsx
<button onClick={async () => {
  const runId = await startRun({
    nl_text: "Generate momentum strategy",
    symbols: ["AAPL", "MSFT"],
    start_date: "2020-01-01",
    end_date: "2024-12-31",
    robust_mode: true,  // Phase 3
    depth: 3,
    branching: 2,
  })
  setSelectedRunId(runId)
}}>
  Start New Run (Phase 3)
</button>
```

**Recommendation:** Use Option A for hackathon demo - always enable Phase 3.

---

### 2. ⚠️ **Polygon Cache Not Persistent**
**Severity:** HIGH
**Impact:** Cache cleared on every Render deploy, slower demo

**Current State:**
- Cache directory: `/opt/render/project/src/cache` (NOT on persistent disk)
- Persistent disk only mounted at: `/opt/render/project/src/results`
- Every deploy = re-download all market data

**Fix (2 min):**
```python
# In config.py, line 15
CACHE_DIR = RESULTS_DIR / "cache"  # Move to persistent disk
```

Then redeploy once to populate cache on persistent storage.

---

### 3. ⚠️ **No LLM Cost Hard Limits**
**Severity:** MEDIUM
**Impact:** Could rack up unexpected API costs during demo

**Current State:**
- Budget tracking exists but no hard caps
- Run could cost $50+ if something goes wrong

**Fix (5 min):**
```python
# In backend_api/main.py, after line 779
MAX_COST_PER_RUN = 10.0  # $10 hard limit
if budget.estimated_cost_usd > MAX_COST_PER_RUN:
    logger.error(f"[{run_id}] Budget exceeded: ${budget.estimated_cost_usd:.2f}")
    raise HTTPException(
        status_code=429,
        detail=f"Run cost limit exceeded (${MAX_COST_PER_RUN})"
    )
```

---

### 4. ❌ **No SSE Implementation in Frontend**
**Severity:** LOW (for completed runs) / HIGH (for live demo)
**Impact:** Cannot show live progress during evolution

**Current State:**
- `connectToRunEvents()` exists in API client but not used
- Frontend only shows completed runs
- No real-time progress updates

**Fix (60 min):**
```jsx
// In App.jsx, add useEffect for SSE
useEffect(() => {
  if (!selectedRunId) return

  const eventSource = connectToRunEvents(selectedRunId, {
    onLog: (data) => {
      console.log('Progress:', data.message)
      // Update UI with progress
    },
    onRunFinished: (data) => {
      console.log('Run complete!', data)
      // Refresh run data
      loadRunData()
    },
  })

  return () => eventSource.close()
}, [selectedRunId])
```

**Workaround for Demo:**
- Pre-run evolution before demo
- Show completed runs only
- Narrate what would happen live

---

## ✅ Must-Have Checks (Already Good)

### 1. ✅ **Keys + Config**
- [x] `YOUCOM_API_KEY` present in `.env`
- [x] `POLYGON_API_KEY` present in `.env`
- [x] `ANTHROPIC_API_KEY` present in `.env`
- [x] `OPENAI_API_KEY` present in `.env`
- [x] All keys in `render.yaml` (sync: false - must be set manually in Render dashboard)

**Action Before Deploy:**
- [ ] Set all 4 keys in Render dashboard environment variables

---

### 2. ✅ **Persistent Disk Paths Match**
- Render mounts: `/opt/render/project/src/results`
- Backend writes: `BASE_DIR / "results"` = `/opt/render/project/src/results`
- **Paths match!** ✅

**But:** Cache directory needs fix (see Critical Issue #2)

---

### 3. ✅ **CORS Configuration**
- Localhost origins allowed: `http://localhost:3000`, `http://localhost:5173`
- Production placeholder exists (commented out)

**Before deploying frontend:**
- [ ] Add production frontend URL to CORS in `backend_api/main.py`

---

### 4. ✅ **Phase 3 Backend Implementation**
- Phase 3 config exists in `backend_api/main.py` (lines 693-712)
- Correctly creates `Phase3Config` when `robust_mode: true`
- All endpoints work: `/api/runs/{runId}/phase3/{graphId}`

**But:** Frontend has no way to trigger it (see Critical Issue #1)

---

### 5. ✅ **You.com Security**
- Backend proxy endpoint: `/api/research/search` ✅
- Frontend uses backend proxy ✅
- API key never exposed to browser ✅

---

### 6. ✅ **Data Caching**
- Polygon data cached to parquet files ✅
- You.com results cached in `results/research_cache/` ✅
- Both use persistent cache keys ✅

**But:** Polygon cache location needs fix (see Critical Issue #2)

---

### 7. ✅ **Artifact Size**
- Phase 3 reports saved as separate JSON files
- Not returned in summary endpoint (prevents large payloads)
- UI loads incrementally ✅

---

### 8. ✅ **Frontend Integration**
- All mock data removed ✅
- Real API calls implemented ✅
- Loading/error states ✅
- Phase 2/3 fallback ✅

---

## ⚠️ High-Leverage Operational Items

### 1. ⚠️ **No Run Reproducibility Tracking**
**Impact:** Hard to debug issues or reproduce demo

**Missing:**
- Random seeds used for episode sampling
- Sampling mode per generation
- Data cache fingerprints

**Fix (15 min):**
```python
# Save in run_config.json
{
  "phase3_config": {
    "seed": 42,  # Add this
    "sampling_mode": "uniform_random",
    # ...
  },
  "data_fingerprint": {
    "polygon_cache_hash": "abc123...",
    "cache_timestamp": "2026-02-06T10:00:00Z"
  }
}
```

---

### 2. ⚠️ **No "Demo Mode" Config**
**Impact:** Every demo run takes 10+ minutes

**Recommendation:**
```python
# Add to backend_api/main.py
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

if DEMO_MODE:
    # Smaller, faster runs for demo
    depth = min(depth, 2)
    branching = min(branching, 1)
    phase3_config.n_episodes = 3  # Not 8
```

Then set `DEMO_MODE=true` in Render for quick demo runs.

---

### 3. ⚠️ **No Pre-Warmed Demo Run**
**Impact:** Demo depends on live API calls succeeding

**Recommendation:**
- Run one full evolution locally before demo
- Push to Render so it's in `results/runs/`
- Use that run for primary demo
- Live run as "bonus" if time permits

---

### 4. ✅ **Rate Limit Handling**
- You.com: Cached, graceful fallback ✅
- Polygon: Cached, rate limit errors caught ✅

---

## 📋 Quality-of-Demo Items

### 1. ⚠️ **"What is Happening" Visibility**
**Current State:** SSE events exist but frontend doesn't show them

**Quick Fix:**
```jsx
// Add a status bar in App.jsx
<div className="status-bar">
  Current: Generation {genIdx} |
  Survivors: {currentGeneration.filter(s => s.state !== 'dead').length} |
  Best Fitness: {Math.max(...currentGeneration.map(fitnessOf))}
</div>
```

---

### 2. ✅ **Missing Artifacts Handled**
- Frontend checks for 404s gracefully ✅
- Phase 2 runs don't break when phase3 reports missing ✅

---

### 3. ⚠️ **Frontend Error Messages**
**Current State:** Generic "Failed to load" messages

**Enhancement:**
```jsx
// In App.jsx error states
<div>Failed to load runs</div>
<div>Possible causes:</div>
<ul>
  <li>Backend not running (check http://localhost:8050/api/health)</li>
  <li>CORS issue (check browser console)</li>
  <li>No runs created yet (run POST /api/run)</li>
</ul>
```

---

## 🎯 Pre-Demo Checklist

### Backend
- [ ] Set all API keys in Render environment
- [ ] Fix cache directory to persistent disk
- [ ] Add LLM cost hard limit ($10 cap)
- [ ] Make Phase 3 default (or add run creation UI)
- [ ] Deploy to Render
- [ ] Verify health check: `curl https://your-service.onrender.com/api/health`

### Frontend
- [ ] Update `VITE_API_BASE_URL` to Render URL
- [ ] Add Render backend URL to CORS allowlist
- [ ] Deploy frontend (if separate)
- [ ] Test: Can load runs list
- [ ] Test: Can view run details
- [ ] Test: LLM costs display correctly
- [ ] Test: Phase 3 reports show up

### Data
- [ ] Pre-run one demo evolution
- [ ] Verify results saved to persistent disk
- [ ] Warm Polygon cache for demo symbols/dates
- [ ] Test: Demo run loads in <2 seconds

### Demo Script
- [ ] Prepare narration for each UI section
- [ ] Have backup run ready if live run fails
- [ ] Test full demo flow 3 times
- [ ] Time the demo (aim for <5 min)

---

## 🚀 Deployment Commands

### Backend
```bash
# Commit changes
git add -A
git commit -m "Pre-demo fixes: cache location, Phase 3 default, cost limits"
git push origin main

# Render auto-deploys from main branch
# Or manually trigger from Render dashboard
```

### Frontend (if separate deployment)
```bash
cd darwin-ai-frontend
npm run build
# Deploy dist/ to Vercel/Netlify
# Or commit and push if using Git-based deploy
```

---

## 🐛 Emergency Debugging

### If backend won't start on Render:
1. Check logs in Render dashboard
2. Verify all env vars set
3. Check health endpoint: `/api/health`
4. Look for "YOUCOM_API_KEY not set" error

### If frontend shows "No runs found":
1. Check CORS errors in browser console
2. Verify `VITE_API_BASE_URL` is correct
3. Test backend directly: `curl <BACKEND_URL>/api/runs`
4. Create a test run via Postman/curl

### If costs show $0.00:
1. Check backend has run data: `GET /api/runs/{runId}/llm/usage`
2. Verify budget.json exists in run directory
3. Check `normalizeCostData()` in APICostDashboard

### If Phase 3 reports missing:
1. Verify `robust_mode: true` was used
2. Check `results/runs/{runId}/phase3_reports/` exists
3. Ensure Phase 3 config is enabled in backend

---

## ⏱️ Time Estimates

**Critical Fixes:**
- Cache location fix: 2 min
- Phase 3 always-on: 5 min
- Cost hard limit: 5 min
- **Total:** 12 minutes

**Pre-Demo Setup:**
- Deploy backend: 10 min
- Set env vars: 5 min
- Pre-run demo: 20 min
- Test frontend: 10 min
- **Total:** 45 minutes

**Nice-to-Have Enhancements:**
- SSE implementation: 60 min
- Run creation UI: 30 min
- Demo mode config: 15 min
- **Total:** 105 minutes

---

## 📞 Support Contacts

**Backend Issues:** Check `backend_debug.log` or `/api/debug/errors`
**Frontend Issues:** Check browser DevTools console
**Deployment Issues:** Check Render dashboard logs

---

**Status:** ✅ Core functionality works, 3 critical fixes needed (12 min), then ready to demo!
