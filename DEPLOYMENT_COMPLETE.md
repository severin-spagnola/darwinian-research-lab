# Deployment Setup - Complete ✅

**Date:** 2026-02-06
**Status:** Ready to Deploy
**Platform:** Render.com (Monorepo Web Service)

---

## Overview

Your Agentic Quant backend is now configured for deployment to Render.com as a monorepo web service. All necessary files and documentation are in place.

---

## What Was Created

### 1. Render Blueprint Configuration

**File:** [render.yaml](render.yaml)

Defines your web service infrastructure:
- **Service Type:** Web (FastAPI backend)
- **Runtime:** Python 3.11
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT`
- **Persistent Disk:** 10GB at `/opt/render/project/src/results`
- **Health Check:** `/api/health` every 30s
- **Auto-Deploy:** Enabled on push to `main`

### 2. Deployment Documentation

**File:** [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md)

Comprehensive guide covering:
- Prerequisites (API keys, GitHub repo)
- Two deployment methods (Blueprint vs Manual)
- Environment variable setup
- Persistent storage configuration
- Post-deployment verification
- CORS configuration for frontend
- Monitoring and debugging
- Scaling options and pricing
- Troubleshooting common issues
- Security notes

### 3. Quick Reference Checklist

**File:** [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md)

Step-by-step checklist format:
- Pre-deployment tasks
- Deployment steps (both Blueprint and Manual)
- Post-deployment verification
- Frontend integration
- Monitoring setup
- Troubleshooting guide
- Rollback instructions

### 4. Environment Variables Template

**File:** [.env.example](.env.example)

Updated with all required keys:
- `YOUCOM_API_KEY` - Research layer (You.com)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` - LLM provider
- `POLYGON_API_KEY` - Market data
- Documentation for each key

---

## Deployment Options

### Option 1: Blueprint (Recommended)

**Fastest and easiest** - Infrastructure as Code approach:

1. Push code to GitHub
2. Create Blueprint on Render dashboard
3. Connect your GitHub repository
4. Select `main` branch
5. Render auto-detects `render.yaml` and provisions everything
6. Add environment variables (API keys)
7. Done! ✅

**Time:** ~5 minutes

### Option 2: Manual Setup

**More control** - Configure each setting manually:

1. Create Web Service on Render dashboard
2. Configure build/start commands
3. Add persistent disk manually
4. Set environment variables
5. Configure health check

**Time:** ~10 minutes

---

## What Gets Deployed

### Backend API (FastAPI)

- **Port:** 8050 (or $PORT from Render)
- **Endpoints:**
  - Core: `/api/runs`, `/api/runs/{runId}`, `/api/runs/{runId}/graphs/{graphId}`, etc.
  - Research: `/api/research/packs`, `/api/runs/{runId}/memos/{graphId}`, `/api/runs/{runId}/verdicts/{graphId}`
  - Health: `/api/health`
  - Debug: `/api/debug/requests`, `/api/debug/errors`

### Persistent Storage

**Mount Point:** `/opt/render/project/src/results`
**Size:** 10GB (configurable in `render.yaml`)

**Stores:**
```
results/
├── research_packs/        # Global research packs
├── research_cache/        # You.com API cache
└── runs/{run_id}/
    ├── summary.json
    ├── run_config.json
    ├── lineage.jsonl
    ├── graphs/
    ├── evals/
    ├── phase3_reports/
    ├── blue_memos/        # Research layer
    ├── red_verdicts/      # Research layer
    └── llm_transcripts/
```

---

## Required Environment Variables

You must set these in the Render dashboard after deployment:

| Variable | Required | Purpose |
|----------|----------|---------|
| `YOUCOM_API_KEY` | **Yes** | Research pack creation via You.com |
| `ANTHROPIC_API_KEY` | **Yes*** | Claude API for LLM mutations |
| `OPENAI_API_KEY` | **Yes*** | OpenAI API for LLM mutations |
| `POLYGON_API_KEY` | **Yes** | Market data fetching |

**Note:** You only need ONE of `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (not both).

---

## Next Steps

### 1. Push to GitHub

```bash
git status
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Deploy on Render

Follow the guide in [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md) or the checklist in [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md).

**Quick start (Blueprint method):**

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. New + → Blueprint
3. Connect GitHub repo
4. Select `main` branch
5. Click "Apply"
6. Add environment variables (API keys)

### 3. Verify Deployment

Once live, test your backend:

```bash
# Health check
curl https://your-service.onrender.com/api/health

# Create research pack
curl -X POST https://your-service.onrender.com/api/research/packs \
  -H "Content-Type: application/json" \
  -d '{"query": "momentum trading strategies", "n_results": 3}'

# List runs
curl https://your-service.onrender.com/api/runs
```

### 4. Configure Frontend (if applicable)

Update your frontend's API base URL to point to your Render service:

```typescript
const API_BASE_URL = "https://your-service.onrender.com";
```

And update CORS in `backend_api/main.py` to allow your frontend domain:

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "https://your-frontend.vercel.app",  # Add this
]
```

---

## Documentation Reference

| Document | Purpose |
|----------|---------|
| [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md) | Complete deployment guide |
| [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) | Step-by-step checklist |
| [render.yaml](render.yaml) | Infrastructure as Code config |
| [.env.example](.env.example) | Environment variable template |
| [docs/HACKATHON_RESEARCH_LAYER.md](docs/HACKATHON_RESEARCH_LAYER.md) | Backend API documentation |
| [FRONTEND_IMPLEMENTATION_GUIDE.md](FRONTEND_IMPLEMENTATION_GUIDE.md) | Frontend integration guide |
| [docs/DATA_STRUCTURES.md](docs/DATA_STRUCTURES.md) | API payload reference |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Repository                       │
│                    (agentic_quant backend)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ git push
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Render.com                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            Web Service (FastAPI)                    │    │
│  │  • Python 3.11                                      │    │
│  │  • uvicorn backend_api.main:app                     │    │
│  │  • Port: 8050                                       │    │
│  │  • Health check: /api/health                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │       Persistent Disk (10GB)                        │    │
│  │  /opt/render/project/src/results                    │    │
│  │  • Research packs                                   │    │
│  │  • You.com cache                                    │    │
│  │  • Run artifacts                                    │    │
│  │  • Blue Memos / Red Verdicts                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Optional)                       │
│              (Vercel, Netlify, or other)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Cost Estimate

### Free Tier (Starter)
- **RAM:** 512 MB
- **CPU:** 0.5
- **Disk:** 1 GB included
- **Cost:** $0/month
- **Limitation:** Spins down after 15 min inactivity

### Recommended (Standard)
- **RAM:** 2 GB
- **CPU:** 1
- **Disk:** 10 GB included
- **Cost:** $25/month
- **Benefit:** No spin-down, better performance

**Disk pricing:** $0.25/GB/month beyond included amount

**Total for Standard + 20GB disk:** ~$27.50/month

---

## Support

### Render Issues
- [Render Documentation](https://render.com/docs)
- [Render Community](https://community.render.com)

### Backend Issues
- Check logs: `/api/debug/errors`
- Review docs: [docs/HACKATHON_RESEARCH_LAYER.md](docs/HACKATHON_RESEARCH_LAYER.md)
- Test locally: `uvicorn backend_api.main:app --reload`

---

## Status

✅ Render configuration complete
✅ Documentation complete
✅ Environment variables documented
✅ Health check endpoint configured
✅ Persistent storage configured
✅ Auto-deploy enabled
✅ Ready for deployment

**All set!** Follow [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md) to deploy. 🚀
