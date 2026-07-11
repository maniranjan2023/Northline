# Voyager AI — Multi-Agent Travel Planning with LangGraph + MCP + Memory

**Voyager AI** is an intelligent travel planning application that uses **multiple specialist AI agents** connected to **real-world tools** through the **Model Context Protocol (MCP)**. Users chat in a friendly Streamlit UI, and the system plans trips by calling flight, hotel, and weather services — then builds a full itinerary. The app also remembers users across sessions using **short-term** and **long-term memory** stored in **Neon PostgreSQL**.

---

## Table of Contents

1. [What This Project Does](#what-this-project-does)
2. [High-Level Architecture](#high-level-architecture)
3. [Features (Detailed)](#features-detailed)
4. [User Flow](#user-flow)
5. [Memory System](#memory-system)
6. [MCP Integration (Remote, Local, Custom)](#mcp-integration-remote-local-custom)
7. [LangGraph Agent Pipeline](#langgraph-agent-pipeline)
8. [Project Structure](#project-structure)
9. [Setup Guide](#setup-guide)
10. [How to Run](#how-to-run)
11. [Environment Variables](#environment-variables)
12. [Example Prompts](#example-prompts)
13. [Troubleshooting](#troubleshooting)

---

## What This Project Does

In simple terms:

1. You enter a **username** and describe a trip (e.g. *"Plan a 7-day Japan trip under ₹2L"*).
2. The app runs **4 specialist agents** one by one: Flights → Hotels → Weather → Itinerary.
3. Each agent calls **MCP tools** (search APIs, aviation data, weather APIs) to get real information.
4. The final agent combines everything into a **day-by-day travel plan**.
5. The system **saves memory** so when you ask follow-ups like *"Where did I plan to go?"*, it answers instantly **without re-running all agents**.
6. If you **switch users** (e.g. Rahul vs Priya), each user gets their **own separate memory and saved plan**.

**Tech stack:** LangGraph · LangChain · Groq LLM · MCP · Neon PostgreSQL · pgvector · Streamlit

---

## High-Level Architecture

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

    subgraph Graph["LangGraph Pipeline (main.py)"]
        ML[memory_load]
        FA[flight_agent]
        HA[hotel_agent]
        WA[weather_agent]
        IA[itinerary_agent]
        MS[memory_save]
        ML --> FA --> HA --> WA --> IA --> MS
    end

    NewPlan --> Graph

    subgraph MCP["MCP Layer (mcp_client.py)"]
        Tavily[Remote: Tavily HTTP MCP]
        Aviation[Local: AviationStack stdio MCP]
        Weather[Custom Local: Weather stdio MCP]
    end

    FA --> Aviation
    HA --> Tavily
    WA --> Weather

    subgraph DB["Neon PostgreSQL"]
        ST[Short-term: PostgresSaver checkpoints]
        LT[Long-term: pgvector memories]
    end

    Graph --> ST
    MS --> LT
    FollowUp --> LT
    FollowUp --> ST
    ML --> LT
```

---

## Features (Detailed)

### 1. Multi-Agent Travel Planning

| Agent | Role | MCP / Tool Used | Output |
|-------|------|-----------------|--------|
| **Flight Agent** | Finds airports, airlines, routes, fare guidance | AviationStack MCP (`list_airports`, `list_airlines`) | `flight_results` |
| **Hotel Agent** | Searches hotels and stay options | Tavily MCP (`tavily_search`) | `hotel_results` |
| **Weather Agent** | Gets current weather + forecast for destination | Custom Weather MCP (`get_current_weather`, `get_forecast`) | `weather_results` |
| **Itinerary Agent** | Combines all results into a day-by-day plan | Groq LLM (no MCP) | `itinerary` |

**How it works inside:**  
`main.py` defines a `StateGraph` where each agent is a node. Agents run **sequentially** — each reads from shared `TravelState` and writes its result back. The `with_memory()` wrapper in `memory/nodes/agent_wrapper.py` records each agent's output into short-term state automatically.

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

```mermaid
flowchart TD
    A[Open Streamlit App] --> B[Enter Username + Save]
    B --> C[Welcome Message Shown]
    C --> D[User Types Message]
    D --> E{Message Router}

    E -->|Greeting| F[Short Friendly Reply]
    E -->|Follow-up| G{Plan Exists?}
    E -->|New Plan| H[Run 4 Agents via LangGraph]
    E -->|Clarify| I[Ask for Trip Details]

    G -->|No| J[No Plan Yet Reply]
    G -->|Yes| K[Load Plan from DB]
    K --> L[answer_follow_up - single LLM call]

    H --> M[memory_load]
    M --> N[flight → hotel → weather → itinerary]
    N --> O[memory_save]
    O --> P[Show Summary + Itinerary + Agent Cards]
    P --> Q[Save trip_plan to Neon]

    B --> R[Switch User]
    R --> S[Load New User's Saved Plan]
    S --> D

    F --> D
    J --> D
    L --> D
    I --> D
    P --> D
```

### Example user journey

1. **Rahul** saves username → sees welcome message.
2. Rahul: *"Plan a 7-day Japan trip under ₹2L"* → agents run → itinerary shown.
3. Rahul: *"Where did I plan to go?"* → instant answer: **Japan** (no agents).
4. Switch to **Priya** → plan Paris trip.
5. Switch back to **Rahul** → sidebar shows *Saved plan destination: Japan*.
6. Rahul: *"Where did I plan to go?"* → still answers **Japan** from database.

---

## Memory System

### Overview

```mermaid
flowchart LR
    subgraph ShortTerm["Short-Term Memory"]
        ST1[LangGraph TravelState]
        ST2[PostgresSaver Checkpoint]
        ST3["Key: thread_id = rahul_chat"]
        ST1 --> ST2 --> ST3
    end

    subgraph LongTerm["Long-Term Memory"]
        LT1[long_term_memories table]
        LT2[pgvector semantic search]
        LT3["Key: user_id = rahul"]
        LT1 --> LT2 --> LT3
    end

    NewPlan[New Trip Request] --> LoadLT[Load relevant long-term memories]
    LoadLT --> Agents[Agents run with memory_context]
    Agents --> SaveST[Checkpoint saved automatically]
    Agents --> SaveLT[Summaries + trip_plan saved]

    FollowUp[Follow-up Question] --> LoadPlan[Load trip_plan / checkpoint]
    LoadPlan --> LLM[Single LLM answer]
```

---

### Short-Term Memory (Working / Session Memory)

| Property | Value |
|----------|-------|
| **What** | Current graph run state — messages, agent outputs, itinerary, errors |
| **Where** | LangGraph `TravelState` + Neon `PostgresSaver` |
| **Key** | `thread_id` → `{username}_chat` |
| **Lifetime** | Persists in DB per thread; used when resuming a session |
| **Cognitive analogy** | **Working memory** — "what we're doing right now" |

**What is stored:**
- `user_query`, `flight_results`, `hotel_results`, `weather_results`, `itinerary`
- `agent_outputs`, `tool_outputs`, `errors`, `retry_count`
- `memory_context` (loaded from long-term at start of run)

**When it is used:**
- During a full agent pipeline run (each node updates state)
- When restoring a plan via `app.get_state(config)` in `load_user_plan()`
- Automatically checkpointed after each graph step by LangGraph

**Implementation files:**
- `memory/services/short_term_service.py` — builds and patches state
- `db_config.py` — creates `PostgresSaver` checkpointer
- `main.py` — `app = graph.compile(checkpointer=checkpointer)`

---

### Long-Term Memory (Persistent User Knowledge)

| Property | Value |
|----------|-------|
| **What** | Structured facts, summaries, and full trip snapshots per user |
| **Where** | Neon table `long_term_memories` + **pgvector** embeddings |
| **Key** | `user_id` → sanitized username |
| **Retrieval** | **Semantic search** (embed query → find similar memories) |
| **Cognitive analogy** | Mix of **semantic** + **episodic** memory |

**When it is used:**
1. **Start of new plan** — `memory_load` node retrieves relevant memories → injected as `memory_context` into agent prompts
2. **End of new plan** — `memory_save` node summarizes run and stores new memories
3. **Follow-up questions** — `load_user_plan()` + `load_memory_context()` feed the LLM
4. **User switch** — `load_trip_plan()` restores last itinerary per user

**Implementation files:**
- `memory/memory_manager.py` — facade for all memory operations
- `memory/services/long_term_service.py` — semantic retrieval + storage
- `memory/services/embedding_service.py` — `sentence-transformers/all-MiniLM-L6-v2`
- `memory/repositories/long_term_repository.py` — SQL + pgvector queries
- `memory/services/summarization_service.py` — LLM extracts memories after each run
- `migrations/001_memory_tables.sql` — schema setup

---

### Long-Term Memory Types (Semantic vs Episodic)

This project uses a **hybrid** long-term memory model — not pure episodic or pure semantic.

```mermaid
flowchart TB
    subgraph Semantic["Semantic-like Memory"]
        P[preference<br/>e.g. Prefers trips under ₹5L]
        UF[user_fact<br/>e.g. Travels with family]
        SP[success_pattern<br/>e.g. Japan trips worked well]
    end

    subgraph Episodic["Episodic-like Memory"]
        S[summary<br/>e.g. Planned 7-day Japan trip]
        TP[trip_plan<br/>Full itinerary snapshot JSON]
    end

    Run[Completed Trip Run] --> Summarizer[SummarizationService LLM]
    Summarizer --> Semantic
    Summarizer --> Episodic
    Run --> TP

    Query[User Query] --> Embed[Embed query text]
    Embed --> VectorSearch[pgvector cosine search]
    VectorSearch --> Semantic
    VectorSearch --> Episodic

    FollowUpQ[Follow-up Question] --> TP
```

| Memory Type | Category | What It Stores | Example |
|-------------|----------|----------------|---------|
| `preference` | **Semantic** | General user preferences | "Prefers budget trips under ₹2L" |
| `user_fact` | **Semantic** | Stable facts about the user | "Often plans international trips" |
| `success_pattern` | **Semantic / Procedural** | What planning patterns worked | "7-day trips with hotels and flights" |
| `summary` | **Episodic (compressed)** | Short summary of a past trip event | "Planned a Japan trip in July" |
| `trip_plan` | **Episodic (full snapshot)** | Complete plan: itinerary, flights, hotels, weather | Full JSON in `metadata` column |
| `feedback` | **Semantic** | User feedback (reserved for future use) | — |

**Important distinction:**
- **Storage type** = semantic facts + episodic summaries/snapshots
- **Retrieval method** = semantic vector search (meaning-based, not keyword matching)

**What is NOT stored:**
- Full raw chat logs in long-term memory
- Every message verbatim (only structured extractions)

---

### Memory Flow During a New Trip

```mermaid
sequenceDiagram
    participant U as User
    participant UI as frontend.py
    participant G as LangGraph
    participant MM as MemoryManager
    participant LT as Long-Term DB
    participant ST as Short-Term Checkpoint

    U->>UI: Plan a 7-day Japan trip
    UI->>G: app.stream(input_state, config)
    G->>MM: memory_load_node
    MM->>LT: retrieve_relevant(user_id, query)
    LT-->>MM: preferences, summaries, patterns
    MM-->>G: memory_context in state

    G->>G: flight_agent (Aviation MCP)
    G->>G: hotel_agent (Tavily MCP)
    G->>G: weather_agent (Weather MCP)
    G->>G: itinerary_agent (LLM combines all)
    G->>ST: auto-checkpoint after each step

    G->>MM: memory_save_node
    MM->>MM: summarize_travel_run (LLM)
    MM->>LT: store preference/summary records
    MM->>LT: save trip_plan snapshot
    MM-->>G: execution_status = completed

    G-->>UI: itinerary + agent outputs
    UI-->>U: Human summary + expandable agent cards
```

---

### Memory Flow During a Follow-Up

```mermaid
sequenceDiagram
    participant U as User
    participant UI as frontend.py
    participant R as chat_router
    participant M as main.py
    participant LT as Long-Term DB
    participant ST as Short-Term Checkpoint
    participant LLM as Groq LLM

    U->>UI: Where did I plan to go?
    UI->>R: classify_message()
    R-->>UI: FOLLOW_UP
    UI->>M: load_user_plan(username)
    M->>ST: app.get_state(thread_id)
    alt checkpoint has itinerary
        ST-->>M: full plan from checkpoint
    else no checkpoint
        M->>LT: get_latest_trip_plan(user_id)
        LT-->>M: trip_plan metadata JSON
    end
    M->>LT: load_memory_context(user_id, query)
    M->>LLM: answer_follow_up(prompt with plan)
    LLM-->>UI: Japan
    UI-->>U: Instant reply, no agents run
```

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
    START((START)) --> ML[memory_load]
    ML --> FA[flight_agent]
    FA --> HA[hotel_agent]
    HA --> WA[weather_agent]
    WA --> IA[itinerary_agent]
    IA --> MS[memory_save]
    MS --> END((END))
```

**Graph definition (`main.py`):**
```
memory_load → flight_agent → hotel_agent → weather_agent → itinerary_agent → memory_save
```

Each agent node is wrapped with `with_memory()` so outputs are tracked in `TravelState`. The graph is compiled with a Postgres checkpointer for persistence:

```python
app = graph.compile(checkpointer=checkpointer)
```

---

## Project Structure

```
Mcp-proj/
├── main.py                      # LangGraph graph, agents, follow-up logic
├── frontend.py                  # Streamlit chat UI
├── chat_router.py               # Message intent classification
├── mcp_client.py                # MultiServerMCPClient (3 MCP servers)
├── custom_weather_mcp_server.py # Custom local weather MCP
├── db_config.py                 # Neon connection + checkpointer setup
├── requirements.txt
├── .env.example
├── migrations/
│   └── 001_memory_tables.sql    # Long-term memory schema + pgvector
├── memory/
│   ├── memory_manager.py        # Single memory entry point
│   ├── models.py                # MemoryType, MemoryRecord
│   ├── nodes/
│   │   ├── memory_load_node.py  # Load long-term at graph start
│   │   ├── memory_save_node.py  # Save long-term at graph end
│   │   └── agent_wrapper.py     # with_memory() decorator
│   ├── services/
│   │   ├── short_term_service.py
│   │   ├── long_term_service.py
│   │   ├── embedding_service.py
│   │   └── summarization_service.py
│   └── repositories/
│       └── long_term_repository.py
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

> First run downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`) — this may take a few minutes.

---

### Step 4: Setup Neon PostgreSQL

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project and database
3. In Neon dashboard → **Extensions** → enable **`vector`** (pgvector)
4. Copy the **pooled** connection string
5. Paste into `.env` as `DATABASE_URL`

The app auto-creates LangGraph checkpoint tables and long-term memory tables on first run.

---

### Step 5: Configure `.env`

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
```

> **Important:** No spaces around `=` in `.env` files.  
> Example: `GROQ_API_KEY=gsk_xxx` ✅ not `GROQ_API_KEY= gsk_xxx` ❌

---

### Step 6: Setup AviationStack MCP (local dependency)

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
| `DATABASE_URL` | Yes | Neon PostgreSQL pooled connection string |
| `EMBEDDING_MODEL` | No | Default: `sentence-transformers/all-MiniLM-L6-v2` |
| `MEMORY_TOP_K` | No | How many memories to retrieve (default: 5) |
| `MEMORY_DUPLICATE_THRESHOLD` | No | Similarity threshold for dedup (default: 0.92) |

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

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `PoolTimeout` on Neon | Ensure `DATABASE_URL` uses the **pooled** connection string. App uses `pool.open(wait=True)`. |
| `ModuleNotFoundError: langchain_mcp_adapters` | Activate venv: `langgraph_env3\Scripts\activate` before running Streamlit |
| Aviation MCP fails | Run `uv sync` in `aviationstack-mcp-main/`. Check `AVIATIONSTACK_API_KEY`. |
| pgvector errors | Enable `vector` extension in Neon dashboard |
| Follow-up says "no plan yet" | Create at least one full trip plan for that username first |
| Memory not restored after user switch | Restart Streamlit after code changes; verify `DATABASE_URL` is correct |
| Slow first run | Embedding model downloads on first use — normal |

---

## Interview Quick Reference

**What is this project?**  
A multi-agent AI travel planner using LangGraph orchestration, MCP tool integration, and dual-layer memory (short-term checkpoints + long-term semantic/episodic storage in Neon).

**Short-term memory:** Session state keyed by `thread_id`, auto-saved by LangGraph PostgresSaver.

**Long-term memory:** Hybrid semantic (preferences, facts) + episodic (summaries, trip snapshots), retrieved via pgvector semantic search, keyed by `user_id`.

**Three MCP types:**
1. **Remote** — Tavily over HTTP (hotel search)
2. **Local** — AviationStack stdio subprocess (flight data)
3. **Custom local** — `custom_weather_mcp_server.py` stdio subprocess (weather)

**User flow:** Username → router classifies message → greeting / follow-up (no agents) / new plan (4 agents) → memory saved → follow-ups answered from stored plan.

---

## Credits

Based on the Multi-Agent Travel Planning System tutorial series. Extended with MCP integration, production memory system, smart chat router, and per-user persistence.

**Related resources:**
- Part 1 repo: [AI-Travel-Planning-System-using-LangGraph](https://github.com/codewithaarohi/AI-Travel-Planning-System-using-LangGraph)
- Tavily MCP: https://docs.tavily.com/documentation/mcp
- LangGraph: https://langchain-ai.github.io/langgraph/
- MCP Protocol: https://modelcontextprotocol.io/
