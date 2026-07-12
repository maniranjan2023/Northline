# Voyager AI — Evaluation Framework

Interview-ready eval suite for the LangGraph travel planner. Measures **safety**, **single-turn agent quality**, and **multi-turn memory** using **DeepEval** (official metrics) plus **custom deterministic checks**.

---

## Why we eval (30-second pitch)

> "Voyager runs 6 agents and 3 MCP tools. A single bad release can leak PII, route a greeting into a full graph run, or forget a user's vegetarian preference. We run **13 evals** in three schedules: **CI on every PR** (guardrails + router, ~2 min), **nightly** (5 DeepEval agent metrics on real trip planning), and **weekly** (5 DeepEval conversation metrics on follow-ups and Mem0). Results append to Markdown logs so we can debug without a dashboard during development."

---

## Folder structure

```
evals/
├── README.md                 ← You are here (why / what / how)
├── conftest.py               ← Pytest hooks → flush results to .md
├── test_ci.py                ← Suite 1: custom (PR)
├── test_nightly.py           ← Suite 2: single-turn DeepEval (daily)
├── test_memory.py            ← Suite 3: multi-turn DeepEval (weekly)
├── datasets/
│   ├── golden_ci.json        ← Test inputs for CI
│   ├── golden_nightly.json   ← Test inputs for nightly
│   └── golden_memory.json    ← Test inputs for memory
├── helpers/
│   ├── datasets.py           ← Load golden JSON
│   ├── graph_runner.py       ← Invoke LangGraph for evals
│   └── judge.py              ← Groq judge for DeepEval metrics
├── reporting/
│   └── write_results.py      ← Append results to Markdown
└── results/
    ├── custom.md             ← CI results (append-only)
    ├── single_turn.md        ← Nightly results
    └── multi_turn.md         ← Memory results
```

---

## 13 eval metrics

### Suite 1 — Custom (CI, every PR)

| Metric | Type | Why | How |
|--------|------|-----|-----|
| **Guardrail alignment** | Custom | Block harmful input before agents; allow real travel queries | `guardrails.pipeline.check_input()` |
| **Prompt injection block** | Custom | Stop jailbreak / override attacks | Regex fast-path + NeMo guardrails |
| **Router intent** | Custom | Don't run 6 agents on "Hello" or skip planning on "Plan Tokyo" | `chat_router.classify_message()` |

**Golden file:** `datasets/golden_ci.json` (3 sections: `guardrails`, `injection`, `router`)

---

### Suite 2 — Single-turn (Nightly, daily)

| Metric | DeepEval doc | Why | How |
|--------|--------------|-----|-----|
| **Task Completion** | [link](https://deepeval.com/docs/metrics-task-completion) | Did user get a full itinerary? | `@observe` + full LangGraph trace |
| **Tool Correctness** | [link](https://deepeval.com/docs/metrics-tool-correctness) | Right MCP per agent? | `LLMTestCase` + `expected_tools` |
| **Plan Adherence** | [link](https://deepeval.com/docs/metrics-plan-adherence) | Did execution follow planner brief? | Trace-only metric |
| **Plan Quality** | [link](https://deepeval.com/docs/metrics-plan-quality) | Was the plan itself good? | Trace-only metric |
| **Argument Correctness** | [link](https://deepeval.com/docs/metrics-argument-correctness) | Correct tool args (e.g. city for weather)? | `LLMTestCase` + `tools_called` |

**Golden file:** `datasets/golden_nightly.json`

---

### Suite 3 — Multi-turn (Weekly)

| Metric | DeepEval doc | Why | How |
|--------|--------------|-----|-----|
| **Knowledge Retention** | [link](https://deepeval.com/docs/metrics-knowledge-retention) | Don't re-ask vegetarian / budget | `ConversationalTestCase` |
| **Turn Relevancy** | [link](https://deepeval.com/docs/metrics-turn-relevancy) | Follow-up answers the question | Multi-turn turns |
| **Turn Faithfulness** | [link](https://deepeval.com/docs/metrics-turn-faithfulness) | No invented hotels/flights | `retrieval_context` = plan + Mem0 |
| **Turn Contextual Recall** | [link](https://deepeval.com/docs/metrics-turn-contextual-recall) | Context had enough for expected answer | + `expected_outcome` |
| **Goal Accuracy** | [link](https://deepeval.com/docs/metrics-goal-accuracy) | User goal met across turns | Full conversation |

**Golden file:** `datasets/golden_memory.json`

---

## CLI commands

### 1. Custom (CI) — no live graph

```bash
pytest evals/test_ci.py -v
```

Runs guardrails (needs `GROQ_API_KEY` for allow-list cases), injection regex cases, and router (always runs).

**Results →** `evals/results/custom.md`

---

### 2. Single-turn (Nightly) — live graph + MCP

```bash
# Terminal 1: Aviation MCP (if not already running)
cd aviationstack-mcp-main
python -m aviationstack_mcp mcp run

# Terminal 2: run evals
set EVAL_LIVE=1
deepeval test run evals/test_nightly.py --verbose
```

Requires: `GROQ_API_KEY`, `DATABASE_URL`, `TAVILY_API_KEY`, `AVIATIONSTACK_API_KEY`, `OPENWEATHER_API_KEY`

**Results →** `evals/results/single_turn.md`

---

### 3. Multi-turn (Memory) — live graph + Mem0

```bash
set EVAL_LIVE=1
deepeval test run evals/test_memory.py --verbose
```

Requires all nightly keys + `MEM0_API_KEY`. Mem0 cases wait ~15s after session 1 for indexing.

**Results →** `evals/results/multi_turn.md`

---

## Result Markdown format

Each CLI run **appends** a dated section:

```markdown
## Run: 2026-07-13 01:45:00 IST | Suite: CI (custom) | Pass: 16/16

| Eval Metric | Case | Result | Score | Threshold | Reason |
|-------------|------|--------|-------|-----------|--------|
| Router intent | route_new_plan_tokyo | PASS | — | — | actual=new_plan, expected=new_plan |
```

- **Custom checks:** no score column (PASS/FAIL + reason)
- **DeepEval:** score, threshold, LLM judge reason (`include_reason=True`)

**Dev extras:** `deepeval inspect` (terminal TUI) · optional `deepeval login` + `deepeval view` (Confident AI browser)

---

## Golden datasets explained

| File | What it stores | What it is NOT |
|------|----------------|----------------|
| `golden_ci.json` | Inputs + expected blocked/intent | Not eval scores |
| `golden_nightly.json` | Trip prompts + expected MCP tools | Not the itinerary text |
| `golden_memory.json` | Multi-turn scripts + expected_outcome | Not Mem0 API responses |

Goldens are **version-controlled test cases**. Results live only in `results/*.md`.

---

## Schedule (recommended CI/CD)

| Suite | When | Command | ~Time |
|-------|------|---------|-------|
| Custom | Every PR | `pytest evals/test_ci.py` | ~2 min |
| Single-turn | Daily cron | `EVAL_LIVE=1 deepeval test run evals/test_nightly.py` | 15–30 min |
| Multi-turn | Weekly cron | `EVAL_LIVE=1 deepeval test run evals/test_memory.py` | ~20 min |

---

## Environment variables

```env
# DeepEval judge + app LLM (all 10 metrics use Groq — no OPENAI_API_KEY needed)
GROQ_API_KEY=...
DEEPEVAL_JUDGE_MODEL=llama-3.3-70b-versatile

# Required for nightly/memory (EVAL_LIVE=1)
DATABASE_URL=...
TAVILY_API_KEY=...
AVIATIONSTACK_API_KEY=...
OPENWEATHER_API_KEY=...

# Memory suite
MEM0_API_KEY=...
MEM0_ENABLED=true

# Optional
EVAL_LIVE=1              # Enable graph evals (skip if unset)
EVAL_THRESHOLD=0.7       # DeepEval pass threshold (nightly default 0.7)
```

---

## Architecture diagram

```
User golden JSON
       │
       ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  test_ci.py  │────▶│ guardrails /    │────▶│ results/custom.md│
│  (PR)        │     │ chat_router     │     └──────────────────┘
└──────────────┘     └─────────────────┘

┌──────────────┐     ┌─────────────────┐     ┌──────────────────────┐
│test_nightly  │────▶│ LangGraph + MCP │────▶│ results/single_turn  │
│  (daily)     │     │ + DeepEval x5   │     └──────────────────────┘
└──────────────┘     └─────────────────┘

┌──────────────┐     ┌─────────────────┐     ┌──────────────────────┐
│ test_memory  │────▶│ Graph + follow- │────▶│ results/multi_turn   │
│  (weekly)    │     │ up + Mem0 x5    │     └──────────────────────┘
└──────────────┘     └─────────────────┘
```

---

## Interview Q&A

**Q: Why DeepEval and not only LangSmith?**  
A: DeepEval gives named agent/conversation metrics with thresholds and reasons. LangSmith traces production runs; we can bridge scores later with `create_feedback()`.

**Q: Why three golden files?**  
A: Different suites, different cost. CI must be fast and deterministic. Nightly/memory need live MCP and cost API credits.

**Q: Why Markdown results?**  
A: Zero setup for dev — git-diffable history, no Confident AI account required. Good for demos and PR artifacts.

**Q: Task Completion vs Plan Adherence?**  
A: [Official distinction](https://deepeval.com/docs/metrics-task-completion): Task Completion = **outcome** (did we deliver the trip?). Plan Adherence = **process** (did agents follow the planner's plan?).

**Q: Why `EVAL_LIVE=1` gate?**  
A: Prevents accidental 30-minute MCP runs on every `pytest` invocation during local dev.

---

## Adding a new test case

1. Add entry to the right `datasets/golden_*.json` with unique `"id"`.
2. Run the suite CLI command.
3. Check appended section in `results/*.md`.
4. If nightly: ensure `expected_tools` matches MCP names (`tavily_search`, `list_airports`, `get_current_weather`, etc.).

---

## Dependencies

```bash
pip install deepeval pytest
```

See root `requirements.txt` for full project deps.
