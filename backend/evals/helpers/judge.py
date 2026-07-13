"""DeepEval judge model — Groq by default (uses GROQ_API_KEY)."""

from __future__ import annotations

import os
from functools import lru_cache

from deepeval.models import DeepEvalBaseLLM
from langchain_groq import ChatGroq


class GroqJudge(DeepEvalBaseLLM):
    """Wrap Groq ChatGroq as a DeepEval-compatible judge."""

    def __init__(self, model_name: str | None = None):
        # Set before super(): DeepEvalBaseLLM.__init__ calls load_model() immediately.
        self._model_name = model_name or os.getenv(
            "DEEPEVAL_JUDGE_MODEL", "llama-3.3-70b-versatile"
        )
        super().__init__(model=self._model_name)

    def load_model(self):
        name = getattr(self, "_model_name", None) or self.name
        return ChatGroq(model=name)

    def generate(self, prompt: str) -> str:
        chat = self.model or self.load_model()
        return str(chat.invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        chat = self.model or self.load_model()
        response = await chat.ainvoke(prompt)
        return str(response.content)

    def get_model_name(self) -> str:
        return f"groq/{self._model_name}"


@lru_cache(maxsize=1)
def get_eval_judge() -> GroqJudge:
    if not os.getenv("GROQ_API_KEY", "").strip():
        raise RuntimeError(
            "GROQ_API_KEY is required for DeepEval judge metrics. "
            "Set it in .env before running nightly/memory suites."
        )
    return GroqJudge()
