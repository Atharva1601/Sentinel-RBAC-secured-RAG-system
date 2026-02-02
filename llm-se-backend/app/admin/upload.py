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

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    filename = os.path.basename(file.filename)
    save_path = os.path.join(SAMPLES_DIR, filename)

    if os.path.exists(save_path):
        raise HTTPException(
            status_code=409,
            detail=f"File already exists: {filename}",
        )

    with open(save_path, "wb") as f:
        f.write(file.file.read())

    return {
        "status": "uploaded",
        "filename": filename,
    }
