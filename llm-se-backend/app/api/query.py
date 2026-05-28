from fastapi import APIRouter, Depends
import anyio

from app.auth.authentication import authenticate_user
from app.config import settings
from app.retrieval.retrieve import retrieve_authorized_documents
from app.retrieval.contextualize import contextualize_query
from app.models.request import QueryRequest
from app.gates.decision import decision_mode
from app.llm.invoke import generate_answer, select_documents_for_prompt
from app.audit.logger import log_audit_event
from app.cache.redis_client import get_cached_response, cache_response

import structlog

log = structlog.get_logger()

router = APIRouter()


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


@router.post("/query")
async def query(
    request: QueryRequest,
    user=Depends(authenticate_user),
):
    """
    Main query endpoint (async).

    Flow:
    1. Check Redis cache (return immediately on hit)
    2. Fetch conversation history (if session_id provided)
    3. Contextualize query (rewrite follow-ups as standalone questions)
    4. Retrieve authorized documents (RBAC + vector search + rerank)
    5. Decision gate → answer / soft_answer / no_info
    6. Generate answer (LLM)
    7. Store conversation turn in DB
    8. Cache response in Redis
    9. Audit log
    """

    # Check Redis cache
    cached = await anyio.to_thread.run_sync(get_cached_response, request.query, user)
    if cached:
        log.info("cache_hit_returning", query=request.query[:80])
        return cached

    # Fetch conversation history
    history = []
    if request.session_id:
        history = await anyio.to_thread.run_sync(_fetch_conversation_history, request.session_id)
        log.info(
            "conversation_history_fetched",
            session_id=request.session_id,
            messages=len(history),
        )

    # Perform query contextualization
    effective_query = await contextualize_query(request.query, history)

    # Retrieve documents and check decision gate
    documents = await retrieve_authorized_documents(
        query=effective_query,
        user=user,
    )

    mode = decision_mode(documents)

    max_similarity = max(d.get("rerank_score", d.get("similarity", 0)) for d in documents) if documents else None

    # Handle no_info fallback path
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
        return response

    # Generate answer using grounded context
    selected_docs = select_documents_for_prompt(documents)
    if not selected_docs:
        selected_docs = sorted(
            documents,
            key=lambda d: d.get("rerank_score", d.get("similarity", 0)),
            reverse=True,
        )[:settings.TOP_K_RERANK]

    answer = await generate_answer(
        query=effective_query,
        documents=selected_docs,
        soft=(mode == "soft_answer"),
    )

    sources = [
        {
            "source": doc["metadata"].get("source", "unknown"),
            "page_number": doc["metadata"].get("page_number"),
            "similarity": doc.get("rerank_score", doc.get("similarity")),
        }
        for doc in selected_docs
    ]

    response = {
        "type": "answer",
        "request_id": request.request_id,
        "data": {
            "answer": answer,
            "sources": sources,
        },
    }

    # Store conversation turn
    if request.session_id:
        await anyio.to_thread.run_sync(
            _save_conversation_turn,
            request.session_id,
            request.query,
            answer,
        )

    # Cache response
    await anyio.to_thread.run_sync(cache_response, request.query, user, response)

    # Log audit event
    log_audit_event(
        request_id=request.request_id,
        user=user,
        query=request.query,
        decision_mode=mode,
        max_similarity=max_similarity,
        llm_called=True,
        sources=sources,
    )

    return response
