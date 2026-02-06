# Frontend Issues & Integration To-Do List

**Created:** 2026-02-06
**Status:** Step 1 Complete - Issues Identified

---

## 🔴 CRITICAL ISSUES (Must Fix)

### 1. **All Data is Mocked - No Backend Integration**

**Current State:**
- `App.jsx` uses `generateEvolutionRun()` and `generateAPICosts()` from `mockDataGenerator.js`
- No API calls to the actual backend at `http://localhost:8050` or Render URL
- Frontend is completely disconnected from real Darwin runs

**Files Affected:**
- `darwin-ai-frontend/src/App.jsx` (lines 12-14, 27, 59)
- `darwin-ai-frontend/src/data/mockDataGenerator.js` (entire file)

**Fix Required:**
- Create API client to fetch real data from backend endpoints:
  - `GET /api/runs` - List all runs
  - `GET /api/runs/{run_id}` - Get run summary
  - `GET /api/runs/{run_id}/lineage` - Get lineage data
  - `GET /api/runs/{run_id}/evals/{graph_id}` - Get evaluation results
  - `GET /api/runs/{run_id}/phase3/{graph_id}` - Get Phase 3 reports
  - `GET /api/llm/usage` - Get LLM cost data
- Replace mock data with real API responses
- Add loading states and error handling

---

### 2. **You.com API Key Exposure Risk**

**Current State:**
- `youcomAPI.js` calls You.com API **directly from the browser** (lines 101-155)
- API key would be exposed in browser DevTools/network tab
- This is a **major security vulnerability** for production

**Files Affected:**
- `darwin-ai-frontend/src/utils/youcomAPI.js` (lines 101-155)
- `darwin-ai-frontend/src/components/feed/YouComFeed.jsx` (uses `searchYouCom()`)

**Fix Required:**
- **DO NOT call You.com API from frontend**
- Use backend proxy endpoint instead:
  - Backend already has research pack endpoints: `POST /api/research/packs`, `GET /api/research/packs/{packId}`
  - Create new backend endpoint: `POST /api/research/search` to proxy You.com calls
  - Frontend calls backend, backend calls You.com (keeps API key secret)
- Update `YouComFeed.jsx` to call backend proxy instead of direct API

---

### 3. **Missing Frontend Environment Variables**

**Current State:**
- No `.env` file in `darwin-ai-frontend/`
- No `VITE_API_BASE_URL` to configure backend endpoint
- No `VITE_YOUCOM_API_KEY` (shouldn't be needed if we fix issue #2)

**Files Affected:**
- `darwin-ai-frontend/` (missing `.env` file)

**Fix Required:**
- Create `darwin-ai-frontend/.env` with:
  ```
  VITE_API_BASE_URL=http://localhost:8050
  ```
- Create `darwin-ai-frontend/.env.example`:
  ```
  VITE_API_BASE_URL=http://localhost:8050
  # For production, set to your Render backend URL:
  # VITE_API_BASE_URL=https://agentic-quant-backend.onrender.com
  ```
- Add `.env` to `.gitignore`

---

### 4. **APICostDashboard Uses Simulated Data**

**Current State:**
- Component simulates cost increments using `setInterval` (lines 258-318)
- Generates fake "events" and adds random costs (lines 269-292)
- Does NOT fetch real LLM usage from backend

**Files Affected:**
- `darwin-ai-frontend/src/components/dashboard/APICostDashboard.jsx` (lines 258-318)

**Fix Required:**
- Remove simulation logic
- Fetch real cost data from backend:
  - `GET /api/llm/usage` - Global LLM usage
  - `GET /api/runs/{run_id}/llm/usage` - Per-run usage
- Expected backend response format:
  ```json
  {
    "total_calls": 150,
    "total_tokens": 45000,
    "total_cost": 1.35,
    "by_stage": {
      "compile": {"count": 1, "tokens": 2000},
      "mutate": {"count": 149, "tokens": 43000}
    }
  }
  ```
- Map backend data to component's expected `costData` prop format

---

### 5. **MetricsDashboard Expects Phase 3 Data That May Not Exist**

**Current State:**
- Accesses `strategy.results.phase3.aggregated_fitness` (line 43)
- Accesses `strategy.results.red_verdict` and `strategy.red_verdict` (lines 59-60)
- These fields only exist if `robust_mode: true` was used in the run
- Will show undefined/0 for Phase 2 runs (default behavior)

**Files Affected:**
- `darwin-ai-frontend/src/components/dashboard/MetricsDashboard.jsx` (lines 42-69)

**Fix Required:**
- Add fallback to Phase 2 metrics when Phase 3 doesn't exist:
  ```javascript
  function fitnessOf(s) {
    // Try Phase 3 first
    const p3 = s?.results?.phase3?.aggregated_fitness ?? s?.phase3?.aggregated_fitness
    if (p3 !== null && p3 !== undefined) return safeNumber(p3, 0)

    // Fallback to Phase 2
    const p2 = s?.results?.fitness ?? s?.fitness
    return safeNumber(p2, 0)
  }
  ```
- Handle missing `red_verdict` gracefully (it's a research layer feature, may not exist)
- Display "N/A" or hide sections when data is missing

---

## ⚠️ HIGH PRIORITY ISSUES

### 6. **No Run Selection UI**

**Current State:**
- App hardcodes mock data generation in `useMemo(() => generateEvolutionRun(5), [])` (line 27)
- No way for user to select which run to view
- No way to start a new Darwin run from the UI

**Fix Required:**
- Add run selector dropdown/list
- Fetch available runs from `GET /api/runs`
- Allow user to click a run to view its evolution
- Add "New Run" button that:
  - Shows form with parameters (nl_text, symbols, timeframe, dates, depth, branching, robust_mode)
  - Calls `POST /api/run` to start evolution
  - Polls `GET /api/run/{run_id}/events` for SSE updates

---

### 7. **YouComFeed Calls Direct API (Security + Wrong Endpoint)**

**Current State:**
- Component imports `searchYouCom` from `youcomAPI.js` (line 20)
- Calls You.com API directly from browser (insecure)
- Uses You.com's public search endpoint, not our backend's research pack system

**Fix Required:**
- Remove direct You.com API calls
- Use backend endpoints:
  - `POST /api/research/packs` - Create research pack (backend calls You.com)
  - `GET /api/research/packs/{packId}` - Get cached research pack
- Component should call backend, which handles You.com API internally
- Backend caches responses in `results/research_cache/`

---

### 8. **Missing Real-Time Updates (SSE Not Implemented)**

**Current State:**
- App simulates progress with playback controls (lines 21-22, 67-74)
- No connection to actual running Darwin processes
- Backend supports SSE via `GET /api/run/{run_id}/events` but frontend doesn't use it

**Fix Required:**
- Implement EventSource to connect to `GET /api/run/{run_id}/events`
- Listen for events:
  - `run_started`
  - `log` (progress messages)
  - `run_finished` (final summary)
  - `error`
- Update UI in real-time as Darwin evolves strategies
- Remove mock playback controls, use real progress from SSE

---

### 9. **Hardcoded Data Shapes Don't Match Backend**

**Current State:**
- Mock data generator creates data shapes that may not match actual backend responses
- Example: `strategy.results.phase3.aggregated_fitness` vs backend's actual structure
- Example: `api.breakdown.you_com_searches` doesn't exist in backend (backend has `compile`, `mutate`)

**Fix Required:**
- Review actual backend API response schemas (see `docs/DATA_STRUCTURES.md`)
- Update component prop interfaces to match real backend data
- Test with real backend responses, not mocks

---

## ⚡ MEDIUM PRIORITY ISSUES

### 10. **No Error Handling for API Calls**

**Current State:**
- No try/catch blocks
- No error states
- No retry logic
- No fallback UI when backend is down

**Fix Required:**
- Add error boundaries
- Add loading/error states to components
- Show user-friendly error messages
- Add retry buttons for failed requests

---

### 11. **No CORS Configuration for Deployed Frontend**

**Current State:**
- Backend `backend_api/main.py` CORS allows:
  - `http://localhost:3000`
  - `http://localhost:5173`
- But NO production frontend domain

**Fix Required:**
- When frontend is deployed (e.g., Vercel, Netlify), add that domain to CORS:
  ```python
  allow_origins=[
      "http://localhost:3000",
      "http://localhost:5173",
      "https://your-frontend.vercel.app",  # Add production domain
  ],
  ```

---

### 12. **Metrics Breakdown Services Wrong**

**Current State:**
- APICostDashboard defines services (line 26-48):
  - `you_com_searches` (unit cost: $0.002)
  - `llm_mutations` (unit cost: $0.03)
  - `validation_runs` (unit cost: $0.008)
- But backend LLM usage API returns:
  - `by_stage: { compile: {...}, mutate: {...} }`
- Service names don't match!

**Fix Required:**
- Update `SERVICES` array to match backend's actual cost breakdown structure
- Backend tracks:
  - LLM calls (compile + mutate stages)
  - You.com calls (if research packs are used)
  - Polygon API calls are free (cached)
- Map backend data correctly to frontend cost visualization

---

### 13. **No TypeScript - Prop Types Not Validated**

**Current State:**
- All files are `.jsx` (JavaScript, not TypeScript)
- No prop type validation
- Easy to pass wrong data shape and get runtime errors

**Fix Required (Optional):**
- Consider migrating to TypeScript (`.tsx`)
- Or add PropTypes validation:
  ```javascript
  APICostDashboard.propTypes = {
    costData: PropTypes.shape({
      total_cost: PropTypes.number,
      breakdown: PropTypes.object,
      // ...
    }),
    // ...
  }
  ```

---

## 📋 LOWER PRIORITY / NICE TO HAVE

### 14. **Mock Data Generator Can Be Removed**

**Current State:**
- `mockDataGenerator.js` is 500+ lines of fake data generation
- Not needed once real API integration is complete

**Fix Required:**
- After real API integration is working, delete `mockDataGenerator.js`
- Update imports in `App.jsx`

---

### 15. **No Loading States**

**Current State:**
- Components assume data is always available
- No spinners or skeleton screens while fetching

**Fix Required:**
- Add loading states:
  ```javascript
  const [isLoading, setIsLoading] = useState(true)
  const [data, setData] = useState(null)

  useEffect(() => {
    setIsLoading(true)
    fetch('/api/runs/123')
      .then(res => res.json())
      .then(data => setData(data))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) return <Spinner />
  ```

---

### 16. **Playback Controls Are Mock-Only**

**Current State:**
- Layout header has play/pause and speed controls (lines 21-22, 97-100)
- These only work for mock data playback
- Real Darwin runs happen on backend, not controllable from frontend

**Fix Required:**
- For real runs, replace playback controls with:
  - "Start New Run" button
  - "View Live Run" (if a run is in progress)
  - Run history selector
- Keep playback controls only for demo/replay mode (viewing past runs)

---

## 📊 SUMMARY

### By Severity:

| Severity | Count | Examples |
|----------|-------|----------|
| 🔴 Critical | 5 | No backend integration, API key exposure, missing env vars |
| ⚠️ High | 4 | No run selection, wrong You.com usage, no SSE, wrong data shapes |
| ⚡ Medium | 4 | No error handling, CORS issues, wrong cost breakdown |
| 📋 Low | 3 | Mock data removal, loading states, playback controls |

### Total Issues: 16

---

## 🎯 RECOMMENDED FIX ORDER

1. **Create frontend `.env` file** (Issue #3)
2. **Create backend API client module** (Issue #1)
3. **Replace mock data with real API calls in App.jsx** (Issue #1)
4. **Fix You.com to use backend proxy** (Issues #2, #7)
5. **Fix APICostDashboard to use real LLM usage API** (Issues #4, #12)
6. **Add Phase 2 fallback to MetricsDashboard** (Issue #5)
7. **Implement SSE for real-time updates** (Issue #8)
8. **Add run selection UI** (Issue #6)
9. **Add error handling** (Issue #10)
10. **Update CORS for production** (Issue #11)
11. **Add loading states** (Issue #15)
12. **Clean up mock data generator** (Issue #14)

---

## 🚀 NEXT STEPS

**Step 1 Complete:** ✅ Issues identified and documented

**Step 2:** Wait for friend's changelog/prompt with mock data details, then implement fixes

**Step 3:** High-level meta-review to ensure project will work end-to-end

---

**Ready to proceed to Step 2 when you share your friend's prompt!**
