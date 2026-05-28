from __future__ import annotations

from functools import lru_cache
from groq import AsyncGroq

from app.config import settings

import structlog

log = structlog.get_logger()

# HyDE system prompt for generating hypothetical answers
HYDE_SYSTEM_PROMPT = (
    "You are an enterprise document assistant. Write a single-sentence hypothetical "
    "answer (max 30 words) that directly and factually answers the question. "
    "Do not include any preamble, introduction, or disclaimers."
)


@lru_cache(maxsize=1)
def _get_groq_client() -> AsyncGroq:
    """Return the singleton AsyncGroq client for HyDE generation."""
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


async def generate_hypothetical_answer(query: str) -> str | None:
    """
    Generate a hypothetical answer for a query using Groq LLM (async).

    This is the core of HyDE — the hypothetical answer gets embedded
    and used for vector search instead of the raw query.

    Args:
        query: The user's original question.

    Returns:
        The hypothetical answer text, or None if generation failed.
    """
    try:
        client = _get_groq_client()

        response = await client.chat.completions.create(
            model=settings.HYDE_MODEL_NAME,
            messages=[
                {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=50,
        )

        hypothetical = response.choices[0].message.content.strip()
        log.info("hyde_generated", query=query[:80], length=len(hypothetical))
        return hypothetical

    except Exception as e:
        log.warning("hyde_failed", error=str(e), query=query[:80])
        return None
