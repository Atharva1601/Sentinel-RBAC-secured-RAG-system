from typing import Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    request_id: str
    query: str
    session_id: Optional[str] = None

