from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from retriever import get_retriever
from schemas import ContextItem, ErrorResponse

router = APIRouter(tags=["debug"])


class DebugRequest(BaseModel):
    query: str
    top_k: int = 10


@router.post("/v1/context-debug")
async def context_debug(request: DebugRequest):
    """
    Debug endpoint that returns the current top-k context for a query without calling the LLM.
    Handy for QA and won't touch your token budget.
    """
    try:
        retriever = get_retriever()
        retrieved_docs = retriever.retrieve(request.query, top_k=request.top_k, min_score=0.05)
        
        context_items = []
        for i, doc in enumerate(retrieved_docs, 1):
            context_item = ContextItem(
                rank=i,
                doc_id=doc['doc_id'],
                title=doc['title'],
                url=doc['url'],
                doc_date=doc['doc_date'],
                pageno=doc['pageno'],
                snippet=doc['snippet']
            )
            context_items.append(context_item)
        
        return {
            "query": request.query,
            "top_k": request.top_k,
            "context_count": len(context_items),
            "context": context_items
        }
        
    except Exception as e:
        print(f"Error in context_debug: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Internal server error",
                detail=str(e)
            ).dict()
        )
