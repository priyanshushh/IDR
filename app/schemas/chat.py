from pydantic import BaseModel

class ChatQueryRequest(BaseModel):
    query: str

class ChatQueryResponse(BaseModel):
    answer: str
    sources: list[dict]