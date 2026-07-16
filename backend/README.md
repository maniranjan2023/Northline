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
3. **Build Command** (main deps **plus** AviationStack MCP):

```bash
pip install -r requirements.txt && pip install ./aviationstack-mcp-main
```

To enable **Admin → Evals → Run** on Render, append evals packages (install last, avoids resolution-too-deep):

```bash
pip install -r requirements.txt && pip install ./aviationstack-mcp-main && pip install -r requirements-evals.txt
```

4. **Start Command** = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Do **not** use `requirements-dev.txt` on Render for that optional step — it re-includes all production deps and can trigger `resolution-too-deep`. Use `requirements-evals.txt` instead.

| What | Needed on Render? | Why |
|------|-------------------|-----|
| `pip install -r requirements.txt` | **Yes** | FastAPI, LangGraph, Mem0, NeMo, etc. |
| `pip install ./aviationstack-mcp-main` | **Yes** | Flight agent runs `python -m aviationstack_mcp mcp run` |
| Weather MCP | **No separate install** | `custom_weather_mcp_server.py` is started from the same env |
| Tavily MCP | **No install** | Remote HTTP MCP (only needs `TAVILY_API_KEY`) |

On startup the API automatically warms MCP tools (Tavily, **AviationStack**, Weather). You do **not** need a third terminal for AviationStack.

### Inngest (scheduled + manual evals)

Endpoint: `https://<your-backend>/api/inngest`

| Env var | Where | Purpose |
|---------|--------|---------|
| `INNGEST_EVENT_KEY` | Render + local Cloud | Send events (manual Admin trigger) |
| `INNGEST_SIGNING_KEY` | Render + local Cloud | Secure sync with Inngest Cloud |
| `INNGEST_DEV=1` | Local only | Talk to Inngest Dev Server — **never set on Render** |

Daily crons (Asia/Kolkata):

| Suite | Time | Trigger event (manual) |
|-------|------|------------------------|
| CI (3) | 12:00 | `evals/ci.run` |
| Single-turn (5) | 18:00 | `evals/single_turn.run` |
| Multi-turn (5) | 22:00 | `evals/multi_turn.run` |
| All 13 | — | `evals/all.run` (manual only) |

After deploy: add the app URL in Inngest Cloud → sync `https://northline-y6rd.onrender.com/api/inngest`.

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
