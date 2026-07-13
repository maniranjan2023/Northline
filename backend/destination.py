"""Lightweight destination extraction (no MCP client import)."""

from __future__ import annotations


def extract_destination(query: str) -> str:
    from langchain_groq import ChatGroq

    llm = ChatGroq(model="llama-3.3-70b-versatile")
    prompt = f"""
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """
    response = llm.invoke(prompt)
    return response.content.strip()
