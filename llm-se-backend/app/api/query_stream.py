from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import anyio

from app.auth.authentication import authenticate_user
from app.config import settings
from app.retrieval.retrieve import retrieve_authorized_documents
from app.retrieval.contextualize import contextualize_query
from app.models.request import QueryRequest
from app.gates.decision import decision_mode
from app.llm.invoke import generate_answer_stream, select_documents_for_prompt
from app.audit.logger import log_audit_event
from app.cache.redis_client import get_cached_response, cache_response

import structlog

log = structlog.get_logger()

router = APIRouter()


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"data: {json.dumps(data)}\n\n"


def _fetch_conversation_history(session_id: str) -> list[dict]:
    """Fetch last 6 messages for a session from the DB."""
    from app.db.database import SessionLocal
    from app.db.models import ConversationMessage

    db = SessionLocal()
    try:
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
            .limit(6)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in messages]
    finally:
        db.close()


def _save_conversation_turn(session_id: str, user_query: str, assistant_answer: str) -> None:
    """Persist the Q+A turn to the conversation_messages table."""
    from app.db.database import SessionLocal
    from app.db.models import ConversationMessage

    db = SessionLocal()
    try:
        db.add(ConversationMessage(session_id=session_id, role="user", content=user_query))
        db.add(ConversationMessage(session_id=session_id, role="assistant", content=assistant_answer))
        db.commit()
    except Exception as e:
        log.warning("conversation_save_failed", session_id=session_id, error=str(e))
    finally:
        db.close()


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    user=Depends(authenticate_user),
):
    """
    Streaming query endpoint using Server-Sent Events (SSE) (async).

    Flow:
    1. Check Redis cache (return cached answer as SSE on hit)
    2. Fetch conversation history + contextualize query
    3. Retrieve + rerank documents
    4. Stream LLM response token-by-token
    5. Save conversation turn + cache response after stream completes
    """

    # ── Step 1: Redis cache check ─────────────────────────────
    cached = await anyio.to_thread.run_sync(get_cached_response, request.query, user)
    if cached:
        log.info("cache_hit_stream", query=request.query[:80])

        def cached_stream():
            # Replay cached answer as a single SSE burst
            if cached.get("type") == "no_info":
                yield _sse_event(cached)
            else:
                data = cached.get("data", {})
                yield _sse_event({
                    "type": "metadata",
                    "request_id": cached.get("request_id", request.request_id),
                    "sources": data.get("sources", []),
                })
                # Stream the cached answer word-by-word for consistent UX
                for word in data.get("answer", "").split(" "):
                    yield _sse_event({"type": "token", "content": word + " "})
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ── Step 2: Conversation history + contextualization ──────
    history = []
    if request.session_id:
        history = await anyio.to_thread.run_sync(_fetch_conversation_history, request.session_id)
        log.info(
            "conversation_history_fetched",
            session_id=request.session_id,
            messages=len(history),
        )

    effective_query = await contextualize_query(request.query, history)

    # ── Step 3: Retrieve ──────────────────────────────────────
    documents = await retrieve_authorized_documents(query=effective_query, user=user)
    mode = decision_mode(documents)

    max_similarity = (
        max(d.get("rerank_score", d.get("similarity", 0)) for d in documents)
        if documents else None
    )

    # ── no_info path ──────────────────────────────────────────
    if mode == "no_info":
        response = {
            "type": "no_info",
            "request_id": request.request_id,
            "reason": "insufficient_relevance",
        }
        log_audit_event(
            request_id=request.request_id,
            user=user,
            query=request.query,
            decision_mode=mode,
            max_similarity=max_similarity,
            llm_called=False,
            sources=None,
        )
        await anyio.to_thread.run_sync(cache_response, request.query, user, response)

        def no_info_stream():
            yield _sse_event(response)
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            no_info_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ── Step 4: Stream LLM response ───────────────────────────
    selected_docs = select_documents_for_prompt(documents)
    if not selected_docs:
        selected_docs = sorted(
            documents,
            key=lambda d: d.get("rerank_score", d.get("similarity", 0)),
            reverse=True,
        )[:settings.TOP_K_RERANK]

    sources = [
        {
            "source": doc["metadata"].get("source", "unknown"),
            "page_number": doc["metadata"].get("page_number"),
            "similarity": doc.get("rerank_score", doc.get("similarity")),
        }
        for doc in selected_docs
    ]

    async def answer_stream():
        # Metadata first
        yield _sse_event({
            "type": "metadata",
            "request_id": request.request_id,
            "sources": sources,
        })

        # Stream tokens
        full_answer_parts = []
        async for token in generate_answer_stream(
            query=effective_query,
            documents=selected_docs,
            soft=(mode == "soft_answer"),
        ):
            full_answer_parts.append(token)
            yield _sse_event({"type": "token", "content": token})

        yield "data: [DONE]\n\n"

        # ── Step 5: Save turn + cache after stream ─────────────
        full_answer = "".join(full_answer_parts)

        if request.session_id:
            await anyio.to_thread.run_sync(
                _save_conversation_turn,
                request.session_id,
                request.query,
                full_answer,
            )

        response_to_cache = {
            "type": "answer",
            "request_id": request.request_id,
            "data": {"answer": full_answer, "sources": sources},
        }
        await anyio.to_thread.run_sync(cache_response, request.query, user, response_to_cache)

        log_audit_event(
            request_id=request.request_id,
            user=user,
            query=request.query,
            decision_mode=mode,
            max_similarity=max_similarity,
            llm_called=True,
            sources=sources,
        )

    return StreamingResponse(
        answer_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
