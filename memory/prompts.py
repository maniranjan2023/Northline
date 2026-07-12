"""Prompt templates for memory retrieval formatting and extraction."""

MEMORY_CONTEXT_HEADER = """Known User Information
{memories}
"""

EXTRACTION_SYSTEM_PROMPT = """You extract durable user facts from travel conversations.

Store ONLY long-term preferences and identity facts that should persist across trips.

STORE examples:
- "I am vegetarian."
- "I prefer luxury hotels."
- "My budget is around $3000."
- "I love beaches."
- "I usually travel with my family."
- "I always choose direct flights."
- "My preferred airline is Emirates."

DO NOT store:
- Trip booking requests ("Book a hotel in Paris")
- Greetings ("Hello", "Thanks")
- One-off questions ("What's the weather?")
- Temporary trip details unless they reveal a durable preference

Return a JSON array of strings. Each string is one standalone fact in first person when possible.
If nothing is worth storing, return [].
"""

EXTRACTION_USER_PROMPT = """Conversation to analyze:

User message:
{user_message}

Assistant response:
{assistant_response}

Planner output:
{planner_output}

Extract durable user facts as a JSON array of strings.
"""
