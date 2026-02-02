from pydantic import BaseModel
from typing import List, Literal, Optional


class Source(BaseModel):
    document_id: str


class AnswerData(BaseModel):
    text: str
    sources: List[Source]


class NoInfoData(BaseModel):
    reason: str = "insufficient_authorized_information"


class DeniedData(BaseModel):
    reason: str = "authorization_failed"


class QueryResponse(BaseModel):
    type: Literal["answer", "no_info", "denied"]
    request_id: str
    data: Optional[dict]
