# PHASE 4 TECHNICAL SPECIFICATION
## Production Deployment, CI/CD, Observability & Cost Tracking
### File-by-File, Function-by-Function Blueprint for Execution Agent

---

## 0. STRATEGIC CONTEXT

### What This Phase Covers
Phases 1-3 produced a fully functional, locally-demoable system. Phase 4 takes it to production-ready:

1. **Google Cloud Run deployment** for both backends (per PRD prerequisites)
2. **Vercel/Netlify deployment** for all three frontends (launcher, safe-harbor, shield-wall)
3. **GitHub Actions CI/CD** — automated test + build + deploy on push to `main`
4. **Observability** — structured logging, error tracking, request tracing
5. **Cost tracking** — per-generation API cost logging (the "eight cents" number from the PRD must be verifiable)
6. **Environment management** — proper secrets handling, staging vs production configs
7. **Health checks and monitoring endpoints**

### What This Phase Does NOT Cover
- Authentication/authorization (separate enterprise feature, not demo scope)
- Database migration (still in-memory for demo; production would need Redis/Postgres)
- Auto-scaling policies (Cloud Run handles this natively)
- IC Memo Synthesizer (KILLED)

### Why This Matters for the Pitch
Peter (CEO) will ask: "Can I deploy this today?" The answer must be yes. Aleks (CTO) will ask: "How does it run in production?" The answer must be: structured logs, health checks, cost tracking, and a CI/CD pipeline — not "run docker compose on my laptop."

---

## 1. DIRECTORY STRUCTURE (additions only)

```
tracelight-safe-harbor/
├── .github/
│   └── workflows/
│       ├── ci.yml                       # Test + lint on every PR
│       └── deploy.yml                   # Build + deploy to Cloud Run on merge to main
├── infra/
│   ├── cloudbuild-safe-harbor.yaml      # Cloud Build config for safe-harbor backend
│   ├── cloudbuild-shield-wall.yaml      # Cloud Build config for shield-wall backend
│   └── env/
│       ├── staging.env                  # Staging environment variables (no secrets)
│       └── production.env               # Production environment variables (no secrets)
├── safe-harbor/
│   ├── backend/
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── logging_middleware.py    # Structured JSON request logging
│   │   │   └── cost_tracker.py         # Per-request API cost aggregation
│   │   └── health.py                   # Health check endpoint
│   └── Dockerfile                      # Updated for production (multi-stage)
├── shield-wall/
│   ├── backend/
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── logging_middleware.py
│   │   │   └── cost_tracker.py
│   │   └── health.py
│   └── Dockerfile                      # Updated for production
└── vercel.json                         # Vercel config for frontend deployments
```

---

## 2. STRUCTURED LOGGING — `backend/middleware/logging_middleware.py`

Identical implementation for both Safe-Harbor and Shield-Wall backends.

### Purpose
Replace all `print()` statements with structured JSON logging. Every request and agent invocation gets a trace ID.

### Implementation

```python
import logging
import uuid
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())[:8]
        request.state.trace_id = trace_id
        start = time.time()

        logger = logging.getLogger("tracelight")
        logger.info(json.dumps({
            "event": "request_start",
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
        }))

        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        logger.info(json.dumps({
            "event": "request_end",
            "trace_id": trace_id,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }))

        response.headers["X-Trace-ID"] = trace_id
        return response
```

### Integration
Add to both `main.py` files:
```python
from backend.middleware.logging_middleware import StructuredLoggingMiddleware
app.add_middleware(StructuredLoggingMiddleware)
```

### Logger Setup
Configure at app startup:
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # JSON-only output for Cloud Run log aggregation
)
```

---

## 3. COST TRACKER — `backend/middleware/cost_tracker.py`

### Purpose
Track actual API costs per pipeline execution. This is critical for the pitch — Peter needs the "eight cents per generation" number backed by real data.

### Pydantic Model

```python
class APICostEntry(BaseModel):
    agent: str                    # "schema_extractor", "synthetic_gen", etc.
    model: str                    # "gpt-4o", "gemini-2.0-flash"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float     # calculated from token pricing
    timestamp: str
```

### Pricing Table (hardcoded, update as needed)

```python
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    "text-embedding-3-small": {"input": 0.02 / 1_000_000, "output": 0.0},
}
```

### Function: `calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float`

Returns estimated USD cost.

### Function: `log_cost(agent: str, model: str, usage: TokenUsage) -> APICostEntry`

Creates an `APICostEntry` and appends it to the job's audit log.

### Integration (Safe-Harbor)
After each agent call in `orchestrator.py`, call `log_cost()`:
```python
# After schema extraction:
cost_tracker.log_cost("schema_extractor", settings.gemini_model, schema_response_usage)
# After synthetic generation:
cost_tracker.log_cost("synthetic_gen", settings.gpt4o_model, gen_response_usage)
```

### Integration (Shield-Wall)
After each agent call:
```python
cost_tracker.log_cost("telemetry_agent", settings.gpt4o_model, telemetry_usage)
cost_tracker.log_cost("synthesis_agent", settings.gpt4o_model, synthesis_usage)
cost_tracker.log_cost("policy_embeddings", "text-embedding-3-small", embedding_usage)
```

### API Endpoint
Add to both `main.py`:
```
GET /api/costs/{job_id}
```
Returns:
```json
{
    "job_id": "...",
    "entries": [APICostEntry, ...],
    "total_cost_usd": 0.082
}
```

---

## 4. HEALTH CHECK — `backend/health.py`

### Purpose
Cloud Run and Docker Compose health checks hit this endpoint.

### Implementation

```python
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "<safe-harbor|shield-wall>",
        "version": "1.0.0",
    }
```

### Integration
```python
from backend.health import router as health_router
app.include_router(health_router)
```

### Docker Compose Update
Change healthcheck from `curl /docs` to `curl /health`.

---

## 5. PRODUCTION DOCKERFILES (multi-stage)

### `safe-harbor/Dockerfile`

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY backend/ ./backend/
COPY templates/ ./templates/
EXPOSE 8000
ENV PORT=8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `shield-wall/Dockerfile`

Same pattern but with:
```
COPY data/ ./data/
EXPOSE 8001
ENV PORT=8001
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## 6. GITHUB ACTIONS — CI

### `.github/workflows/ci.yml`

**Trigger:** On every PR to `main`, and on push to `main`.

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-safe-harbor:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: safe-harbor
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pip install pytest
      - run: python -m pytest tests/ -v --tb=short

  test-shield-wall:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: shield-wall
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio
      - run: python -m pytest tests/ -v --tb=short

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check safe-harbor/backend/ shield-wall/backend/ --select E,F,W --ignore E501
```

---

## 7. GITHUB ACTIONS — DEPLOY

### `.github/workflows/deploy.yml`

**Trigger:** On push to `main` (after CI passes).

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-safe-harbor:
    runs-on: ubuntu-latest
    needs: [] # Can add CI job dependency
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud builds submit safe-harbor/ \
            --config=infra/cloudbuild-safe-harbor.yaml \
            --project=${{ secrets.GCP_PROJECT_ID }}

  deploy-shield-wall:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud builds submit shield-wall/ \
            --config=infra/cloudbuild-shield-wall.yaml \
            --project=${{ secrets.GCP_PROJECT_ID }}

  deploy-frontends:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_SAFE_HARBOR }}
          working-directory: safe-harbor/frontend
```

---

## 8. CLOUD BUILD CONFIGS

### `infra/cloudbuild-safe-harbor.yaml`

```yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args:
      - build
      - -t
      - gcr.io/$PROJECT_ID/safe-harbor-backend:$COMMIT_SHA
      - -t
      - gcr.io/$PROJECT_ID/safe-harbor-backend:latest
      - .

  - name: gcr.io/cloud-builders/docker
    args: [push, gcr.io/$PROJECT_ID/safe-harbor-backend:$COMMIT_SHA]

  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    entrypoint: gcloud
    args:
      - run
      - deploy
      - safe-harbor-backend
      - --image=gcr.io/$PROJECT_ID/safe-harbor-backend:$COMMIT_SHA
      - --region=europe-west1
      - --platform=managed
      - --allow-unauthenticated
      - --memory=1Gi
      - --cpu=1
      - --max-instances=3
      - --set-env-vars=OPENAI_API_KEY=$$OPENAI_API_KEY,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=europe-west1

images:
  - gcr.io/$PROJECT_ID/safe-harbor-backend:$COMMIT_SHA
  - gcr.io/$PROJECT_ID/safe-harbor-backend:latest
```

### `infra/cloudbuild-shield-wall.yaml`

Same pattern, service name `shield-wall-backend`, port 8001.

---

## 9. ENVIRONMENT CONFIGS

### `infra/env/staging.env`

```
SAFE_HARBOR_BACKEND_URL=https://safe-harbor-staging-xxxxx-ew.a.run.app
SHIELD_WALL_BACKEND_URL=https://shield-wall-staging-xxxxx-ew.a.run.app
DEMO_MODE=true
```

### `infra/env/production.env`

```
SAFE_HARBOR_BACKEND_URL=https://safe-harbor-xxxxx-ew.a.run.app
SHIELD_WALL_BACKEND_URL=https://shield-wall-xxxxx-ew.a.run.app
DEMO_MODE=true
```

### Frontend Environment Handling

Each frontend needs to read the backend URL from environment. Add to each frontend's `src/config.js`:

```javascript
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
export const WS_BASE = API_BASE.replace('http', 'ws');
```

Replace all hardcoded `http://localhost:8000` and `http://localhost:8001` references in:
- `safe-harbor/frontend/src/components/UploadZone.jsx`
- `safe-harbor/frontend/src/components/AuditTrail.jsx`
- `safe-harbor/frontend/src/components/VerdictBadge.jsx`
- `safe-harbor/frontend/src/App.jsx`
- `safe-harbor/frontend/src/hooks/useWebSocket.js`
- `shield-wall/frontend/src/components/QuestionnaireUpload.jsx`
- `shield-wall/frontend/src/components/ExportPanel.jsx`
- `shield-wall/frontend/src/App.jsx`
- `shield-wall/frontend/src/hooks/useWebSocket.js`
- `launcher/src/App.jsx`

Pattern:
```javascript
// Before:
fetch('http://localhost:8000/api/upload', ...)
// After:
import { API_BASE } from '../config';
fetch(`${API_BASE}/api/upload`, ...)
```

For WebSocket:
```javascript
// Before:
new WebSocket(`ws://localhost:8000/ws/${jobId}`)
// After:
import { WS_BASE } from '../config';
new WebSocket(`${WS_BASE}/ws/${jobId}`)
```

For launcher links:
```javascript
const SAFE_HARBOR_URL = import.meta.env.VITE_SAFE_HARBOR_URL || 'http://localhost:5174';
const SHIELD_WALL_URL = import.meta.env.VITE_SHIELD_WALL_URL || 'http://localhost:5175';
```

---

## 10. CORS UPDATE FOR PRODUCTION

Both `main.py` files must accept the deployed frontend origins:

```python
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    os.getenv("FRONTEND_ORIGIN", ""),
]
# Filter empty strings
allowed_origins = [o for o in allowed_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 11. `print()` → `logger` REPLACEMENT

### Scope
Replace all `print()` calls across both backends with proper `logging.getLogger(__name__)` calls.

**Files to modify (Safe-Harbor):**
- `backend/agents/schema_extractor.py` — `logger.warning` / `logger.info`
- `backend/orchestrator.py` — already uses audit log, just add logger

**Files to modify (Shield-Wall):**
- `backend/agents/questionnaire_parser.py` — `logger.warning`
- `backend/agents/telemetry_agent.py` — `logger.error`
- `backend/agents/synthesis_agent.py` — `logger.error`
- `backend/policy_store/indexer.py` — `logger.error`
- `backend/policy_store/retriever.py` — `logger.error`
- `backend/parsers/pdf_parser.py` — `logger.error`
- `backend/parsers/text_parser.py` — `logger.error`

Pattern:
```python
# Before:
print(f"Error: {e}")
# After:
import logging
logger = logging.getLogger(__name__)
logger.error(f"Error: {e}")
```

---

## 12. VERCEL CONFIG — `vercel.json`

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite"
}
```

Each frontend (launcher, safe-harbor/frontend, shield-wall/frontend) gets its own Vercel project. The `vercel.json` goes in each frontend's root.

---

## 13. BUILD ORDER

```
Step 1:  Health check endpoints (both backends) — no deps
Step 2:  Structured logging middleware (both backends) — no deps
Step 3:  Cost tracker middleware (both backends) — depends on Pydantic schemas
Step 4:  Replace all print() with logger (both backends)
Step 5:  Frontend config.js — extract hardcoded URLs
Step 6:  CORS update for production origins
Step 7:  Production Dockerfiles (multi-stage)
Step 8:  Cloud Build configs
Step 9:  GitHub Actions CI workflow
Step 10: GitHub Actions Deploy workflow
Step 11: Environment configs (staging + production)
Step 12: vercel.json for frontends
Step 13: docker-compose.yml healthcheck update (/health)
Step 14: Cost endpoint + frontend cost display in Audit Trail
```

Steps 1-4 are independent within each service — run in parallel.
Step 5 is independent of backend work.
Steps 7-12 are independent — run in parallel.

---

## 14. TESTS — Phase 4

### `safe-harbor/tests/test_health.py`
- `GET /health` returns 200 with status "healthy".

### `safe-harbor/tests/test_cost_tracker.py`
- Test: `calculate_cost("gpt-4o", 3000, 5000)` returns approximately $0.0575.
- Test: `calculate_cost("gemini-2.0-flash", 4000, 2000)` returns approximately $0.0012.
- Test: `log_cost()` creates a valid `APICostEntry`.

### `shield-wall/tests/test_health.py`
- Same as Safe-Harbor.

---

## 15. CRITICAL BOUNDARIES

- **No new AI agents or features.** Phase 4 is infrastructure only.
- **No authentication.** The demo is unauthenticated. Enterprise auth is a separate workstream.
- **No database.** Job state stays in-memory. Production persistence (Redis/Postgres) is out of scope.
- **Secrets go in GitHub Secrets / GCP Secret Manager.** NEVER in env files or code.
- **The `.env.example` at repo root stays as a template.** The actual `.env` is `.gitignore`d.
- **IC Memo Synthesizer is KILLED.** Do not build.
- **The cost tracker is for OBSERVABILITY, not billing.** It logs estimates, not invoices.

---

*End of Phase 4 Technical Specification.*
