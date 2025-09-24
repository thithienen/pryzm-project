from pydantic import BaseModel
from typing import List, Optional


class AnswerRequest(BaseModel):
    prompt: str


class ContextItem(BaseModel):
    rank: int
    doc_id: str
    title: str
    url: Optional[str] = ""
    doc_date: str
    pageno: int
    snippet: str


class AnswerResponse(BaseModel):
    answer_md: str
    context: List[ContextItem]
    used_model: str
    latency_ms: int


class SourceResponse(BaseModel):
    doc_id: str
    title: str
    doc_date: str
    url: str
    pageno: int
    text: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
