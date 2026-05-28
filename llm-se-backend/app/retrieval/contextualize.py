from __future__ import annotations

from functools import lru_cache
from typing import List, Dict

from groq import AsyncGroq

from app.config import settings

import structlog

log = structlog.get_logger()


CONTEXTUALIZE_PROMPT = (
    "Given this conversation history, rewrite the follow-up question "
    "as a standalone question. Only return the rewritten question, "
    "with no preamble or explanation."
)


@lru_cache(maxsize=1)
def _get_groq_client() -> AsyncGroq:
    """Return the singleton AsyncGroq client for query contextualization."""
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


async def contextualize_query(query: str, history: List[Dict]) -> str:
    """
    Rewrite a follow-up query as a standalone question (async).

    If history is empty (first message), returns the query unchanged.
    If rewriting fails, returns the original query (graceful fallback).

    Args:
        query: The user's follow-up question.
        history: List of conversation messages, each with 'role' and 'content'.
                 Only the last 4 messages (2 turns) are used.

    Returns:
        The rewritten standalone question, or the original query on failure.
    """
    if not history:
        return query

    try:
        client = _get_groq_client()

        # Use last 4 messages (2 turns) for context
        recent_history = history[-4:]
        history_text = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in recent_history
        )

        response = await client.chat.completions.create(
            model=settings.HYDE_MODEL_NAME,
            messages=[
                {"role": "system", "content": CONTEXTUALIZE_PROMPT},
                {
                    "role": "user",
                    "content": f"History:\n{history_text}\n\nFollow-up: {query}",
                },
            ],
            temperature=0.0,
            max_tokens=100,
        )

        rewritten = response.choices[0].message.content.strip()

        log.info(
            "query_contextualized",
            original=query[:80],
            rewritten=rewritten[:80],
        )
        return rewritten

    except Exception as e:
        log.warning("contextualize_failed", error=str(e), query=query[:80])
        return query
