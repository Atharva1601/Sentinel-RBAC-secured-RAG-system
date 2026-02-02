from pydantic import BaseModel


class QueryRequest(BaseModel):
    request_id: str
    query: str
