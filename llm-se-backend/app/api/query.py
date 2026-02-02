from fastapi import APIRouter, Depends

from app.auth.authentication import authenticate_user
from app.retrieval.retrieve import retrieve_authorized_documents
from app.models.request import QueryRequest
from app.gates.decision import decision_mode
from app.llm.invoke import generate_answer, select_documents_for_prompt
from app.audit.logger import log_audit_event

router = APIRouter()


@router.post("/query")
def query(
    request: QueryRequest,
    user=Depends(authenticate_user),
):
    """
    Main query endpoint.

    Flow:
    - Authenticate user
    - Retrieve authorized documents (RBAC + vector search)
    - Decide response mode (answer / soft_answer / no_info)
    - Optionally invoke LLM
    - Audit log every decision
    """

    documents = retrieve_authorized_documents(
        query=request.query,
        user=user,
    )

    mode = decision_mode(documents)

    max_similarity = max(d["similarity"] for d in documents) if documents else None

    if mode == "no_info":
        log_audit_event(
            request_id=request.request_id,
            user=user,
            query=request.query,
            decision_mode=mode,
            max_similarity=max_similarity,
            llm_called=False,
            sources=None,
        )

        return {
            "type": "no_info",
            "request_id": request.request_id,
            "reason": "insufficient_relevance",
        }

    selected_docs = select_documents_for_prompt(documents)

    if not selected_docs:
        selected_docs = sorted(
            documents,
            key=lambda d: d.get("similarity", 0),
            reverse=True,
        )[:3]

    answer = generate_answer(
        query=request.query,
        documents=selected_docs,
        soft=(mode == "soft_answer"),
    )

    sources = [
        {
            "source": doc["metadata"]["source"],
            "similarity": doc["similarity"],
        }
        for doc in selected_docs
    ]

    log_audit_event(
        request_id=request.request_id,
        user=user,
        query=request.query,
        decision_mode=mode,
        max_similarity=max_similarity,
        llm_called=True,
        sources=sources,
    )

    return {
        "type": "answer",
        "request_id": request.request_id,
        "data": {
            "answer": answer,
            "sources": sources,
        },
    }
