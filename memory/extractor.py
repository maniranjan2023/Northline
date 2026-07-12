"""LLM-based extraction of durable facts before Mem0 storage."""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from memory.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT
from memory.provider.base import BaseMemoryProvider

logger = logging.getLogger(__name__)


class MemoryExtractor:
    """Extracts durable user facts and stores them via the memory provider."""

    def __init__(self, llm, provider: BaseMemoryProvider):
        self._llm = llm
        self._provider = provider

    async def extract_facts(
        self,
        *,
        user_message: str,
        assistant_response: str,
        planner_output: str = "",
    ) -> list[str]:
        """Use LLM to decide which facts are worth long-term storage."""
        prompt = EXTRACTION_USER_PROMPT.format(
            user_message=user_message,
            assistant_response=assistant_response[:3000],
            planner_output=planner_output[:1500],
        )

        try:
            response = await self._llm.ainvoke([
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            return self._parse_facts(response.content)
        except Exception as exc:
            logger.error("Memory extraction LLM failed: %s", exc)
            return []

    def _parse_facts(self, raw: str) -> list[str]:
        text = (raw or "").strip()
        if not text:
            return []

        # Try JSON array first.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: extract [...] block from model output.
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass

        return []

    async def save_conversation(
        self,
        user_id: str,
        *,
        user_message: str,
        assistant_response: str,
        planner_output: str = "",
    ) -> int:
        """
        Extract durable facts and persist to Mem0.

        Returns number of facts stored.
        """
        facts = await self.extract_facts(
            user_message=user_message,
            assistant_response=assistant_response,
            planner_output=planner_output,
        )
        logger.info("Memory extraction: user_id=%s facts=%d", user_id, len(facts))

        stored = 0
        for fact in facts:
            try:
                await self._provider.add_fact(user_id, fact)
                stored += 1
                logger.info("Memory saved: user_id=%s fact=%r", user_id, fact[:80])
            except Exception as exc:
                logger.error("Memory save failed for user_id=%s: %s", user_id, exc)

        # Also store full turn so Mem0 can enrich over time (official pattern).
        if user_message and assistant_response:
            try:
                await self._provider.add_messages(
                    user_id,
                    [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": assistant_response[:4000]},
                    ],
                )
            except Exception as exc:
                logger.error("Mem0 conversation add failed: %s", exc)

        return stored
