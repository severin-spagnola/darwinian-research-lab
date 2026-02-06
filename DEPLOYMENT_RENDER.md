# Render.com Deployment Guide

**Project:** Agentic Quant Backend
**Type:** Monorepo Web Service (FastAPI)
**Platform:** Render.com

---

## Prerequisites

1. **Render.com Account** - Sign up at [render.com](https://render.com)
2. **GitHub Repository** - Your code must be pushed to GitHub
3. **API Keys** - You'll need:
   - `YOUCOM_API_KEY` (for research layer)
   - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (for LLM mutations)
   - `POLYGON_API_KEY` (for market data)

---

## Deployment Methods

### Option 1: Blueprint (Recommended - Infrastructure as Code)

This method uses the `render.yaml` file for automated setup.

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Add Render deployment config"
   git push origin main
   ```

2. **Create New Blueprint on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New +"** → **"Blueprint"**
   - Connect your GitHub repository
   - Select the branch: `main`
   - Render will detect `render.yaml` automatically
   - Click **"Apply"**

3. **Set Environment Variables**:
   After the blueprint is applied, go to the web service settings and add:
   ```
   YOUCOM_API_KEY=<your_key>
   ANTHROPIC_API_KEY=<your_key>  # or OPENAI_API_KEY
   POLYGON_API_KEY=<your_key>
   ```

4. **Persistent Disk Configuration**:
   - The blueprint creates a 10GB disk at `/opt/render/project/src/results`
   - This persists research packs, phase3 reports, memos, verdicts, and cache
   - Adjust size in `render.yaml` if needed (10GB, 20GB, etc.)

---

### Option 2: Manual Web Service Creation

If you prefer manual setup without the blueprint:

1. **Create Web Service**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New +"** → **"Web Service"**
   - Connect your GitHub repository
   - Configure:
     - **Name**: `agentic-quant-backend`
     - **Region**: Oregon (or your preference)
     - **Branch**: `main`
     - **Runtime**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT`

2. **Environment Variables**:
   - `PYTHON_VERSION=3.11`
   - `YOUCOM_API_KEY=<your_key>`
   - `ANTHROPIC_API_KEY=<your_key>` (or `OPENAI_API_KEY`)
   - `POLYGON_API_KEY=<your_key>`
   - `PORT=8050` (Render sets this automatically, but you can override)

3. **Add Persistent Disk**:
   - In service settings, go to **"Disks"**
   - Click **"Add Disk"**
   - **Name**: `results-storage`
   - **Mount Path**: `/opt/render/project/src/results`
   - **Size**: 10GB (or more)

4. **Health Check**:
   - **Path**: `/api/health`
   - **Interval**: 30s
   - **Timeout**: 10s
   - **Unhealthy Threshold**: 3

---

## Post-Deployment

### 1. Verify Deployment

Once deployed, your backend will be available at:
```
https://agentic-quant-backend.onrender.com
```

Test the health check:
```bash
curl https://agentic-quant-backend.onrender.com/api/health
# Expected: {"status": "ok", "version": "1.0.0"}
```

### 2. Test Research Layer

Create a research pack:
```bash
curl -X POST https://agentic-quant-backend.onrender.com/api/research/packs \
  -H "Content-Type: application/json" \
  -d '{"query": "momentum trading strategies", "n_results": 5}'
```

Expected response:
```json
{
  "ok": true,
  "pack": {
    "id": "abc123...",
    "query": "momentum trading strategies",
    "sources": [...]
  }
}
```

### 3. List Runs

```bash
curl https://agentic-quant-backend.onrender.com/api/runs
```

---

## Persistent Storage

### What Gets Stored

The persistent disk at `/opt/render/project/src/results` stores:

```
results/
├── research_packs/        # Research packs (shared across runs)
├── research_cache/        # You.com API response cache
└── runs/{run_id}/
    ├── summary.json       # Run summary
    ├── run_config.json    # Configuration
    ├── lineage.jsonl      # Lineage graph
    ├── graphs/            # Strategy graphs
    ├── evals/             # Evaluation results
    ├── phase3_reports/    # Phase 3 robustness reports
    ├── blue_memos/        # Blue Memos (research layer)
    ├── red_verdicts/      # Red Verdicts (research layer)
    └── llm_transcripts/   # LLM API call logs
```

### Disk Management

- **Initial Size**: 10GB (configured in `render.yaml`)
- **Upgrade**: Can be increased in Render dashboard (10GB → 20GB → 50GB, etc.)
- **Cleanup**: Old runs can be deleted via shell access or custom cleanup endpoint

---

## Monitoring and Logs

### View Logs

In Render dashboard:
1. Go to your web service
2. Click **"Logs"** tab
3. View real-time logs from uvicorn and FastAPI

Or via CLI:
```bash
# Install Render CLI
npm install -g render

# View logs
render logs -s agentic-quant-backend --tail
```

### Debug Endpoints

The backend exposes debug endpoints for troubleshooting:

**Recent Requests**:
```bash
curl https://agentic-quant-backend.onrender.com/api/debug/requests
```

**Recent Errors**:
```bash
curl https://agentic-quant-backend.onrender.com/api/debug/errors
```

---

## Scaling

### Free Tier (Starter Plan)

- 512 MB RAM
- 0.5 CPU
- Spins down after 15 minutes of inactivity
- Cold start: ~30-60 seconds

**Limitations**:
- Long Darwin runs may timeout on free tier
- Use for testing/demo only

### Paid Tiers

For production, upgrade to **Standard** or **Pro**:
- **Standard**: 2 GB RAM, 1 CPU, no spin-down ($7/month)
- **Pro**: 4 GB RAM, 2 CPU, no spin-down ($25/month)

Darwin evolution with LLM mutations is CPU/memory intensive - recommend **Standard** or higher.

---

## Environment Variables Reference

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `PYTHON_VERSION` | No | Python version | `3.11` |
| `PORT` | No | Port to bind (auto-set by Render) | `8050` |
| `YOUCOM_API_KEY` | **Yes** (for research) | You.com API key | `your_key` |
| `ANTHROPIC_API_KEY` | **Yes** (if using Claude) | Anthropic API key | `sk-ant-...` |
| `OPENAI_API_KEY` | **Yes** (if using OpenAI) | OpenAI API key | `sk-...` |
| `POLYGON_API_KEY` | **Yes** | Polygon.io API key | `your_key` |

**Note**: You only need ONE of `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` depending on which LLM provider you use for mutations.

---

## Auto-Deploy

The blueprint is configured for **auto-deploy** on push to `main`:

```yaml
autoDeploy: true
```

Whenever you push to the `main` branch, Render will:
1. Pull latest code
2. Run `pip install -r requirements.txt`
3. Restart the service with new code

To disable auto-deploy:
- Edit `render.yaml` and set `autoDeploy: false`
- OR disable in Render dashboard under service settings

---

## CORS Configuration

The backend allows CORS from:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)

For production frontend (e.g., Vercel, Netlify), add your frontend domain:

```python
# backend_api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://your-frontend.vercel.app",  # Add production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy.

---

## Troubleshooting

### Issue: Service won't start

**Check logs** in Render dashboard. Common causes:
- Missing environment variables (API keys)
- Dependency installation failure
- Port binding error

**Fix**: Ensure `render.yaml` specifies correct start command:
```yaml
startCommand: uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT
```

### Issue: 404 on all endpoints

**Cause**: Uvicorn may not be finding the app.

**Fix**: Ensure the start command uses the correct module path:
```bash
uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT
```

### Issue: Persistent disk not working

**Symptoms**: Research packs/cache not persisting after restart.

**Fix**:
1. Verify disk is mounted at `/opt/render/project/src/results`
2. Check `config.py` uses this path:
   ```python
   RESULTS_DIR = Path(__file__).parent / "results"
   ```
3. Render's working directory is `/opt/render/project/src/`

### Issue: Darwin runs timeout

**Cause**: Free tier spins down after 15 minutes, long runs get killed.

**Fix**:
- Upgrade to **Standard** plan (no spin-down)
- OR reduce `max_total_evals` for shorter runs

### Issue: Research pack creation fails with 400

**Cause**: `YOUCOM_API_KEY` not set.

**Fix**: Add environment variable in Render dashboard:
```
YOUCOM_API_KEY=your_actual_key
```

---

## Security Notes

### API Keys

- **Never commit API keys to git**
- Set them as environment variables in Render dashboard
- Use Render's secret storage (not visible in logs)

### Public Endpoints

All endpoints are **publicly accessible** by default. For production:

1. Add authentication middleware (e.g., API key header)
2. Use Render's IP whitelist feature
3. Deploy behind a reverse proxy (Cloudflare, etc.)

---

## Next Steps

1. **Deploy backend** using blueprint or manual setup
2. **Deploy frontend** (if applicable) to Vercel/Netlify
3. **Update CORS** to allow frontend domain
4. **Test end-to-end** flow:
   - Create research pack
   - Launch Darwin run
   - View lineage graph
   - Fetch Blue Memos and Red Verdicts

---

## Support

For Render-specific issues:
- [Render Docs](https://render.com/docs)
- [Render Community](https://community.render.com)

For backend issues:
- Check logs: `/api/debug/errors`
- Review documentation: `docs/HACKATHON_RESEARCH_LAYER.md`
- Test locally first: `uvicorn backend_api.main:app --reload`

---

## Example: Full Deployment Workflow

```bash
# 1. Ensure all code is committed
git status
git add .
git commit -m "Ready for deployment"

# 2. Push to GitHub
git push origin main

# 3. Create Blueprint on Render (via dashboard)
# - Connect GitHub repo
# - Select main branch
# - Apply blueprint

# 4. Set environment variables in Render dashboard
# - YOUCOM_API_KEY
# - ANTHROPIC_API_KEY or OPENAI_API_KEY
# - POLYGON_API_KEY

# 5. Wait for deployment (usually 2-5 minutes)

# 6. Test health check
curl https://agentic-quant-backend.onrender.com/api/health

# 7. Test research layer
curl -X POST https://agentic-quant-backend.onrender.com/api/research/packs \
  -H "Content-Type: application/json" \
  -d '{"query": "mean reversion trading", "n_results": 3}'

# 8. Success! Backend is live 🚀
```

---

## Cost Estimate (Render Pricing)

| Plan | RAM | CPU | Disk | Price/Month | Best For |
|------|-----|-----|------|-------------|----------|
| **Free** | 512 MB | 0.5 | 1GB | $0 | Testing/Demo |
| **Starter** | 512 MB | 0.5 | 10GB | $7 | Small projects |
| **Standard** | 2 GB | 1 | 10GB+ | $25 | Production (recommended) |
| **Pro** | 4 GB | 2 | 10GB+ | $85 | High traffic |

**Disk pricing**: $0.25/GB/month (beyond included amount)

**Recommendation for this project**: Standard plan with 20GB disk = ~$27.50/month

---

## Checklist

- [ ] Code pushed to GitHub
- [ ] Blueprint applied OR manual service created
- [ ] Environment variables set (API keys)
- [ ] Persistent disk attached (10GB+)
- [ ] Health check configured (`/api/health`)
- [ ] Deployment successful (check logs)
- [ ] Health check passing
- [ ] Research pack creation tested
- [ ] CORS configured for frontend domain (if applicable)
- [ ] Auto-deploy enabled (optional)

---

**Deployment complete!** Your backend is now live and ready to serve requests. 🎉
