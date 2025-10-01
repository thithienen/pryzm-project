from fastapi import APIRouter, HTTPException
from schemas import SourceRequest, SourceResponse, SourcePageResponse, EvidenceItem, ErrorResponse
from llm.retriever import get_retriever
from llm.context_processor import process_context
import time

router = APIRouter(tags=["source"])


@router.get("/source/{doc_id}/{pageno}", response_model=SourcePageResponse)
async def get_source_page(doc_id: str, pageno: int) -> SourcePageResponse:
    """
    Get the full page text and metadata for a specific document and page.
    
    Reconstructs the page from database chunks (lightweight mode).
    
    Args:
        doc_id: The document ID
        pageno: The 1-indexed page number (must be >= 1)
        
    Returns:
        SourcePageResponse with doc_id, title, doc_date, url, pageno, and full text
        
    Raises:
        HTTPException: 404 if document or page not found, 400 if pageno < 1
    """
    print(f"🟠 SOURCE: get_source_page called with doc_id={doc_id}, pageno={pageno}")
    
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
        # Reconstruct page from database chunks (lightweight mode)
        print(f"🟠 SOURCE: Reconstructing page from database chunks...")
        retriever = get_retriever()
        
        # Query all chunks for this doc_id and page
        cursor = retriever.conn.execute(
            """SELECT chunk_id, doc_id, doc_title, source_url, date, doctype,
                      page, section_path, text, is_table
               FROM chunks 
               WHERE doc_id = ? AND page = ?
               ORDER BY chunk_id""",
            (doc_id, pageno)
        )
        
        chunks = cursor.fetchall()
        print(f"🟠 SOURCE: Found {len(chunks)} chunks for doc_id={doc_id}, page={pageno}")
        
        if not chunks:
            print(f"🟠 SOURCE: ❌ No chunks found")
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error="not found",
                    detail=f"No data found for document '{doc_id}' page {pageno}"
                ).dict()
            )
        
        # Reconstruct page from chunks
        first_chunk = chunks[0]
        page_text = "\n\n".join(chunk['text'] for chunk in chunks)
        
        print(f"🟠 SOURCE: ✅ Reconstructed page text ({len(page_text)} chars from {len(chunks)} chunks)")
        
        return SourcePageResponse(
            doc_id=first_chunk['doc_id'],
            title=first_chunk['doc_title'],
            doc_date=first_chunk['date'] or first_chunk['doctype'] or 'Unknown',
            url=first_chunk['source_url'] or '',
            pageno=pageno,
            text=page_text
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the error and return 500
        print(f"🟠 SOURCE: ❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
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
                date=ev.get('date'),
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
