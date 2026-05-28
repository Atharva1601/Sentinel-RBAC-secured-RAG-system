from __future__ import annotations

from functools import lru_cache
from typing import List

from groq import Groq

from app.config import settings

import structlog

log = structlog.get_logger()

# ── Keywords that suggest multi-intent queries ────────────────
DECOMPOSE_KEYWORDS = {"and", "also", "compare", "both", "difference", "versus"}

# ── Decomposition system prompt ───────────────────────────────
DECOMPOSE_PROMPT = (
    "You are a query decomposition assistant. Given a complex question, "
    "break it into 2-3 simple, focused sub-questions. Each sub-question "
    "should be independently searchable. Return only the sub-questions, "
    "one per line, without numbering or bullets."
)


@lru_cache(maxsize=1)
def _get_groq_client() -> Groq:
    """Return the singleton Groq client for query decomposition."""
    return Groq(api_key=settings.GROQ_API_KEY)


def should_decompose(query: str) -> bool:
    """
    Determine if a query should be decomposed into sub-questions.

    Gate conditions (both must be true):
    1. Query has more than 12 words (short queries are usually single-intent)
    2. Query contains at least one decomposition keyword

    This prevents unnecessary decomposition of simple queries that happen
    to contain a keyword (e.g., "What is the leave and attendance policy?").
    """
    words = query.lower().split()
    if len(words) <= 12:
        return False
    return any(kw in words for kw in DECOMPOSE_KEYWORDS)


def decompose_query(query: str) -> List[str]:
    """
    Decompose a complex query into 2-3 focused sub-questions using Groq.

    If decomposition fails for any reason, returns the original query
    as a single-element list (graceful fallback).

    Args:
        query: The complex user query.

    Returns:
        List of 2-3 sub-questions, or [query] on failure.
    """
    try:
        client = _get_groq_client()

        response = client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": DECOMPOSE_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()

        # Parse sub-questions (one per line, filter empty lines)
        sub_queries = [
            line.strip()
            for line in raw.split("\n")
            if line.strip() and len(line.strip()) > 5
        ]

        # Sanity check: must produce 2-3 sub-queries
        if len(sub_queries) < 2:
            log.warning("decompose_too_few", query=query[:80], result=raw)
            return [query]

        if len(sub_queries) > 3:
            sub_queries = sub_queries[:3]

        log.info(
            "decompose_done",
            query=query[:80],
            sub_queries=sub_queries,
        )
        return sub_queries

    except Exception as e:
        log.warning("decompose_failed", error=str(e), query=query[:80])
        return [query]
