# Memory Architecture — Northline

Production memory uses **two separate tiers** with clear responsibilities.

| Tier | Technology | Key | Scope |
|------|------------|-----|-------|
| **Short-term** | LangGraph `PostgresSaver` | `thread_id` | One chat session |
| **Long-term** | [Mem0](https://docs.mem0.ai/integrations/langgraph) | `user_id` | Across all sessions |

---

## Graph flow

```
START → retrieve_memory → planner_agent → research_agent → hotel_agent
      → flight_agent → activity_agent → final_response_agent → store_memory → END
```

- **retrieve_memory** — queries Mem0, injects `memory_context` before agents run
- **store_memory** — LLM extracts durable facts, saves to Mem0 after itinerary
- **PostgresSaver** — checkpoints full `TravelState` after every node automatically

---

## Environment variables

Add to `.env`:

```env
# Short-term (required)
DATABASE_URL=postgresql://...@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require

# Long-term Mem0 (get key at https://app.mem0.ai)
MEM0_API_KEY=m0-xxxxxxxx
MEM0_ENABLED=true
MEMORY_TOP_K=8
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Neon Postgres for LangGraph checkpoints |
| `MEM0_API_KEY` | Yes for long-term | Mem0 Platform API key |
| `MEM0_ENABLED` | No | Set `false` to disable Mem0 (graph still runs) |
| `MEMORY_TOP_K` | No | Max memories retrieved per query (default 8) |

---

## Identifiers

```
user_id = rahul          → Mem0 (all trips, forever)
thread_id = rahul_chat   → PostgresSaver (this session)
thread_id = rahul_trip_tokyo  → separate session per trip (optional)
```

One user → many conversations (thread_ids).

---

## What gets stored where

### Short-term (PostgresSaver / `thread_id`)

Full `TravelState` after each node:

- messages, planner_output, research_output
- hotel_results, flight_results, activity_results
- itinerary, tool_outputs, agent_outputs
- errors, current_step, memory_context (this session)

### Long-term (Mem0 / `user_id`)

Only **durable user facts**:

- "I am vegetarian."
- "I prefer luxury hotels."
- "My budget is around $3000."

NOT stored: greetings, one-off booking requests, weather questions.

---

## Testing

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Verify imports

```powershell
python -c "from main import app, memory_manager; print('OK', memory_manager.config.mem0_enabled)"
```

### 3. Test Mem0 retrieval (after adding API key)

```powershell
python -c "
import asyncio
from memory.memory_manager import MemoryManager
from langchain_groq import ChatGroq
mm = MemoryManager(ChatGroq(model='llama-3.3-70b-versatile'))
async def t():
    ctx = await mm.load_memory_context('testuser', 'Plan a trip to Japan')
    print(ctx)
asyncio.run(t())
"
```

### 4. Test full graph (CLI)

```powershell
python main.py
```

### 5. Test in Streamlit

```powershell
streamlit run frontend.py
```

**Session 1:** Log in as `rahul`, say: `I am vegetarian and prefer direct flights. Plan a trip to Tokyo.`

**Session 2:** New browser / clear chat, same username, say: `Plan a trip to Bali` — planner should respect vegetarian + direct flight preferences from Mem0.

### 6. Verify checkpoint restore

After planning a trip, refresh the page. Sidebar should restore destination from `load_user_plan()` (PostgresSaver checkpoint).

---

## Module structure

```
memory/
  config.py          # Env config
  prompts.py         # Extraction + formatting prompts
  retriever.py       # Mem0 search + format
  extractor.py       # LLM fact extraction + save
  memory_manager.py  # Facade (inject into nodes)
  state.py           # TravelState TypedDict
  provider/
    base.py          # Abstract provider (swap Mem0 easily)
    mem0_provider.py # Official MemoryClient

graph/
  builder.py         # Graph wiring
  nodes/
    retrieve_memory.py
    store_memory.py
    planner.py, research.py, hotel.py, flight.py, activities.py, final_response.py
```

---

## Error handling

| Failure | Behavior |
|---------|----------|
| Mem0 unavailable | Log error, continue graph with empty `memory_context` |
| Postgres unavailable | Raise checkpoint error (short-term memory required) |

---

## Official references

- Mem0 + LangGraph: https://docs.mem0.ai/integrations/langgraph
- LangGraph PostgresSaver: https://docs.langchain.com/oss/python/langgraph/persistence
