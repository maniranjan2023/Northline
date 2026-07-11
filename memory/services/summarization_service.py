"""
SummarizationService
--------------------
Uses the LLM to convert one travel run into short structured memories.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from memory.models import MemoryRecord, MemoryType


class SummarizationService:
    """Creates long-term memory records from a completed graph state."""

    def __init__(self, llm):
        self.llm = llm

    def summarize_travel_run(self, state: dict[str, Any]) -> list[MemoryRecord]:
        """
        Build structured memory items from one completed session.

        Input: final LangGraph state
        Output: list of MemoryRecord objects
        """
        user_id = state.get("user_id", "anonymous")
        user_query = state.get("user_query", "")
        itinerary = state.get("itinerary", "")

        prompt = f"""
Extract useful long-term travel memories from this run.

User query:
{user_query}

Itinerary:
{itinerary}

Return JSON array only. Each item must have:
- memory_type: one of preference, user_fact, success_pattern, summary
- content: one short sentence
- importance: number from 0.1 to 1.0

Example:
[
  {{"memory_type":"preference","content":"Prefers trips under ₹5L","importance":0.8}},
  {{"memory_type":"summary","content":"Planned a 7-day Japan trip with hotels and flights","importance":0.7}}
]
"""

        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content="You extract compact structured travel memories."),
                    HumanMessage(content=prompt),
                ]
            )
            parsed = self._parse_json_array(response.content)
        except Exception:
            parsed = []

        records: list[MemoryRecord] = []
        for item in parsed:
            memory_type = self._safe_memory_type(item.get("memory_type"))
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            records.append(
                MemoryRecord(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                    importance=float(item.get("importance", 0.5)),
                    metadata={"source_query": user_query},
                )
            )

        if not records and itinerary:
            records.append(
                MemoryRecord(
                    user_id=user_id,
                    memory_type=MemoryType.SUMMARY,
                    content=f"Planned trip: {user_query}",
                    importance=0.6,
                    metadata={"source_query": user_query},
                )
            )

        return records

    def _parse_json_array(self, text: str) -> list[dict]:
        """Parse LLM JSON output even if wrapped in markdown."""
        clean = text.strip()
        if "```" in clean:
            clean = re.sub(r"^```(?:json)?|```$", "", clean, flags=re.MULTILINE).strip()
        data = json.loads(clean)
        return data if isinstance(data, list) else []

    def _safe_memory_type(self, value: str | None) -> MemoryType:
        """Convert text to a valid MemoryType."""
        try:
            return MemoryType(value)
        except Exception:
            return MemoryType.SUMMARY
