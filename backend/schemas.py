from pydantic import BaseModel
from typing import List, Optional


# ============================================================================
# Request Schemas
# ============================================================================

class AnswerRequest(BaseModel):
    """Request for answer generation"""
    prompt: str
    max_sources: Optional[int] = 15
    use_reranking: Optional[bool] = False  # Disabled by default for lightweight operation


class SourceRequest(BaseModel):
    """Request for source retrieval"""
    query: str
    max_results: Optional[int] = 15
    use_reranking: Optional[bool] = False  # Disabled by default for lightweight operation


# ============================================================================
# Response Schemas - New Hybrid System
# ============================================================================

class EvidenceItem(BaseModel):
    """Evidence block with citation"""
    evidence_id: int
    citation: str  # e.g., "[FY2026 Budget p.12-14]"
    doc_id: str
    doc_title: str
    doctype: Optional[str] = None
    date: Optional[str] = None  # Document date
    page_range: List[int]  # [start, end]
    section_path: List[str] = []
    text: str
    source_url: str  # URL with page anchor
    chunk_ids: List[str]  # Original chunk IDs
    token_count: int
    # Scores for debugging/transparency
    rerank_score: Optional[float] = None
    rrf_score: Optional[float] = None
    bm25_score: Optional[float] = None
    faiss_score: Optional[float] = None


class SourceResponse(BaseModel):
    """Response with retrieved sources"""
    query: str
    sources: List[EvidenceItem]
    metadata: dict
    latency_ms: int


class AnswerResponse(BaseModel):
    """Response with answer and sources"""
    answer_md: str
    sources: List[EvidenceItem]
    used_model: str
    latency_ms: int
    metadata: dict


# ============================================================================
# Legacy Schemas (kept for backward compatibility)
# ============================================================================

class ContextItem(BaseModel):
    """Legacy context item format"""
    rank: int
    doc_id: str
    title: str
    url: Optional[str] = ""
    doc_date: str
    pageno: int
    snippet: str


class SourcePageResponse(BaseModel):
    """Response for single page retrieval"""
    doc_id: str
    title: str
    doc_date: str
    url: str
    pageno: int
    text: str


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    error: str
    detail: str
