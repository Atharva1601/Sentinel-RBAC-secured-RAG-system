import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.auth.authentication import authenticate_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/upload/pdf")
def upload_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(authenticate_user),
):
    """
    Admin-only PDF upload.
    Saves PDF into /samples directory.
    Does NOT ingest or embed.
    """

    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="Admin privileges required")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    filename = os.path.basename(file.filename)

    from app.db.database import SessionLocal
    from app.db.models import Document

    db = SessionLocal()
    try:
        existing_doc = db.query(Document).filter(Document.filename == filename).first()
        if existing_doc:
            raise HTTPException(
                status_code=409,
                detail=f"File already registered in database: {filename}",
            )

        # Read PDF content bytes
        file_bytes = file.file.read()

        new_doc = Document(
            filename=filename,
            owner_department="shared",
            min_role_level=1,
            min_clearance_level=1,
            status="uploaded",
            file_content=file_bytes,
        )
        db.add(new_doc)
        db.commit()
    finally:
        db.close()


    return {
        "status": "uploaded",
        "filename": filename,
    }
