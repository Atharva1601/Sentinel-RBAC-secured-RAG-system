from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Dict, AsyncGenerator, List

import groq
from groq import AsyncGroq

from app.config import settings

import structlog

log = structlog.get_logger()


async def call_with_retry(
    client_fn,
    *args,
    max_retries: int = 5,
    initial_delay: float = 2.0,
    **kwargs,
):
    """
    Call a Groq API function with automatic retry and exponential backoff
    when hitting rate limits (RateLimitError).

    Includes immediate model fallback if daily token/request quotas are exhausted.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await client_fn(*args, **kwargs)
        except groq.RateLimitError as e:
            msg = str(e).lower()

            # If hit by daily token limit (TPD) or daily request limit (RPD), fall back to 8B model
            if "tokens per day" in msg or "tpd" in msg or "daily" in msg:
                if "model" in kwargs and kwargs["model"] == settings.LLM_MODEL_NAME:
                    fallback_model = "llama-3.1-8b-instant"
                    log.warning(
                        "groq_daily_rate_limit_fallback",
                        model=kwargs["model"],
                        fallback_model=fallback_model,
                        error=str(e),
                    )
                    kwargs["model"] = fallback_model
                    # Try execution immediately with fallback model
                    try:
                        return await client_fn(*args, **kwargs)
                    except Exception as fallback_err:
                        log.error("groq_fallback_failed", error=str(fallback_err))
                        raise e from fallback_err

            if attempt == max_retries - 1:
                raise
            
            # Default wait time
            wait_time = delay
            
            # Parse wait time from message if possible (e.g. "Please try again in 13.09s.")
            msg_str = str(e)
            if "try again in" in msg_str:
                try:
                    parts = msg_str.split("try again in")
                    if len(parts) > 1:
                        seconds_str = parts[1].strip().split("s")[0].strip()
                        wait_time = float(seconds_str) + 0.5
                except Exception:
                    pass
            
            log.warning("groq_rate_limit_exceeded", attempt=attempt, wait_time=wait_time, error=str(e))
            await asyncio.sleep(wait_time)
            delay *= 2


# Module-level singleton Groq client
@lru_cache(maxsize=1)
def _get_groq_client() -> AsyncGroq:
    """Return the singleton AsyncGroq client."""
    return AsyncGroq(api_key=settings.GROQ_API_KEY)


# System prompts (unchanged from original)

SYSTEM_PROMPT = """
You are an enterprise knowledge assistant.

You must answer using ONLY the provided context.
Do NOT use external knowledge, assumptions, or prior training data.

Rules:
- If the answer is fully supported by the context, answer clearly and concisely.
- If the context only partially answers the question, provide the partial answer
  and explicitly state what information is missing.
- If the context is irrelevant or does not contain the answer, respond with:
  "No relevant information found in the provided documents."

Formatting:
- Use bullet points for procedures or lists.
- Use short, clear paragraphs for explanations.
- Do not mention embeddings, retrieval, chunking, or system internals.

Tone:
- Professional
- Clear
- Practical
- Suitable for enterprise documentation and manuals.
"""

SOFT_MODE_NOTE = """
You are an enterprise knowledge assistant working with internal documents
such as manuals, policies, guides, and technical documentation.

Guidelines:
- Use ONLY the provided context.
- You MAY rephrase, summarize, and connect related statements found
  across the retrieved content.
- If the answer is partially supported, provide the best possible answer
  based on available information.
- Clearly state limitations ONLY if a critical detail is missing.
- Avoid saying "No relevant information found" unless the context is truly unrelated.

Summarization behavior:
- If asked to summarize a topic, produce a coherent summary using all
  relevant fragments found in the context.
- If asked to summarize a document, give a high-level overview even if
  only parts of the document are retrieved.
- If the summary is incomplete, add a short note such as:
  "This summary is based on the available sections of the document."

Restrictions:
- Do NOT introduce external facts, definitions, or assumptions.
- Do NOT speculate beyond what is implied in the documents.

Tone:
- Professional
- Helpful
- Explanatory
- Optimized for enterprise users reading internal documentation.
"""


PROMPT_SIMILARITY_THRESHOLD = 0.55


def select_documents_for_prompt(documents, max_docs=None):
    """
    Select top-N most relevant documents for LLM grounding.
    Do NOT over-filter — allow enough context for explanation.
    """

    if not documents:
        return []

    if max_docs is None:
        max_docs = settings.TOP_K_RERANK

    sorted_docs = sorted(
        documents,
        key=lambda d: d.get("rerank_score", d.get("similarity", 0)),
        reverse=True,
    )

    return sorted_docs[:max_docs]


def build_user_prompt(query: str, documents: List[Dict]) -> str:
    """
    Build a grounded user prompt using retrieved documents.

    Includes page citations in evidence headers when available:
    [Evidence 1 -- policy.pdf, Page 4]
    """

    context_blocks = []

    for i, doc in enumerate(documents, start=1):
        meta = doc.get("metadata", {})
        source = meta.get("source", "unknown")
        page_number = meta.get("page_number")

        if page_number:
            header = f"[Evidence {i} -- {source}, Page {page_number}]"
        else:
            header = f"[Evidence {i} -- {source}]"

        context_blocks.append(f"{header}\n{doc['content']}")

    context_text = "\n\n".join(context_blocks)

    return f"""Answer the question strictly using the information below.

{context_text}

Question:
{query}
"""


async def generate_answer(
    query: str,
    documents: List[Dict],
    soft: bool = False,
) -> str:
    """
    Generate a grounded answer using Groq LLM (blocking/async).
    """
    client = _get_groq_client()

    system_prompt = SYSTEM_PROMPT
    if soft:
        system_prompt = SYSTEM_PROMPT + "\n" + SOFT_MODE_NOTE

    messages = [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
        {
            "role": "user",
            "content": build_user_prompt(query, documents),
        },
    ]

    response = await call_with_retry(
        client.chat.completions.create,
        model=settings.LLM_MODEL_NAME,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    return response.choices[0].message.content.strip()


async def generate_answer_stream(
    query: str,
    documents: List[Dict],
    soft: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Generate a grounded answer using Groq LLM (streaming).

    Yields text chunks as they arrive from the Groq API.
    Used by the SSE streaming endpoint.
    """
    client = _get_groq_client()

    system_prompt = SYSTEM_PROMPT
    if soft:
        system_prompt = SYSTEM_PROMPT + "\n" + SOFT_MODE_NOTE

    messages = [
        {
            "role": "system",
            "content": system_prompt.strip(),
        },
        {
            "role": "user",
            "content": build_user_prompt(query, documents),
        },
    ]

    stream = await call_with_retry(
        client.chat.completions.create,
        model=settings.LLM_MODEL_NAME,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
