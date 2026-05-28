import anyio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from app.auth.authentication import authenticate_user
from app.retrieval.qdrant_client import get_async_qdrant_client, get_collection_name
from app.models.admin_ingest import PdfIngestRequest
from app.embeddings.client import embed_batch
from app.config import settings

import structlog

log = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin"])


# Token-based recursive text splitter:
# Tries split boundaries in order: paragraph -> newline -> sentence -> word
# Token-based sizing ensures consistent LLM context consumption.
_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


async def run_ingestion_background(
    pdf_filename: str,
    owner_dept: str,
    min_role_level: int,
    min_clearance_level: int,
) -> None:
    """
    Perform the actual PDF text extraction, chunking, embedding,
    and storage in Qdrant in the background.
    """
    from app.db.database import SessionLocal
    from app.db.models import Document
    import uuid
    import io
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        doc_record = db.query(Document).filter(Document.filename == pdf_filename).first()
        if not doc_record or not doc_record.file_content:
            log.error("ingest_background_failed_missing_content", source=pdf_filename)
            return

        client = await get_async_qdrant_client()
        collection_name = get_collection_name()

        # Delete any existing chunks for this document in Qdrant before re-ingesting
        await client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=pdf_filename),
                    )
                ]
            ),
        )

        # Check for optional pytesseract OCR fallback
        try:
            import pytesseract
            has_pytesseract = True
        except ImportError:
            has_pytesseract = False

        ingested_at = datetime.now(timezone.utc).isoformat()
        all_chunks: list[str] = []
        all_metadatas: list[dict] = []
        chunk_index = 0
        num_pages = 0

        with pdfplumber.open(io.BytesIO(doc_record.file_content)) as pdf:
            num_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                
                # If text is empty or very short, attempt OCR fallback
                if not text or len(text.strip()) < 50:
                    if has_pytesseract:
                        try:
                            # Convert page to image at 150 DPI for OCR processing
                            img = page.to_image(resolution=150)
                            pil_img = img.original
                            ocr_text = pytesseract.image_to_string(pil_img)
                            if ocr_text and len(ocr_text.strip()) >= 50:
                                text = ocr_text
                                log.info("ocr_extraction_success", source=pdf_filename, page=page_num, char_count=len(text))
                        except Exception as ocr_err:
                            log.warning("ocr_extraction_failed", source=pdf_filename, page=page_num, error=str(ocr_err))
                    else:
                        log.info("ocr_skipped_missing_dependency", source=pdf_filename, page=page_num)

                if not text or not text.strip():
                    continue

                # Chunk this page's text
                page_chunks = _splitter.split_text(text)

                for chunk_text in page_chunks:
                    all_chunks.append(chunk_text)
                    all_metadatas.append({
                        "source": pdf_filename,
                        "page_number": page_num,
                        "chunk_index": chunk_index,
                        "owner_department": owner_dept,
                        "min_role_level": min_role_level,
                        "min_clearance_level": min_clearance_level,
                        "ingested_at": ingested_at,
                    })
                    chunk_index += 1

        if not all_chunks:
            raise ValueError("No text extracted from PDF (empty or OCR-only)")

        # Batch embed all chunks at once
        log.info(
            "ingest_embedding_background",
            source=pdf_filename,
            chunks=len(all_chunks),
        )
        embeddings = await anyio.to_thread.run_sync(embed_batch, all_chunks)

        # Store in Qdrant
        points = []
        for i, (chunk, embedding, meta) in enumerate(
            zip(all_chunks, embeddings, all_metadatas)
        ):
            payload = {**meta, "content": chunk}
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=payload,
                )
            )

        # Qdrant supports batch upsert — upload in chunks of 100
        BATCH_SIZE = 100
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            await client.upsert(
                collection_name=collection_name,
                points=batch,
            )

        # Update SQL to "ingested"
        doc_record = db.query(Document).filter(Document.filename == pdf_filename).first()
        if doc_record:
            doc_record.status = "ingested"
            db.commit()

        log.info(
            "ingest_complete_background",
            source=pdf_filename,
            chunks_added=len(all_chunks),
            pages_processed=num_pages,
        )

    except Exception as e:
        # Update SQL to "failed"
        try:
            doc_record = db.query(Document).filter(Document.filename == pdf_filename).first()
            if doc_record:
                doc_record.status = "failed"
                db.commit()
        except Exception:
            pass

        log.error("ingest_failed_background", source=pdf_filename, error=str(e))
    finally:
        db.close()


@router.post("/ingest/pdf")
async def ingest_pdf(
    payload: PdfIngestRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only PDF ingestion (non-blocking).

    Starts ingestion in the background and returns status "ingesting".
    """

    # Auth check
    if user["role_level"] < 3:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required",
        )

    pdf_filename = payload.pdf_filename
    metadata = payload.metadata

    # DB validation
    from app.db.database import SessionLocal
    from app.db.models import Document, Department

    db = SessionLocal()
    try:
        # Check if the document exists in the DB and has file content
        doc_record = db.query(Document).filter(Document.filename == pdf_filename).first()
        if not doc_record or not doc_record.file_content:
            raise HTTPException(
                status_code=404,
                detail=f"PDF document not found in database: {pdf_filename}",
            )

        owner_dept = metadata.get("owner_department", "shared")
        dept_exists = db.query(Department).filter(Department.name == owner_dept).first()
        if not dept_exists:
            raise HTTPException(
                status_code=400,
                detail=f"Department '{owner_dept}' does not exist"
            )

        # Check if document already exists and log re-ingestion
        client = await get_async_qdrant_client()
        collection_name = get_collection_name()

        existing, _ = await client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=pdf_filename),
                    )
                ]
            ),
            limit=1,
        )
        if existing:
            log.info("document_exists_proceeding_with_overwrite", source=pdf_filename)

        # Update document record as ingesting
        doc_record.status = "ingesting"
        doc_record.owner_department = owner_dept
        doc_record.min_role_level = metadata.get("min_role_level", 1)
        doc_record.min_clearance_level = metadata.get("min_clearance_level", 1)
        db.commit()

    except Exception as e:
        db.close()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Database validation failed: {str(e)}")
    finally:
        db.close()

    # Trigger background task for chunking and embedding
    background_tasks.add_task(
        run_ingestion_background,
        pdf_filename=pdf_filename,
        owner_dept=owner_dept,
        min_role_level=metadata.get("min_role_level", 1),
        min_clearance_level=metadata.get("min_clearance_level", 1),
    )

    return {
        "status": "ingesting",
        "source": pdf_filename,
        "message": "Ingestion started in the background",
    }
