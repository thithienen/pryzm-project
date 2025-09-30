from fastapi import APIRouter, HTTPException
from schemas import SourceRequest, SourceResponse, SourcePageResponse, EvidenceItem, ErrorResponse
from doc_repo import get_doc_repo
from llm.retriever import get_retriever
from llm.context_processor import process_context
import time

router = APIRouter(tags=["source"])


@router.get("/source/{doc_id}/{pageno}", response_model=SourcePageResponse)
async def get_source_page(doc_id: str, pageno: int) -> SourcePageResponse:
    """
    Get the full page text and metadata for a specific document and page.
    
    Args:
        doc_id: The document ID from docs.json
        pageno: The 1-indexed page number (must be >= 1)
        
    Returns:
        SourceResponse with doc_id, title, doc_date, url, pageno, and full text
        
    Raises:
        HTTPException: 404 if document or page not found, 400 if pageno < 1
    """
    # Validate pageno is 1-indexed
    if pageno < 1:
        raise HTTPException(
            status_code=400, 
            detail=ErrorResponse(
                error="Invalid page number", 
                detail="Page number must be >= 1 (1-indexed)"
            ).dict()
        )
    
    try:
        doc_repo = get_doc_repo()
        page_data = doc_repo.get_page(doc_id, pageno)
        
        if not page_data:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="not found",
                    detail="Document or page not found"
                ).dict()
            )
        
        return SourcePageResponse(
            doc_id=page_data['doc_id'],
            title=page_data['title'],
            doc_date=page_data['doc_date'],
            url=page_data['url'],
            pageno=page_data['pageno'],
            text=page_data['text']
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the error and return 500
        print(f"Error in get_source_page: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=ErrorResponse(
                error="Internal server error",
                detail=str(e)
            ).dict()
        )


@router.post("/sources", response_model=SourceResponse)
async def retrieve_sources(request: SourceRequest) -> SourceResponse:
    """
    Retrieve relevant sources for a query using hybrid search.
    
    Uses:
    - BM25 (FTS5) for keyword matching
    - FAISS for semantic similarity
    - RRF fusion to combine results
    - Cross-encoder reranking (optional)
    - Context processing for merging and citation formatting
    
    Args:
        request: SourceRequest with query and options
        
    Returns:
        SourceResponse with ranked evidence blocks
    """
    start_time = time.time()
    
    try:
        # Step 1: Hybrid retrieval
        retriever = get_retriever()
        search_results = retriever.retrieve(
            request.query,
            top_k=request.max_results,
            use_reranking=request.use_reranking
        )
        
        if not search_results:
            return SourceResponse(
                query=request.query,
                sources=[],
                metadata={
                    "total_sources": 0,
                    "reranking_used": request.use_reranking,
                    "message": "No sources found for query"
                },
                latency_ms=int((time.time() - start_time) * 1000)
            )
        
        # Step 2: Process context (merge chunks, format citations)
        context_data = process_context(
            search_results,
            query=request.query,
            max_context_tokens=32000,  # Large budget for sources endpoint
            context_fill_ratio=1.0  # Use all available sources
        )
        
        # Step 3: Convert to EvidenceItem format
        evidence_items = []
        for ev in context_data['evidence']:
            evidence_item = EvidenceItem(
                evidence_id=ev['evidence_id'],
                citation=ev['citation'],
                doc_id=ev['doc_id'],
                doc_title=ev['doc_title'],
                doctype=ev.get('doctype'),
                page_range=ev['page_range'],
                section_path=ev.get('section_path', []),
                text=ev['text'],
                source_url=ev['source_url'],
                chunk_ids=ev['chunk_ids'],
                token_count=ev['token_count'],
                # Include scores from original search results if available
                rerank_score=search_results[ev['evidence_id']-1].get('rerank_score') if ev['evidence_id'] <= len(search_results) else None,
                rrf_score=search_results[ev['evidence_id']-1].get('rrf_score') if ev['evidence_id'] <= len(search_results) else None,
                bm25_score=search_results[ev['evidence_id']-1].get('bm25_score') if ev['evidence_id'] <= len(search_results) else None,
                faiss_score=search_results[ev['evidence_id']-1].get('faiss_score') if ev['evidence_id'] <= len(search_results) else None
            )
            evidence_items.append(evidence_item)
        
        # Step 4: Return response
        latency_ms = int((time.time() - start_time) * 1000)
        
        return SourceResponse(
            query=request.query,
            sources=evidence_items,
            metadata={
                "total_sources": len(evidence_items),
                "total_tokens": context_data['metadata']['total_tokens'],
                "reranking_used": request.use_reranking,
                "blocks_merged": context_data['metadata'].get('total_blocks', 0)
            },
            latency_ms=latency_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in retrieve_sources: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Internal server error",
                detail=str(e)
            ).dict()
        )
