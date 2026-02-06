# Hackathon Demo Checklist

**90 minutes to showtime!** Use this checklist to prepare your demo.

---

## Pre-Demo Setup (30 min)

### Backend (Render)
- [ ] Verify Render deployment is live: `https://your-app.onrender.com/api/health`
- [ ] Check environment variables are set:
  - [ ] POLYGON_API_KEY
  - [ ] OPENAI_API_KEY or ANTHROPIC_API_KEY
  - [ ] YOUCOM_API_KEY
- [ ] Verify persistent disk is mounted (cache survives deploys)
- [ ] Test API endpoints:
  ```bash
  curl https://your-app.onrender.com/api/runs
  curl https://your-app.onrender.com/api/health
  ```

### Frontend (Vercel or Local)
- [ ] Deploy frontend to Vercel or run locally
- [ ] Set `VITE_API_BASE_URL` to Render backend URL
- [ ] Test frontend loads and shows BootScreen
- [ ] Verify graceful fallback: unplug backend, should show mock data

### Gap & Go Strategy
- [ ] Review seed prompt: `prompts/gap_and_go_seed.txt`
- [ ] Test compilation locally (requires LLM API key):
  ```bash
  python -m llm.compile --prompt prompts/gap_and_go_seed.txt
  ```
- [ ] If compilation fails, prepare to demo with mock data

### Event Calendar
- [ ] Verify event calendar: `validation/event_calendar.py`
- [ ] Run smoke test:
  ```bash
  python scripts/smoke_gap_and_go.py
  ```
- [ ] Expected: Some episodes tagged with "event_day" (FOMC, earnings)

### Akash Integration (Optional)
- [ ] Review: `AKASH_DEPLOYMENT.md`
- [ ] Have Dockerfile ready to show
- [ ] Prepare talking points: "98% cost savings vs AWS"

---

## Demo Flow (15 min presentation)

### 1. The Problem (2 min)
**Script:**
> "Trading strategy development is slow and manual. Quants spend weeks writing, testing, and iterating on strategies. And even then, strategies overfit to historical data and fail in production."

**Show:**
- Slide with traditional quant workflow (slow, manual, overfitting)

---

### 2. Darwin AI Solution (3 min)
**Script:**
> "Darwin AI evolves trading strategies using natural language and LLM-driven mutations. You describe what you want in plain English, and Darwin generates, tests, and evolves strategies automatically."

**Show:**
- Architecture diagram (NL → Graph DSL → Backtest → LLM Mutate → Evolve)
- Emphasize: **Phase 3 Multi-Episode Validation** (8 random time windows, regime tagging)

**Key Features:**
- Graph-based strategy DSL (composable, interpretable)
- Phase 3 validation (overfitting protection via episodes + regimes)
- Research layer with You.com (self-advocacy + oversight)
- Akash-ready architecture (decentralized compute)

---

### 3. Live Demo: Gap & Go Strategy (5 min)

**Option A: Real Backend (Ideal)**
1. Open frontend: `https://your-vercel-app.vercel.app`
2. Show BootScreen animation
3. Navigate to Evolution Arena
4. Select a strategy → show fitness, regime performance
5. Click into Validation Viewer → show Phase 3 episodes with event tags
6. Open You.com Feed → show research pack, BlueMemo, RedVerdict
7. Show Lineage Tree → demonstrate parent-child mutations
8. Open Metrics Dashboard → show fitness progression across generations

**Option B: Mock Fallback (If Backend Fails)**
1. Unplug backend (simulate failure)
2. Show graceful fallback to mock data
3. Walk through same UI flow with mock strategies
4. Emphasize: "Frontend is resilient - works offline or online"

**Key Talking Points:**
- **Gap & Go Strategy:** Detect overnight gaps, enter on Nth green candle, exit at profit target
- **Event Calendar Integration:** Episodes tagged with FOMC meetings, earnings (using You.com knowledge)
- **Regime Diversity:** Darwin tests strategies on trending, choppy, high volatility, and drawdown periods
- **Research Layer:** Strategies advocate for themselves (BlueMemo), overseer judges (RedVerdict)

---

### 4. Multi-Sponsor Integration (2 min)

**You.com:**
- Research layer uses You.com for market context
- ResearchPack creation for strategy evaluation
- BlueMemo (self-advocacy) and RedVerdict (oversight)

**Akash Network:**
- Show `AKASH_DEPLOYMENT.md`
- Explain: "Darwin is designed to scale on Akash for 98% cost savings vs AWS"
- Emphasize architecture: Render for API, Akash for compute-heavy evolution runs

**Demo Akash Readiness:**
```bash
# Show Dockerfile
cat Dockerfile

# Show SDL template
cat AKASH_DEPLOYMENT.md | grep -A 30 "akash-deploy.yaml"
```

**Script:**
> "We architected Darwin to run on decentralized compute. For a 10-hour evolution run, AWS costs $4, Akash costs $0.05. That's 98% cheaper, with no vendor lock-in."

---

### 5. Technical Deep Dive (2 min)

**Phase 3 Multi-Episode Validation:**
- Show Phase 3 config in code or config file
- Explain: 8 random time windows, regime tagging (trend, volatility, choppiness, drawdown, event_day)
- Aggregated fitness across episodes (weighted by regime diversity)

**Event Calendar:**
- Show `validation/event_calendar.py`
- Explain: Strategies tested on FOMC days, earnings days, normal days
- Darwin learns which patterns work on event days vs normal days

**Research Layer:**
- Show `research/models.py` (ResearchPack, BlueMemo, RedVerdict)
- Explain: Strategies create BlueMemos (self-advocacy), Overseer creates RedVerdicts (judgment)
- Integration with You.com for market context

---

### 6. Results & Future (1 min)

**Current State:**
- ✅ Full backend + frontend integration
- ✅ Phase 3 multi-episode validation
- ✅ Event calendar with FOMC/earnings tagging
- ✅ Research layer with You.com
- ✅ Akash deployment docs + Dockerfile
- ✅ Graceful degradation (backend fail → mock data)

**Future Roadmap:**
- Parallel evolution on Akash (10 Darwin instances concurrently)
- News sentiment node (real-time You.com integration)
- Local LLMs on Akash GPUs (Llama 3.1 for compile/mutate)
- Multi-asset support (crypto, forex, commodities)

---

## Q&A Prep (Common Judge Questions)

**Q: How do you prevent overfitting?**
> "Phase 3 multi-episode validation. We test strategies on 8 random time windows with different market regimes. Strategies must perform well across trending, choppy, high volatility, and event days. Plus we use holdout data for final evaluation."

**Q: How does the LLM mutation work?**
> "The LLM sees the current strategy graph as JSON, its fitness scores across episodes, and regime tags. It suggests targeted mutations like 'increase RSI threshold' or 'tighten stop loss'. We compile the mutation to a new graph and evaluate it."

**Q: Why graph DSL instead of Python code?**
> "Three reasons: (1) Compositional - nodes are reusable building blocks. (2) Interpretable - you can visualize the strategy logic. (3) LLM-friendly - easier to mutate structured JSON than raw Python."

**Q: What's unique about your approach vs AutoML?**
> "Darwin combines symbolic AI (graph DSL) with neural AI (LLM mutations). AutoML is a black box. Darwin strategies are interpretable, explainable, and use domain knowledge. Plus we have the research layer for strategy advocacy and oversight."

**Q: How does You.com integration work?**
> "We use You.com for two things: (1) ResearchPacks - gather market context for strategy evaluation. (2) BlueMemos and RedVerdicts - strategies advocate for themselves using You.com knowledge, and an overseer judges them."

**Q: Can this actually trade live?**
> "Not yet - this is a research platform. But the output is a strategy graph + backtest report. You could integrate with Alpaca/Interactive Brokers to execute. The hard part is the strategy development, which Darwin automates."

**Q: Why Akash instead of AWS?**
> "Cost and decentralization. Darwin runs are embarrassingly parallel - perfect for commodity compute. Akash is 98% cheaper than AWS for our workload. Plus no vendor lock-in, and it aligns with Web3 ethos."

---

## Emergency Backup Plans

### If Backend Fails:
1. Show mock data in frontend (automatic fallback)
2. Show code instead: walk through `graph/schema.py`, `validation/episodes.py`
3. Run smoke tests locally: `python scripts/smoke_gap_and_go.py`

### If Frontend Fails:
1. Use API directly with curl/Postman
2. Show backend logs on Render
3. Fall back to architecture diagram + code walkthrough

### If LLM API Runs Out:
1. Show pre-compiled strategies in `graphs/`
2. Demo Phase 3 validation with existing graphs
3. Explain LLM mutation logic conceptually

### If Demo Machine Crashes:
1. Use phone to show deployed Vercel app
2. Show GitHub repo on another device
3. Present architecture slides only

---

## Post-Demo Materials

**Leave judges with:**
- [ ] GitHub repo link
- [ ] Live demo URL (Vercel frontend)
- [ ] README with quickstart
- [ ] AKASH_DEPLOYMENT.md for technical reviewers
- [ ] Contact info for follow-up questions

**README highlights:**
- One-line install: `pip install -r requirements.txt`
- Seed prompts in `prompts/`
- Full API docs at `/docs`
- Frontend source in `darwin-ai-frontend/`

---

## Timing Breakdown

| Section | Time | Notes |
|---------|------|-------|
| Problem Statement | 2 min | Keep it punchy |
| Darwin Solution | 3 min | Architecture + key features |
| Live Demo | 5 min | Gap & Go + event calendar |
| Multi-Sponsor | 2 min | You.com + Akash |
| Technical Deep Dive | 2 min | Phase 3, event calendar, research layer |
| Results & Future | 1 min | Wrap up with roadmap |
| **Total** | **15 min** | Leave 5 min for Q&A |

---

## Final Checks (5 min before demo)

- [ ] Backend health check passes
- [ ] Frontend loads successfully
- [ ] Mock data fallback works (unplug backend to test)
- [ ] Browser tabs organized: Frontend, GitHub, Akash docs
- [ ] Presentation slides ready (if using)
- [ ] Phone backup ready (hotspot if WiFi fails)
- [ ] Water bottle nearby (don't let your mouth go dry!)

---

**Good luck! You've built something real. Now go show it off. 🚀**
