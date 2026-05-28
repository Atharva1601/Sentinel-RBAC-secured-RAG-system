"""
Evaluation-only query endpoint that returns full context text.

Used by the RAGAS evaluation script. Not exposed in production.
Returns the answer, retrieved contexts (full text), sources,
and decision metadata needed for evaluation.
"""

from fastapi import APIRouter, Depends

from app.auth.authentication import authenticate_user
from app.config import settings
from app.retrieval.retrieve import retrieve_authorized_documents
from app.models.request import QueryRequest
from app.gates.decision import decision_mode
from app.llm.invoke import generate_answer, select_documents_for_prompt

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/query")
async def eval_query(
    request: QueryRequest,
    user=Depends(authenticate_user),
):
    """
    Evaluation query endpoint — returns full context text for RAGAS (async).

    Response includes:
    - answer: LLM-generated answer
    - contexts: list of full-text chunks used for grounding
    - sources: source metadata
    - decision_mode: answer / soft_answer / no_info
    - num_candidates: total retrieval candidates before reranking
    """
    documents = await retrieve_authorized_documents(
        query=request.query,
        user=user,
    )

    mode = decision_mode(documents)

    if mode == "no_info" or not documents:
        return {
            "type": "no_info",
            "request_id": request.request_id,
            "answer": "No relevant information found in the provided documents.",
            "contexts": [],
            "sources": [],
            "decision_mode": mode,
            "num_candidates": 0,
        }

    selected_docs = select_documents_for_prompt(documents)
    if not selected_docs:
        selected_docs = sorted(
            documents,
            key=lambda d: d.get("rerank_score", d.get("similarity", 0)),
            reverse=True,
        )[:settings.TOP_K_RERANK]

    answer = await generate_answer(
        query=request.query,
        documents=selected_docs,
        soft=(mode == "soft_answer"),
    )

    contexts = [doc["content"] for doc in selected_docs]
    sources = [
        {
            "source": doc["metadata"].get("source", "unknown"),
            "page_number": doc["metadata"].get("page_number"),
            "similarity": doc.get("rerank_score", doc.get("similarity")),
        }
        for doc in selected_docs
    ]

    return {
        "type": "answer",
        "request_id": request.request_id,
        "answer": answer,
        "contexts": contexts,
        "sources": sources,
        "decision_mode": mode,
        "num_candidates": len(documents),
    }
