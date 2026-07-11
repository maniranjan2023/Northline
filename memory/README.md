# Memory System

This folder contains short-term and long-term memory for Voyager AI.

## Short-term memory
- **What:** current chat session state
- **Where:** LangGraph `TravelState` + Neon `PostgresSaver`
- **Key:** `thread_id` (example: `rahul_chat`)

Stores:
- conversation messages
- agent outputs
- tool outputs
- errors and retry counts

## Long-term memory
- **What:** structured user knowledge
- **Where:** Neon PostgreSQL + pgvector
- **Key:** `user_id` (username)

Stores:
- preferences
- user facts
- successful trip patterns
- summaries

## Main class
Use `MemoryManager` only. Do not query memory tables directly from agents.

## Flow
1. `memory_load` node loads relevant long-term memories
2. Agents run using `memory_context` in prompts
3. `memory_save` node summarizes run and stores long-term memories
