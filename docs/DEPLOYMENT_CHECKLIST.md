# Deployment Checklist - Render.com

Quick reference checklist for deploying the Agentic Quant backend to Render.com.

---

## Pre-Deployment

- [ ] All code committed to GitHub
  ```bash
  git status
  git add .
  git commit -m "Deploy to Render"
  git push origin main
  ```

- [ ] API keys ready:
  - [ ] `YOUCOM_API_KEY` (You.com)
  - [ ] `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
  - [ ] `POLYGON_API_KEY` (Polygon.io)

- [ ] `render.yaml` exists and is valid
- [ ] `requirements.txt` up to date

---

## Deployment Steps

### Option A: Blueprint (Recommended)

1. [ ] Go to [Render Dashboard](https://dashboard.render.com)
2. [ ] Click **"New +"** → **"Blueprint"**
3. [ ] Connect GitHub repository
4. [ ] Select branch: `main`
5. [ ] Click **"Apply"**
6. [ ] Wait for deployment (~2-5 minutes)

### Option B: Manual Web Service

1. [ ] Go to [Render Dashboard](https://dashboard.render.com)
2. [ ] Click **"New +"** → **"Web Service"**
3. [ ] Connect GitHub repository
4. [ ] Configure:
   - Name: `agentic-quant-backend`
   - Branch: `main`
   - Runtime: Python 3
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT`
5. [ ] Add persistent disk:
   - Name: `results-storage`
   - Mount: `/opt/render/project/src/results`
   - Size: 10GB+

---

## Post-Deployment

### Environment Variables

In Render dashboard, go to service → Environment:

- [ ] Add `YOUCOM_API_KEY=<your_key>`
- [ ] Add `ANTHROPIC_API_KEY=<your_key>` (or `OPENAI_API_KEY`)
- [ ] Add `POLYGON_API_KEY=<your_key>`
- [ ] Optional: `PYTHON_VERSION=3.11`

### Health Check

- [ ] Health check configured:
  - Path: `/api/health`
  - Interval: 30s
  - Timeout: 10s
  - Unhealthy Threshold: 3

### Verification

- [ ] Service is running (green status in dashboard)
- [ ] Health check passing:
  ```bash
  curl https://your-service.onrender.com/api/health
  # Expected: {"status": "ok", "version": "1.0.0"}
  ```

- [ ] Research pack creation works:
  ```bash
  curl -X POST https://your-service.onrender.com/api/research/packs \
    -H "Content-Type: application/json" \
    -d '{"query": "momentum trading", "n_results": 3}'
  ```

- [ ] Runs endpoint works:
  ```bash
  curl https://your-service.onrender.com/api/runs
  # Expected: {"runs": []}
  ```

---

## Frontend Integration (if applicable)

- [ ] Update CORS in `backend_api/main.py`:
  ```python
  allow_origins=[
      "http://localhost:3000",
      "http://localhost:5173",
      "https://your-frontend.vercel.app",  # Add your domain
  ]
  ```

- [ ] Redeploy backend after CORS update
- [ ] Update frontend API base URL to Render service URL

---

## Monitoring

- [ ] View logs in Render dashboard
- [ ] Check debug endpoints:
  - `/api/debug/requests` - Recent requests
  - `/api/debug/errors` - Recent errors

---

## Scaling (Optional)

Current plan: **Starter** (512 MB RAM, 0.5 CPU)

For production:
- [ ] Upgrade to **Standard** ($25/month, 2GB RAM, no spin-down)
- [ ] Increase disk if needed (20GB, 50GB, etc.)

---

## Troubleshooting

### Service won't start
- [ ] Check logs in Render dashboard
- [ ] Verify all API keys are set
- [ ] Verify build command succeeded

### 404 on all endpoints
- [ ] Check start command: `uvicorn backend_api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Verify working directory is `/opt/render/project/src/`

### Research pack creation fails (400)
- [ ] Verify `YOUCOM_API_KEY` is set
- [ ] Check logs for "YOUCOM_API_KEY not set" error

### Persistent disk not working
- [ ] Verify disk is mounted at `/opt/render/project/src/results`
- [ ] Check disk is attached in service settings

---

## Rollback

If deployment fails:

1. [ ] Go to Render dashboard
2. [ ] Select service → Rollbacks tab
3. [ ] Click **"Rollback"** on previous successful deployment

---

## Success Criteria

✅ Service is live and healthy
✅ All endpoints responding
✅ Research pack creation working
✅ Persistent disk saving data
✅ Environment variables set
✅ Logs showing no errors

---

**Deployment complete!** 🚀

Service URL: `https://agentic-quant-backend.onrender.com`

For detailed instructions, see: [DEPLOYMENT_RENDER.md](../DEPLOYMENT_RENDER.md)
