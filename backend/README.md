# Northline — Backend

FastAPI API, LangGraph agents, memory, lessons, guardrails, and evals.

```powershell
cd backend
pip install -r requirements.txt
python run.py
```

On startup the API automatically warms MCP tools (Tavily, **AviationStack**, Weather). You do **not** need a third terminal for AviationStack.

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
