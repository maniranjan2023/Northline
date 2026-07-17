# Northline — Backend

FastAPI API, LangGraph agents, memory, lessons, guardrails, and evals.



```powershell
cd backend
# Use Python 3.11 or 3.12 (not 3.14) — same as Render runtime.txt
pip install -r requirements.txt
python run.py
```

### Render deploy notes

1. **Root Directory** = `Mcp-proj/backend` (or `backend` if that is the repo root)
2. **Python Version** = `3.12` (also set via `runtime.txt` → `python-3.12.8`)
3. **Build command** (main deps + AviationStack MCP + eval packages):

```bash
pip install -r requirements.txt && cd aviationstack-mcp-main && pip install -e . && cd .. && pip install -r requirements-evals.txt
```

4. **Start command** = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. **Frontend** on Vercel — set `VITE_API_BASE` to your Render URL.

On startup the API warms MCP tools (Tavily, AviationStack, Weather).

### Inngest (single Render web service)

Official Python pattern: `inngest.fast_api.serve` at **`/api/inngest`**.

After deploy, sync in [Inngest Cloud](https://app.inngest.com):

```
https://<your-render-app>.onrender.com/api/inngest
```

| Env var | Purpose |
|---------|---------|
| `INNGEST_EVENT_KEY` | Send events (Admin manual trigger) |
| `INNGEST_SIGNING_KEY` | Secure `/api/inngest` sync |
| `INNGEST_DEV=1` | Local Dev Server only — **never on Render** |

Daily crons (Asia/Kolkata):

| Suite | Time | Event (manual) |
|-------|------|----------------|
| CI (3) | 12:00 | `evals/ci.run` |
| Single-turn (5) | 18:00 | `evals/single_turn.run` |
| Multi-turn (5) | 22:00 | `evals/multi_turn.run` |
| All 13 | — | `evals/all.run` |

**Local:**

```powershell
# Terminal A — API + Inngest serve
$env:INNGEST_DEV=1; uvicorn app.main:app --reload --port 8000

# Terminal B — Inngest Dev Server
inngest dev -u http://localhost:8000/api/inngest
```

Admin → Evals polls Postgres (`eval_jobs`) for live progress.

**One-time AviationStack MCP setup** (inside backend):

```powershell
cd backend\aviationstack-mcp-main
uv sync
```

Or without uv: `pip install -r requirements.txt` inside that folder.

Tests:

```powershell
cd backend
python -m pytest tests evals/test_ci.py -q
```

Core layout:

```
backend/
├── app/              # FastAPI routes + services
├── graph/            # LangGraph pipeline
├── memory/           # Mem0 + Postgres checkpoint state
├── lessons/          # Evidence-backed lesson book
├── guardrails/       # NeMo input/output safety
├── evals/            # DeepEval + CI suites
├── tests/            # Unit tests
├── aviationstack-mcp-main/  # AviationStack MCP (auto-started with API)
├── main.py           # CLI entry + graph helpers
├── run.py            # API server entry
└── requirements.txt
```

Environment:

```powershell
copy .env.example .env     # backend secrets → backend/.env
```

```powershell
cd ../frontend
copy .env.example .env     # frontend config → frontend/.env
```

Legacy: a repo-root `.env` still works as a fallback for unset backend keys.
