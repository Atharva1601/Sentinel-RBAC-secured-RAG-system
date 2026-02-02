from fastapi import APIRouter, Depends, HTTPException, Query
from collections import defaultdict

from app.auth.authentication import authenticate_user
from app.retrieval.chroma_client import get_chroma_collection

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: dict):
    if user["role_level"] < 3:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )


@router.get("/documents")
def list_documents(
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only.
    Lists all documents currently stored in Chroma,
    grouped by source (PDF filename).
    """
    require_admin(user)

    collection = get_chroma_collection()

    results = collection.get(include=["metadatas"])
    metadatas = results.get("metadatas", [])

    documents = defaultdict(lambda: {
        "chunks": 0,
        "owner_department": None,
        "min_role_level": None,
        "min_clearance_level": None,
    })

    for meta in metadatas:
        source = meta.get("source", "unknown")
        documents[source]["chunks"] += 1
        documents[source]["owner_department"] = meta.get("owner_department")
        documents[source]["min_role_level"] = meta.get("min_role_level")
        documents[source]["min_clearance_level"] = meta.get("min_clearance_level")

    return {
        "documents": documents
    }


@router.delete("/documents")
def delete_document(
    source: str = Query(..., description="PDF filename, e.g. GAN.pdf"),
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only.
    Deletes all chunks belonging to a document (by source filename).
    """
    require_admin(user)

    collection = get_chroma_collection()

    before = collection.count()

    collection.delete(
        where={"source": {"$eq": source}}
    )

    after = collection.count()

    return {
        "status": "deleted",
        "source": source,
        "before": before,
        "after": after,
    }
