# Voyager AI — Multi-Agent Travel Planning with LangGraph + MCP + Memory

**Voyager AI** is a production-style AI travel planner: **6 specialist LangGraph agents** call **real-world tools** via **MCP** (Tavily, AviationStack, Weather), personalize trips with **dual-layer memory** (Postgres + Mem0), enforce **NeMo Guardrails** on every message, trace runs in **LangSmith**, and validate quality with **13 DeepEval metrics** across CI, nightly, and weekly suites.

> **One-line pitch:** *Multi-agent LangGraph app with MCP tools, two-tier memory, input/output guardrails, LangSmith tracing, and a 13-metric eval framework — not just a chatbot demo.*

---

## At a Glance — What Makes This Project Stand Out

| Pillar | Technology | What it does | Deep-dive |
|--------|------------|--------------|-----------|
| **Multi-agent planning** | LangGraph + Groq | 6 sequential agents (planner → research → hotel → flight → activity → itinerary) orchestrated as a `StateGraph` | [Agent pipeline](#langgraph-agent-pipeline) |
| **Tool integration (MCP)** | Tavily, AviationStack, custom Weather | Agents call live APIs through remote HTTP + local stdio MCP servers | [MCP integration](#mcp-integration-remote-local-custom) |
| **Memory** | PostgresSaver + Mem0 | **Short-term:** full trip state per session (`thread_id`). **Long-term:** user preferences across sessions (`user_id`) | [`memory/README.md`](memory/README.md) |
| **Safety (Guardrails)** | NeMo + Groq 8B | Regex, PII detection, Colang flows, and LLM self-check on **input and output** — blocked messages never hit agents | [`guardrails/README.md`](guardrails/README.md) |
| **Observability** | LangSmith | Every graph node, LLM call, `user_id`, and `thread_id` traced for debugging and demos | [`docs/LANGSMITH.md`](docs/LANGSMITH.md) |
| **Evaluations** | DeepEval + pytest | **13 metrics** in 3 suites: CI (safety/router), nightly (agent quality), weekly (multi-turn memory) | [`evals/README.md`](evals/README.md) |

**End-to-end flow in one sentence:** User chats in Streamlit → guardrails check input → router picks greeting / follow-up / new plan → (if new plan) Mem0 loads prefs → 6 agents + MCP tools run → Mem0 saves prefs → Postgres checkpoints state → guardrails sanitize output → LangSmith records the trace → evals verify nothing regressed.

---

## Table of Contents

1. [What This Project Does](#what-this-project-does)
2. [High-Level Architecture](#high-level-architecture)
3. [Features (Detailed)](#features-detailed)
4. [User Flow](#user-flow)
5. [Memory System](#memory-system)
6. [Safety (Guardrails)](#safety-guardrails)
7. [Observability (LangSmith)](#observability-langsmith)
8. [MCP Integration (Remote, Local, Custom)](#mcp-integration-remote-local-custom)
9. [LangGraph Agent Pipeline](#langgraph-agent-pipeline)
10. [Project Structure](#project-structure)
11. [Setup Guide](#setup-guide)
12. [How to Run](#how-to-run)
13. [Environment Variables](#environment-variables)
14. [Example Prompts](#example-prompts)
15. [Evaluations](#evaluations)
16. [Troubleshooting](#troubleshooting)
17. [Interview Quick Reference](#interview-quick-reference)

---

## What This Project Does

In simple terms:

1. You enter a **username** and describe a trip (e.g. *"Plan a 7-day Japan trip under ₹2L"*).
2. **Guardrails** screen the message for injection, PII, and unsafe content — only safe travel queries proceed.
3. The **message router** classifies intent: greeting, follow-up, new plan, or clarify — avoiding unnecessary agent runs.
4. For a **new plan**, the app runs **6 specialist agents** one by one: Planner → Research → Hotels → Flights → Activities → Itinerary.
5. Each agent calls **MCP tools** (Tavily search, AviationStack flights, Weather API) for real data.
6. **Mem0** injects past preferences (vegetarian, budget, direct flights) at graph start and saves new facts at graph end.
7. **PostgresSaver** checkpoints the full trip state after every node — follow-ups work without re-planning.
8. The final agent builds a **day-by-day itinerary**; **LangSmith** traces the full run for debugging.
9. **Evals** (13 metrics) continuously verify guardrails, agent quality, and multi-turn memory.

### The four production layers

| Layer | Problem it solves | Key files |
|-------|-------------------|-----------|
| **Memory** | Users shouldn't repeat preferences every trip; follow-ups should be instant | `memory/`, `graph/nodes/memory_*.py` |
| **Guardrails** | LLM apps must block jailbreaks, PII leaks, and toxic input before agents run | `guardrails/pipeline.py` |
| **Observability** | Multi-agent pipelines are hard to debug without per-node traces | `observability.py`, `docs/LANGSMITH.md` |
| **Evaluations** | Ship agent changes safely — measure tool use, plan quality, and memory retention | `evals/`, `evals/README.md` |

**Tech stack:** LangGraph · LangChain · Groq LLM · MCP · Mem0 · Neon PostgreSQL · NeMo Guardrails · LangSmith · DeepEval · Streamlit

---

## High-Level Architecture

Voyager AI is organized in **four layers**. Each layer has a single responsibility; data flows left-to-right from the user through safety checks, orchestration, tools, and persistence.

| Layer | Components | Responsibility |
|-------|------------|----------------|
| **UI** | Streamlit (`frontend.py`), message router | Collect user input, classify intent, render replies |
| **Safety** | NeMo Guardrails (`guardrails/pipeline.py`) | Block unsafe input/output before agents run |
| **Orchestration** | LangGraph (`graph/builder.py`) | Run 6 specialist agents in sequence |
| **Tools** | MCP clients (`mcp_client.py`) | Tavily, AviationStack, Weather APIs |
| **Memory** | PostgresSaver + Mem0 | Session state (`thread_id`) + user prefs (`user_id`) |
| **Observability** | LangSmith (`observability.py`) | Trace every graph node and LLM call |

```mermaid
flowchart TB
    subgraph UI["Streamlit UI (frontend.py)"]
        User[User Chat]
        Router[Message Router]
        User --> Router
    end

    subgraph RouterOut["Router Decisions"]
        Greeting[Greeting - no agents]
        FollowUp[Follow-up - LLM only]
        NewPlan[New Plan - full pipeline]
    end

    Router --> Greeting
    Router --> FollowUp
    Router --> NewPlan

    subgraph Graph["LangGraph Pipeline (main.py + graph/)"]
        RM[retrieve_memory]
        PA[planner_agent]
        RA[research_agent]
        HA[hotel_agent]
        FA[flight_agent]
        AA[activity_agent]
        FR[final_response_agent]
        SM[store_memory]
        RM --> PA --> RA --> HA --> FA --> AA --> FR --> SM
    end

    NewPlan --> Graph

    subgraph MCP["MCP Layer (mcp_client.py)"]
        Tavily[Remote: Tavily HTTP MCP]
        Aviation[Local: AviationStack stdio MCP]
        Weather[Custom Local: Weather stdio MCP]
    end

    RA --> Tavily
    HA --> Tavily
    FA --> Aviation
    AA --> Weather

    subgraph Memory["Memory Layer"]
        ST[Short-term: PostgresSaver<br/>key = thread_id]
        LT[Long-term: Mem0 Platform<br/>key = user_id]
    end

    RM --> LT
    SM --> LT
    Graph --> ST
    FollowUp --> ST
    FollowUp --> LT
```

**Key annotations:**
- **Router** decides whether to greet, answer a follow-up, or run the full graph — saving cost on simple messages.
- **`retrieve_memory` / `store_memory`** bookend the graph: Mem0 context in at start, durable facts saved at end.
- **PostgresSaver** checkpoints the full `TravelState` after every node — no manual save code.
- **MCP tools** are called only by the agents that need them (research/hotel → Tavily, flight → AviationStack, activity → Weather).

---

## Features (Detailed)

### 1. Multi-Agent Travel Planning

| Agent | Role | MCP / Tool Used | Output |
|-------|------|-----------------|--------|
| **Planner Agent** | Creates personalized trip outline from query + Mem0 context | Groq LLM | `planner_output` |
| **Research Agent** | Researches destination highlights | Tavily MCP | `research_output` |
| **Hotel Agent** | Searches hotels and stay options | Tavily MCP | `hotel_results` |
| **Flight Agent** | Finds airports, airlines, routes, fare guidance | AviationStack MCP | `flight_results` |
| **Activity Agent** | Weather + activities for destination | Weather MCP + Tavily | `activity_results` |
| **Itinerary Agent** | Combines all results into day-by-day plan | Groq LLM | `itinerary` |

**How it works inside:**  
`graph/builder.py` defines a `StateGraph` where agents run **sequentially**. Each reads `memory_context` from state (loaded by `retrieve_memory` from Mem0). The `with_memory()` wrapper records each agent's output into short-term checkpointed state.

---

### 2. Smart Chat UI with Message Router

The Streamlit app (`frontend.py`) does not run all agents for every message. `chat_router.py` classifies each message:

| Intent | Example | What Happens |
|--------|---------|--------------|
| `GREETING` | "Hello" | Friendly reply only — **no agents** |
| `FOLLOW_UP` | "Where did I plan to go?" | Answers from saved plan + memory — **no agents** |
| `NEW_PLAN` | "Plan a 7-day Japan trip" | Runs full 4-agent pipeline |
| `CLARIFY` | Vague message | Asks for destination, days, budget |

**How it works inside:**  
Regex patterns in `chat_router.py` detect intent. `frontend.py` calls `classify_message()` before deciding whether to invoke `run_travel_graph()` or `answer_follow_up()`.

---

### 3. Live Agent Pipeline UI

When planning a new trip, the UI shows **agent pills** (Waiting → Working → Done) so users see which specialist is running. After completion, each agent's output appears in expandable **status cards** with human-readable formatting.

**Implementation:** `render_agent_pipeline()` and `run_travel_graph()` in `frontend.py` stream LangGraph updates via `app.stream(..., stream_mode="updates")`.

---

### 4. Per-User Memory (Multi-User Support)

- Each user enters a **username** in the sidebar.
- `user_id` = username (long-term memory key)
- `thread_id` = `{username}_chat` (short-term session key)
- Switching users loads that user's **saved trip plan** from the database.

**Implementation:** `save_username()` in `frontend.py` calls `load_user_plan()` from `main.py`.

---

### 5. Follow-Up Questions Without Re-Planning

Questions like *"Where did I plan to travel?"* or *"What hotels did you suggest?"* are answered with a **single LLM call** using the stored plan — fast and cheap, no MCP calls.

**Implementation:** `answer_follow_up()` in `main.py` builds a prompt from `last_plan` + chat history + long-term memory context.

---

### 6. Plan Download

After a successful plan, users can download the itinerary as a Markdown file from the sidebar. Files are saved locally in `travel_plans/` (gitignored).

---

### 7. Production Memory System

A dedicated `memory/` module with `MemoryManager` as the single entry point. Agents never write to the database directly — they go through the memory layer.

---

## User Flow

A typical session follows this path. The router is the gatekeeper: only **new plan** messages trigger the expensive 6-agent pipeline.

| Step | What happens | Agents run? |
|------|----------------|-------------|
| 1 | User enters username → session keys set (`user_id`, `thread_id`) | No |
| 2 | User sends a message → **guardrails** check input | No |
| 3 | **Router** classifies intent (greeting / follow-up / new plan / clarify) | No |
| 4a | Greeting or clarify → short reply, loop back to chat | No |
| 4b | Follow-up → load plan from PostgresSaver → single LLM answer | No |
| 4c | New plan → Mem0 retrieve → 6 agents → Mem0 store → show itinerary | **Yes** |
| 5 | PostgresSaver auto-checkpoints after every graph node | — |

```mermaid
flowchart TD
    A[Open Streamlit App] --> B[Enter Username + Save]
    B --> C[Welcome Message Shown]
    C --> D[User Types Message]
    D --> E{Message Router}

    E -->|Greeting| F[Short Friendly Reply]
    E -->|Follow-up| G{Plan Exists?}
    E -->|New Plan| H[Run 6 Agents via LangGraph]
    E -->|Clarify| I[Ask for Trip Details]

    G -->|No| J[No Plan Yet Reply]
    G -->|Yes| K[Load Plan from Checkpoint]
    K --> L[answer_follow_up - single LLM call]

    H --> M[retrieve_memory from Mem0]
    M --> N[planner → research → hotel → flight → activity → itinerary]
    N --> O[store_memory to Mem0]
    O --> P[Show Summary + Itinerary + Agent Cards]
    P --> Q[PostgresSaver auto-checkpoints state]

    B --> R[Switch User]
    R --> S[Load New User's Saved Plan]
    S --> D

    F --> D
    J --> D
    L --> D
    I --> D
    P --> D
```

---

### Example user journey

1. **Rahul** saves username → sees welcome message.
2. Rahul: *"Plan a 7-day Japan trip under ₹2L"* → agents run → itinerary shown.
3. Rahul: *"Where did I plan to go?"* → instant answer: **Japan** (no agents).
4. Switch to **Priya** → plan Paris trip.
5. Switch back to **Rahul** → sidebar shows *Saved plan destination: Japan*.
6. Rahul: *"Where did I plan to go?"* → still answers **Japan** from database.

---

## Memory System

> **Why it matters:** Separating session state from user identity is a common interview topic. Voyager uses `thread_id` for the current trip and `user_id` for cross-session preferences — never mixed.

Voyager AI uses **two separate memory systems** with different keys, lifetimes, and purposes. They are **not mixed** — each has a clear job.

| Tier | Technology | Key | Scope | Analogy |
|------|------------|-----|-------|---------|
| **Short-term** | LangGraph `PostgresSaver` on Neon | `thread_id` | One chat session | Working memory — *what we're doing right now* |
| **Long-term** | [Mem0](https://docs.mem0.ai/integrations/langgraph) Platform | `user_id` | All sessions forever | User profile — *who this person is* |

```mermaid
flowchart TB
    subgraph LT["Long-term — Mem0 (key: user_id)"]
        RM[retrieve_memory<br/>search past preferences]
        SM[store_memory<br/>extract + save facts]
    end

    subgraph Graph["LangGraph pipeline (key: thread_id)"]
        P[planner] --> R[research] --> H[hotel]
        H --> F[flight] --> A[activity] --> I[itinerary]
    end

    subgraph ST["Short-term — PostgresSaver"]
        CP[auto-checkpoint<br/>after every node]
    end

    RM -->|memory_context| P
    I --> SM
    Graph --> CP
```

**Flow annotations:**
- **Read (start):** `retrieve_memory` queries Mem0 with `user_id` + latest message → fills `memory_context` in state.
- **Write (end):** `store_memory` uses an LLM to extract durable facts (diet, budget, style) → saves to Mem0.
- **Checkpoint (continuous):** PostgresSaver persists the full graph state after each agent — used for follow-ups and session restore.
- **Follow-ups** read from PostgresSaver only (fast path); Mem0 is optional extra context.

```
One user  →  many conversations

user_id   = rahul          →  Mem0 (preferences persist forever)
thread_id = rahul_chat     →  PostgresSaver (this session's full trip state)
```

### Short-term memory (session)

- **What:** Full graph state — itinerary, agent outputs, messages, errors
- **When:** Auto-saved after **every graph node** by LangGraph checkpointer
- **Used for:** Restoring the current trip after refresh; follow-up questions in the same session

### Long-term memory (Mem0)

- **What:** Durable user facts only — diet, budget, travel style, airline preference
- **When retrieved:** At graph **start** (`retrieve_memory` node) before any agent runs
- **When saved:** At graph **end** (`store_memory` node) after the itinerary is built
- **Used for:** Personalizing **new trips** across sessions without repeating preferences

### Graph memory flow

```
START → retrieve_memory (Mem0 search)
      → planner → research → hotel → flight → activity → final_response
      → store_memory (Mem0 save)
      → END

PostgresSaver checkpoints the full state after each step automatically.
```

### Example

1. Rahul says: *"I'm vegetarian, budget $3000, prefer direct flights. Plan Tokyo."*
2. **Mem0** stores: vegetarian, $3000 budget, direct flights (long-term)
3. **PostgresSaver** stores: full Tokyo itinerary + agent outputs (short-term)
4. Next week Rahul says: *"Plan Bali"* → **Mem0** injects preferences into agents automatically
5. Rahul asks: *"Where am I going?"* → **PostgresSaver** answers from checkpoint (fast, no agents)

**Full interview guide:** [`memory/README.md`](memory/README.md)  
**Setup & testing:** [`docs/MEMORY.md`](docs/MEMORY.md)

---

## Safety (Guardrails)

> **Why it matters:** Production LLM apps need defense-in-depth — not just a system prompt. Voyager blocks jailbreaks, PII, and toxic input *before* any agent or MCP tool is invoked.

NeMo Guardrails run **before** the message router (input) and **after** agent replies (output). Blocked messages never reach LangGraph.

| Check layer | What it catches | Implementation |
|-------------|-----------------|----------------|
| 1. Regex fast-path | Jailbreak, injection, toxic patterns | `guardrails/pipeline.py` |
| 2. PII detection | Email, phone, credit card, API keys | NeMo `actions.py` |
| 3. Colang flows | Semantic unsafe intent | `guardrails/config/rails.co` |
| 4. LLM self-check | Final yes/no safety verdict | Groq 8B (`GUARDRAIL_MODEL`) |

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit
    participant Guard as Guardrails
    participant Router as chat_router
    participant Graph as LangGraph

    User->>UI: message
    UI->>Guard: check_input()
    alt blocked
        Guard-->>UI: safe refusal
        UI-->>User: blocked (agents NOT called)
    else allowed
        Guard->>Router: classify intent
        alt new plan
            Router->>Graph: run 6 agents
        else follow-up / greeting
            Router->>UI: lightweight reply
        end
        UI->>Guard: check_output()
        Guard-->>UI: sanitized reply
        UI-->>User: final reply
    end
```

*Full guide: [`guardrails/README.md`](guardrails/README.md)*

---

## Observability (LangSmith)

> **Why it matters:** With 6 agents and 3 MCP servers, you cannot debug from logs alone. LangSmith shows exactly which node failed, which tool was called, and which user/session triggered the run.

Every trip-planning run is traced in LangSmith with graph nodes, LLM calls, metadata (`user_id`, `thread_id`), and tags.

| What is traced | Where configured | Visible in LangSmith as |
|----------------|------------------|-------------------------|
| Top-level graph run | `main.py` → `build_run_config()` | `travel_planning` trace |
| Each agent node | LangGraph auto-tracing | Nested spans per node |
| Groq LLM calls | LangChain callback (env vars) | `ChatGroq` child spans |
| User/session context | `metadata` + `tags` | `user:<name>`, `thread_id` filters |

```mermaid
sequenceDiagram
    participant UI as Streamlit
    participant Obs as observability.py
    participant App as main.py
    participant Graph as LangGraph
    participant LS as LangSmith

    Note over Obs: configure_langsmith() at startup
    UI->>App: run_travel_graph(state, config)
    App->>Graph: app.stream() with metadata/tags
    loop each graph node
        Graph->>LS: span (planner, research, hotel, ...)
        Graph->>LS: nested ChatGroq LLM spans
    end
    Graph-->>UI: itinerary + agent outputs
```

*Full guide: [`docs/LANGSMITH.md`](docs/LANGSMITH.md)*

---

## MCP Integration (Remote, Local, Custom)

**MCP (Model Context Protocol)** lets AI agents call external tools in a standard way. This project uses **three MCP servers** configured in `mcp_client.py` via `MultiServerMCPClient`.

```mermaid
flowchart LR
    subgraph App["Mcp-proj (mcp_client.py)"]
        Client[MultiServerMCPClient]
    end

    subgraph Remote["Remote MCP"]
        Tavily[Tavily Cloud MCP<br/>streamable_http]
    end

    subgraph Local["Local MCP"]
        Aviation[AviationStack MCP<br/>stdio subprocess]
    end

    subgraph Custom["Custom Local MCP"]
        Weather[custom_weather_mcp_server.py<br/>stdio subprocess]
    end

    Client -->|HTTPS| Tavily
    Client -->|spawn process| Aviation
    Client -->|spawn process| Weather
```

---

### 1. Remote MCP — Tavily (Hotel Search)

| Property | Detail |
|----------|--------|
| **Type** | Remote / cloud-hosted MCP |
| **Transport** | `streamable_http` |
| **URL** | `https://mcp.tavily.com/mcp/?tavilyApiKey=...` |
| **Tool used** | `tavily_search` |
| **Used by** | `hotel_agent` in `main.py` |
| **API key** | `TAVILY_API_KEY` in `.env` |

**In simple terms:** The app talks to Tavily's MCP server over the internet. No local install needed — just an API key. The hotel agent sends a search query like *"Best hotels for 7-day Japan trip"* and gets web search results.

**Code (`mcp_client.py`):**
```python
"tavily": {
    "transport": "streamable_http",
    "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
}
```

**Agent usage (`main.py`):**
```python
hotel_results = asyncio.run(tavily_mcp_search(query))
```

---

### 2. Local MCP — AviationStack (Flight Data)

| Property | Detail |
|----------|--------|
| **Type** | Local MCP server (third-party package) |
| **Transport** | `stdio` (subprocess stdin/stdout) |
| **Location** | `../aviationstack-mcp-main/` (sibling folder) |
| **Command** | `python -m aviationstack_mcp mcp run` |
| **Tools used** | `list_airports`, `list_airlines`, and more |
| **Used by** | `flight_agent` in `main.py` |
| **API key** | `AVIATIONSTACK_API_KEY` in `.env` |

**In simple terms:** The app **spawns a local Python process** that runs the AviationStack MCP server. Communication happens through stdin/stdout (stdio transport). The flight agent calls `list_airports` and `list_airlines` to get real aviation data, then the LLM turns that into travel guidance.

**You do NOT need a separate terminal** — `mcp_client.py` starts this process automatically when agents run.

**Code (`mcp_client.py`):**
```python
"aviationstack": {
    "transport": "stdio",
    "command": aviation_python,  # uses aviationstack-mcp-main/.venv if present
    "args": ["-m", "aviationstack_mcp", "mcp", "run"],
    "cwd": str(AVIATIONSTACK_ROOT),
    "env": {"AVIATION_STACK_API_KEY": AVIATION_STACK_API_KEY},
}
```

**Agent usage (`main.py`):**
```python
airports = asyncio.run(aviation_mcp_call("list_airports"))
airlines = asyncio.run(aviation_mcp_call("list_airlines"))
```

---

### 3. Custom Local MCP — Weather Server (OpenWeather)

| Property | Detail |
|----------|--------|
| **Type** | Custom-built local MCP server (written by you) |
| **Transport** | `stdio` |
| **File** | `custom_weather_mcp_server.py` |
| **Framework** | `FastMCP` from the `mcp` Python package |
| **Tools** | `get_current_weather(city)`, `get_forecast(city)` |
| **Used by** | `weather_agent` in `main.py` |
| **API key** | `OPENWEATHER_API_KEY` in `.env` |
| **External API** | OpenWeatherMap REST API |

**In simple terms:** This is a **small MCP server you wrote yourself**. It exposes two tools that call the OpenWeatherMap API. The app spawns it as a subprocess (like AviationStack), but the code lives inside this repo at `custom_weather_mcp_server.py`.

**Code (`custom_weather_mcp_server.py`):**
```python
mcp = FastMCP("Weather Server")

@mcp.tool()
def get_current_weather(city: str):
    # calls https://api.openweathermap.org/data/2.5/weather
    ...

@mcp.tool()
def get_forecast(city: str):
    # calls https://api.openweathermap.org/data/2.5/forecast
    ...
```

**MCP client config (`mcp_client.py`):**
```python
"weather": {
    "transport": "stdio",
    "command": sys.executable,
    "args": [str(WEATHER_SERVER_SCRIPT)],
    "env": {"OPENWEATHER_API_KEY": OPENWEATHER_API_KEY},
}
```

**Agent usage (`main.py`):**
```python
city = extract_destination(state["user_query"])
weather_data = asyncio.run(weather_mcp_search(city))
forecast_data = asyncio.run(forecast_mcp_search(city))
```

---

### MCP Comparison Table

| MCP Server | Type | Transport | Runs Where | Who Starts It | Tools |
|------------|------|-----------|------------|---------------|-------|
| **Tavily** | Remote | HTTP | Tavily cloud | `MultiServerMCPClient` | `tavily_search` |
| **AviationStack** | Local (package) | stdio | Your machine | `MultiServerMCPClient` spawns subprocess | `list_airports`, `list_airlines`, ... |
| **Weather** | Custom local | stdio | Your machine | `MultiServerMCPClient` spawns subprocess | `get_current_weather`, `get_forecast` |

---

## LangGraph Agent Pipeline

```mermaid
flowchart LR
    START((START)) --> RM[retrieve_memory]
    RM --> PA[planner_agent]
    PA --> RA[research_agent]
    RA --> HA[hotel_agent]
    HA --> FA[flight_agent]
    FA --> AA[activity_agent]
    AA --> FR[final_response_agent]
    FR --> SM[store_memory]
    SM --> END((END))
```

**Graph flow:**
```
retrieve_memory → planner → research → hotel → flight → activity → final_response → store_memory
```

- **`retrieve_memory`** — queries Mem0, fills `memory_context` before agents run
- **`store_memory`** — extracts durable facts, saves to Mem0 after itinerary
- **PostgresSaver** — checkpoints full `TravelState` after every node automatically

Each agent reads `memory_context` from state and personalizes its output. The graph is compiled with a Postgres checkpointer:

```python
app = graph.compile(checkpointer=checkpointer)
```

---

## Project Structure

```
Mcp-proj/
├── main.py                      # App entry, follow-up logic, run config
├── frontend.py                  # Streamlit chat UI
├── chat_router.py               # Message intent classification
├── mcp_client.py                # MultiServerMCPClient (3 MCP servers)
├── custom_weather_mcp_server.py # Custom local weather MCP
├── db_config.py                 # Neon PostgresSaver (short-term memory)
├── graph/
│   ├── builder.py               # LangGraph wiring
│   └── nodes/                   # retrieve_memory, agents, store_memory
├── memory/
│   ├── memory_manager.py        # Single memory facade (Mem0 + state helpers)
│   ├── retriever.py             # Mem0 search + prompt formatting
│   ├── extractor.py             # LLM fact extraction before Mem0 save
│   ├── provider/mem0_provider.py# Official Mem0 MemoryClient integration
│   └── README.md                # Interview-ready memory architecture guide
├── docs/
│   ├── MEMORY.md                # Setup and testing guide
│   └── LANGSMITH.md             # Observability guide
├── evals/                       # DeepEval + custom eval suites (see evals/README.md)
│   ├── datasets/                # golden_ci, golden_nightly, golden_memory
│   ├── results/                 # custom.md, single_turn.md, multi_turn.md
│   ├── test_ci.py               # PR: guardrails, injection, router
│   ├── test_nightly.py          # Daily: 5 agent metrics
│   └── test_memory.py           # Weekly: 5 conversation metrics
└── tests/
    └── test_memory_manager.py

../aviationstack-mcp-main/       # Local AviationStack MCP (separate folder)
```

---

## Setup Guide

### Prerequisites

| Requirement | Link |
|-------------|------|
| Python 3.10+ | https://python.org |
| Groq API key | https://console.groq.com |
| Tavily API key | https://tavily.com |
| AviationStack API key | https://aviationstack.com |
| OpenWeatherMap API key | https://openweathermap.org |
| Neon PostgreSQL (free tier) | https://neon.tech |
| Mem0 API key (free tier) | https://app.mem0.ai |

---

### Step 1: Clone and enter project

```powershell
cd Mcp-proj
```

---

### Step 2: Create Python virtual environment

```powershell
python -m venv langgraph_env3
langgraph_env3\Scripts\activate
```

---

### Step 3: Install dependencies

```powershell
pip install -r requirements.txt
```

> First run may take a moment while dependencies initialize.

---

### Step 4: Setup Neon PostgreSQL (short-term memory)

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project and database
3. Copy the **pooled** connection string
4. Paste into `.env` as `DATABASE_URL`

The app auto-creates LangGraph checkpoint tables on first run via `PostgresSaver.setup()`.

---

### Step 5: Setup Mem0 (long-term memory)

1. Create a free account at [app.mem0.ai](https://app.mem0.ai)
2. Go to **Settings → API Keys** and create a key
3. Add to `.env`:

```env
MEM0_API_KEY=your_mem0_api_key
MEM0_ENABLED=true
MEMORY_TOP_K=8
```

Official integration reference: [Mem0 + LangGraph docs](https://docs.mem0.ai/integrations/langgraph)

---

### Step 6: Configure `.env`

```powershell
copy .env.example .env
```

Edit `.env` and add your keys:

```env
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
DATABASE_URL=postgresql://user:password@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require
MEM0_API_KEY=your_mem0_api_key
MEM0_ENABLED=true
```

> **Important:** No spaces around `=` in `.env` files.  
> Example: `GROQ_API_KEY=gsk_xxx` ✅ not `GROQ_API_KEY= gsk_xxx` ❌

---

### Step 7: Setup AviationStack MCP (local dependency)

The aviation MCP lives in a **sibling folder**:

```powershell
cd ..\aviationstack-mcp-main
```

Install [uv](https://docs.astral.sh/uv/) if needed:

```powershell
pip install uv
```

Create `.env` with your aviation API key:

```env
AVIATION_STACK_API_KEY=your_api_key_here
```

Install dependencies:

```powershell
uv sync
```

Return to main project:

```powershell
cd ..\Mcp-proj
```

> **Note:** You do **not** need to manually start the aviation MCP server in a separate terminal. `mcp_client.py` spawns it automatically via stdio when agents run.

---

## How to Run

### Streamlit Web App (recommended)

```powershell
cd Mcp-proj
langgraph_env3\Scripts\activate
streamlit run frontend.py
```

Open the URL shown in terminal (usually `http://localhost:8501`).

### CLI Version

```powershell
python main.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq LLM API key (Llama 3.3 70B) |
| `TAVILY_API_KEY` | Yes | Tavily search MCP |
| `AVIATIONSTACK_API_KEY` | Yes | AviationStack flight data MCP |
| `OPENWEATHER_API_KEY` | Yes | OpenWeatherMap for custom weather MCP |
| `DATABASE_URL` | Yes | Neon PostgreSQL for LangGraph PostgresSaver (short-term) |
| `MEM0_API_KEY` | Yes | Mem0 Platform API key (long-term user memory) |
| `MEM0_ENABLED` | No | Enable/disable Mem0 (default: `true`) |
| `MEMORY_TOP_K` | No | Max memories retrieved per query (default: 8) |
| `LANGSMITH_TRACING` | No | Enable LangSmith observability |
| `LANGSMITH_API_KEY` | No | LangSmith API key |

---

## Example Prompts

**New trip planning:**
```
Plan a complete 7-day Japan trip including flights, hotels and sightseeing under ₹2L.
```

**Follow-up (after a plan exists):**
```
Where did I plan to go?
What hotels did you suggest?
Remind me of my itinerary.
```

**Greeting:**
```
Hello
What can you do?
```

---

## Evaluations

> **Why it matters:** Agent apps regress silently — wrong tool choice, forgotten preferences, or a greeting triggering a full graph run. Voyager runs **13 automated evals** on every PR (CI), daily (agent quality), and weekly (memory).

Voyager AI ships **13 eval metrics** in three suites (CI / nightly / memory). Results append to Markdown logs under `evals/results/`.

| Suite | Metrics | Command | Schedule | Results file |
|-------|---------|---------|----------|--------------|
| **CI** | Guardrail alignment, prompt injection, router intent | `pytest evals/test_ci.py -v` | Every PR | `custom.md` |
| **Nightly** | Task completion, tool correctness, plan adherence, plan quality, argument correctness | `EVAL_LIVE=1 deepeval test run evals/test_nightly.py` | Daily | `single_turn.md` |
| **Memory** | Knowledge retention, turn relevancy, faithfulness, contextual recall, goal accuracy | `EVAL_LIVE=1 deepeval test run evals/test_memory.py` | Weekly | `multi_turn.md` |

```mermaid
flowchart LR
    CLI[Developer CLI] --> CI[test_ci.py<br/>3 custom checks]
    CLI --> Nightly[test_nightly.py<br/>5 DeepEval metrics]
    CLI --> Memory[test_memory.py<br/>5 multi-turn metrics]

    CI --> R1[(custom.md)]
    Nightly --> Judge[GroqJudge<br/>llama-3.3-70b]
    Memory --> Judge
    Judge --> R2[(single_turn.md)]
    Judge --> R3[(multi_turn.md)]
```

**How it works:** CI evals are deterministic (no API cost). Nightly and memory suites invoke the real LangGraph pipeline with `EVAL_LIVE=1`, score outputs with DeepEval + Groq judge, and append pass/fail rows to the results Markdown files.

**Full guide (why / what / how, interview Q&A):** [`evals/README.md`](evals/README.md)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `PoolTimeout` on Neon | Ensure `DATABASE_URL` uses the **pooled** connection string. App uses `pool.open(wait=True)`. |
| `ModuleNotFoundError: langchain_mcp_adapters` | Activate venv: `langgraph_env3\Scripts\activate` before running Streamlit |
| Aviation MCP fails | Run `uv sync` in `aviationstack-mcp-main/`. Check `AVIATIONSTACK_API_KEY`. |
| Mem0 not retrieving preferences | Verify `MEM0_API_KEY` in `.env`; wait 15s after first trip (async indexing) |
| Follow-up says "no plan yet" | Create at least one full trip plan for that username first |
| Memory not restored after refresh | Verify `DATABASE_URL`; same username must use same `thread_id` |
| Slow first run | MCP tool initialization on first agent call — normal |

---

## Interview Quick Reference

**What is this project?**  
A production-style multi-agent AI travel planner: LangGraph orchestration, MCP tool integration, dual-layer memory, NeMo guardrails, LangSmith tracing, and a 13-metric DeepEval suite.

**Memory (two tiers, two keys):**
- **Short-term** — PostgresSaver on Neon, keyed by `thread_id`. Full `TravelState` auto-checkpointed after every graph node. Powers follow-ups and session restore.
- **Long-term** — Mem0 Platform, keyed by `user_id`. Durable preferences only (diet, budget, style). `retrieve_memory` at graph start, `store_memory` at graph end.
- Deep-dive: [`memory/README.md`](memory/README.md)

**Guardrails (input + output):**  
Regex fast-path → PII detection → Colang flows → Groq 8B self-check. Blocked input never reaches the router or LangGraph. Output is sanitized before the user sees it.  
Deep-dive: [`guardrails/README.md`](guardrails/README.md)

**Observability:**  
`observability.py` sets LangSmith env vars; `build_run_config()` attaches `user_id`, `thread_id`, and tags. Every agent node and nested `ChatGroq` call appears as a trace span.  
Deep-dive: [`docs/LANGSMITH.md`](docs/LANGSMITH.md)

**Evaluations (13 metrics, 3 schedules):**
- **CI (PR):** guardrail alignment, prompt injection block, router intent → `pytest evals/test_ci.py`
- **Nightly:** task completion, tool correctness, plan adherence, plan quality, argument correctness → DeepEval + Groq judge
- **Weekly:** knowledge retention, turn relevancy, faithfulness, contextual recall, goal accuracy → multi-turn Mem0 tests  
Deep-dive: [`evals/README.md`](evals/README.md)

**Three MCP types:**
1. **Remote** — Tavily over HTTP (hotel + research search)
2. **Local** — AviationStack stdio subprocess (flight data)
3. **Custom local** — `custom_weather_mcp_server.py` stdio subprocess (weather)

**User flow:** Username → guardrails → router (greeting / follow-up / new plan) → (new plan) Mem0 retrieve → 6 agents + MCP → Mem0 store → Postgres checkpoint → guardrails on output → LangSmith trace.

**Why this matters in interviews:** Shows you can build beyond a single LLM call — orchestration, tools, memory, safety, observability, and evals are what separate demo apps from shippable agent systems.

---

## Credits

Based on the Multi-Agent Travel Planning System tutorial series. Extended with MCP integration, production memory system, smart chat router, and per-user persistence.

**Related resources:**
- Part 1 repo: [AI-Travel-Planning-System-using-LangGraph](https://github.com/codewithaarohi/AI-Travel-Planning-System-using-LangGraph)
- Tavily MCP: https://docs.tavily.com/documentation/mcp
- LangGraph: https://langchain-ai.github.io/langgraph/
- MCP Protocol: https://modelcontextprotocol.io/
