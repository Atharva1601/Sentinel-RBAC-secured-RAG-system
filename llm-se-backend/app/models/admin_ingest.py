
from pydantic import BaseModel
from typing import Dict, Any


class PdfIngestRequest(BaseModel):
    pdf_filename: str
    metadata: Dict[str, Any]
