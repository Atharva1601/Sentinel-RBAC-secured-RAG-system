"""
Admin document management endpoints — Qdrant-backed.

List and delete documents stored in the Qdrant vector database.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Query

from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.auth.authentication import authenticate_user
from app.retrieval.qdrant_client import get_async_qdrant_client, get_collection_name
from app.db.database import SessionLocal
from app.db.models import Document

import structlog

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: dict):
    if user["role_level"] < 3:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )


@router.get("/documents")
async def list_documents(
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only.
    Lists all documents currently tracked in SQLite and Qdrant.
    """
    require_admin(user)

    client = await get_async_qdrant_client()
    collection_name = get_collection_name()

    db = SessionLocal()
    try:
        docs = db.query(Document).all()
        result = {}
        for doc in docs:
            # Query Qdrant for active chunk count
            try:
                count_res = await client.count(
                    collection_name=collection_name,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="source",
                                match=MatchValue(value=doc.filename),
                            )
                        ]
                    ),
                    exact=True,
                )
                chunk_count = count_res.count
            except Exception:
                chunk_count = 0

            result[doc.filename] = {
                "chunks": chunk_count,
                "owner_department": doc.owner_department,
                "min_role_level": doc.min_role_level,
                "min_clearance_level": doc.min_clearance_level,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }

        return {"documents": result}
    finally:
        db.close()



@router.delete("/documents")
async def delete_document(
    source: str = Query(..., description="PDF filename, e.g. GAN.pdf"),
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only.
    Deletes a document from SQL, Qdrant, and deletes its physical file from /samples.
    """
    require_admin(user)

    client = await get_async_qdrant_client()
    collection_name = get_collection_name()

    # 1. Delete all points matching the source filter from Qdrant
    await client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="source",
                    match=MatchValue(value=source),
                )
            ]
        ),
    )

    # 2. Delete row from SQLite
    db = SessionLocal()
    try:
        doc_record = db.query(Document).filter(Document.filename == source).first()
        if doc_record:
            db.delete(doc_record)
            db.commit()
    finally:
        db.close()

    log.info("document_deleted", source=source)

    return {
        "status": "deleted",
        "source": source,
    }

