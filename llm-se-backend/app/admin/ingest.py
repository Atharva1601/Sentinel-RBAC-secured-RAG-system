import os
import uuid
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pypdf import PdfReader

from app.auth.authentication import authenticate_user
from app.retrieval.chroma_client import get_chroma_collection
from app.models.admin_ingest import PdfIngestRequest
from app.embeddings.hf_client import embed_text  # ✅ NEW IMPORT

router = APIRouter(prefix="/admin", tags=["admin"])


CHUNK_SIZE = 900
CHUNK_OVERLAP = 180


def chunk_text(text: str):
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


@router.post("/ingest/pdf")
def ingest_pdf(
    payload: PdfIngestRequest,
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only PDF ingestion.

    payload:
    {
        "pdf_filename": "attention.pdf",
        "metadata": {
            "owner_department": "shared",
            "min_role_level": 2,
            "min_clearance_level": 2
        }
    }
    """

    if user["role_level"] < 3:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )

    pdf_filename = payload.pdf_filename
    metadata = payload.metadata

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
    pdf_path = os.path.join(SAMPLES_DIR, pdf_filename)

    if not os.path.exists(pdf_path):
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found: {pdf_filename}",
        )

    reader = PdfReader(pdf_path)

    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

    if not full_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text extracted from PDF (OCR not enabled yet)",
        )

    chunks = chunk_text(full_text)

    collection = get_chroma_collection()
    before = collection.count()

    enriched_metadata = {
        **metadata,
        "source": pdf_filename,
    }

    doc_topic = pdf_filename.replace(".pdf", "")

    SEMANTIC_PREFIX = (
        f"This document discusses the topic: {doc_topic}. "
        f"It contains technical and explanatory information.\n\n"
    )

    embeddings = [embed_text(SEMANTIC_PREFIX + chunk) for chunk in chunks]
    collection.add(
        ids=[str(uuid.uuid4()) for _ in chunks],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[enriched_metadata] * len(chunks),
    )

    after = collection.count()

    return {
        "status": "ingested",
        "source": pdf_filename,
        "chunks_added": len(chunks),
        "before": before,
        "after": after,
    }
