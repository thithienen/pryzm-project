from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import time
import re
import json
from llm.llm import openrouter_client
from llm.retriever import get_retriever
from llm.context_processor import process_context
from settings import OPENROUTER_MODEL
from schemas import AnswerRequest, AnswerResponse, EvidenceItem, ErrorResponse

router = APIRouter(tags=["answer"])


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(request: AnswerRequest) -> AnswerResponse:
    """
    Answer a question using retrieval-augmented generation with hybrid search.
    
    Process:
    1. Run hybrid retrieval (BM25 + FAISS + RRF + reranking)
    2. Process context (merge chunks, format citations)
    3. Build evidence blocks for LLM with proper citations
    4. Compose system + user messages for LLM
    5. Call OpenRouter model and get response
    6. Validate citations and return structured response
    
    Args:
        request: AnswerRequest with prompt and options
        
    Returns:
        AnswerResponse with answer and cited sources
    """
    start_time = time.time()
    print(f"\n🟢 BACKEND: ===== NEW REQUEST =====")
    print(f"🟢 BACKEND: Received question: {request.prompt}")
    print(f"🟢 BACKEND: max_sources={request.max_sources}, use_reranking={request.use_reranking}, use_web_search={request.use_web_search}")
    
    try:
        # Step 1: Decide on search strategy
        if request.use_web_search:
            print(f"🟢 BACKEND: Step 1 - Web search mode enabled, skipping local retrieval")
            search_results = []
            context_data = {'evidence': [], 'metadata': {'total_sources': 0, 'message': 'Web search mode'}}
        else:
            # Step 1: Run hybrid retrieval
            print(f"🟢 BACKEND: Step 1 - Getting retriever...")
            retriever = get_retriever()
            print(f"🟢 BACKEND: Step 1 - Retriever obtained, running search...")
            step_start = time.time()
            search_results = retriever.retrieve(
                request.prompt,
                top_k=request.max_sources,
                use_reranking=request.use_reranking
            )
            step_elapsed = time.time() - step_start
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: Step 1 - ✅ Search completed in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - found {len(search_results) if search_results else 0} results")
            
            # Step 2: Check if we have results
            print(f"🟢 BACKEND: Step 2 - Checking results...")
            if not search_results:
                print(f"🟢 BACKEND: Step 2 - ⚠️ No search results found")
                return AnswerResponse(
                    answer_md="My local knowledge base lacks sufficient context on this topic for a reliable response. Would you like me to search the web for more details?",
                    sources=[],
                    used_model=OPENROUTER_MODEL,
                    latency_ms=int((time.time() - start_time) * 1000),
                    metadata={
                        "total_sources": 0,
                        "reranking_used": request.use_reranking,
                        "message": "No search results found",
                        "suggest_web_search": True
                    },
                    used_web_search=False
                )
        
        # Step 3: Process context (merge chunks, format citations, pack within budget)
        if not request.use_web_search:
            print(f"🟢 BACKEND: Step 3 - Processing context...")
            step_start = time.time()
            context_data = process_context(
                search_results,
                query=request.prompt,
                max_context_tokens=30000,  # Reduced from 60000 for faster LLM response
                context_fill_ratio=0.55,  # Reduced from 70% to 55% for speed
                max_evidence_blocks=7,  # Limit to 7 evidence blocks max
                max_block_chars=800,  # Truncate each block to 800 chars max
                text_similarity_threshold=0.85  # Remove highly similar chunks
            )
            step_elapsed = time.time() - step_start
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: Step 3 - ✅ Context processed in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - {len(context_data['evidence'])} evidence blocks")
            
            if not context_data['evidence']:
                print(f"🟢 BACKEND: Step 3 - ⚠️ No evidence after processing")
                return AnswerResponse(
                    answer_md="My local knowledge base lacks sufficient context on this topic for a reliable response. Would you like me to search the web for more details?",
                    sources=[],
                    used_model=OPENROUTER_MODEL,
                    latency_ms=int((time.time() - start_time) * 1000),
                    metadata={**context_data['metadata'], "suggest_web_search": True},
                    used_web_search=False
                )
        else:
            print(f"🟢 BACKEND: Step 3 - Skipping context processing for web search mode")
        
        # Step 4: Build context for LLM with citations
        if request.use_web_search:
            print(f"🟢 BACKEND: Step 4 - Building web search messages...")
            step_start = time.time()
            
            # Step 5: Compose messages for web search LLM
            print(f"🟢 BACKEND: Step 5 - Composing web search LLM messages...")
            system_message = """You are a helpful assistant with access to current web information. Answer the user's question using your web search capabilities to find the most up-to-date and relevant information.

INSTRUCTIONS:
1. Search the web for current information related to the question
2. PRIORITIZE reliable sources: government websites (.gov), educational institutions (.edu), and reputable organizations (.org)
3. Avoid commercial websites (.com) unless they are well-established, authoritative sources
4. Provide accurate, well-sourced information with proper citations
5. Include relevant details and context
6. Format your response in clear markdown
7. If you find conflicting information, mention the different perspectives
8. Always cite your sources with clickable links
9. At the end of your response, always ask if the user would like you to search for additional information on the web"""

            user_message = f"""Please search the web for current information to answer this question comprehensively."""
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            step_elapsed = time.time() - step_start
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: Step 5 - ✅ Web search messages composed in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s)")
        else:
            print(f"🟢 BACKEND: Step 4 - Building evidence blocks...")
            step_start = time.time()
            evidence_blocks = []
            for ev in context_data['evidence']:
                evidence_blocks.append(
                    f"[{ev['evidence_id']}] {ev['citation']}\n{ev['text']}"
                )
            
            context_block = "\n\n".join(evidence_blocks)
            step_elapsed = time.time() - step_start
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: Step 4 - ✅ Built {len(evidence_blocks)} evidence blocks in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s) - {len(context_block)} chars")
            
            # Step 5: Compose messages for LLM
            print(f"🟢 BACKEND: Step 5 - Composing LLM messages...")
            step_start = time.time()
            system_message = """You are a helpful assistant that answers questions using ONLY information from your knowledge base and the documents available to you.

CRITICAL RULES:
1. ONLY use information from the EVIDENCE blocks below (these are documents from your knowledge base)
2. Cite EVERY claim using [n] where n is the evidence number
3. If evidence is insufficient, explicitly say "Insufficient evidence"
4. Prefer newer sources when multiple sources cover the same topic
5. Use concise, clear language
6. Format response in markdown with bullet points where appropriate
7. When introducing your answer, say things like "Based on my knowledge base" or "According to the documents I have" rather than "Based on the provided evidence"

When citing:
- Place [n] immediately after the relevant statement
- You can cite multiple sources like [1][3] if needed
- Do not invent or assume information not in the evidence"""

            user_message = f"""Question: {request.prompt}

EVIDENCE FROM YOUR KNOWLEDGE BASE:
{context_block}

Please answer the question using ONLY information from your knowledge base above. Remember to cite every claim with [n]."""
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            step_elapsed = time.time() - step_start
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: Step 5 - ✅ Messages composed in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s)")
        
        # Step 6: Call LLM
        model_suffix = ":online" if request.use_web_search else ""
        print(f"🟢 BACKEND: Step 6 - Calling LLM (model: {OPENROUTER_MODEL}{model_suffix}, web_search: {request.use_web_search})...")
        step_start = time.time()
        response_text = await openrouter_client.send_messages(
            messages,
            max_tokens=4000,
            temperature=0.3,
            use_web_search=request.use_web_search
        )
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 6 - ✅ LLM response received in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - {len(response_text) if response_text else 0} chars")
        
        if not response_text:
            print(f"🟢 BACKEND: Step 6 - ❌ No response from LLM")
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="LLM Error",
                    detail="Failed to get response from LLM"
                ).dict()
            )
        
        # Step 7: Validate citations
        print(f"🟢 BACKEND: Step 7 - Validating citations...")
        step_start = time.time()
        citation_pattern = r'\[(\d+)\]'
        citations_found = re.findall(citation_pattern, response_text)
        
        if not citations_found:
            # No citations found - replace with proper no-evidence message
            response_text = "My local knowledge base lacks sufficient context on this topic for a reliable response. Would you like me to search the web for more details?"
        else:
            # Validate that citation numbers are valid
            max_evidence_num = len(context_data['evidence'])
            invalid_citations = []
            
            for citation_str in set(citations_found):  # Use set to check unique citations
                citation_num = int(citation_str)
                if citation_num < 1 or citation_num > max_evidence_num:
                    invalid_citations.append(citation_num)
            
            if invalid_citations:
                response_text = "My local knowledge base lacks sufficient context on this topic for a reliable response. Would you like me to search the web for more details?"
        
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 7 - ✅ Citations validated in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s) - {len(set(citations_found)) if citations_found else 0} unique citations")
        
        # Step 8: Convert evidence to EvidenceItem format
        print(f"🟢 BACKEND: Step 8 - Converting evidence to response format...")
        step_start = time.time()
        evidence_items = []
        
        if not request.use_web_search:
            for ev in context_data['evidence']:
                # Find corresponding search result to get scores
                source_idx = ev['evidence_id'] - 1
                orig_result = search_results[source_idx] if source_idx < len(search_results) else {}
                
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
                    rerank_score=orig_result.get('rerank_score'),
                    rrf_score=orig_result.get('rrf_score'),
                    bm25_score=orig_result.get('bm25_score'),
                    faiss_score=orig_result.get('faiss_score')
                )
                evidence_items.append(evidence_item)
        else:
            # For web search, create a placeholder evidence item indicating web sources were used
            evidence_item = EvidenceItem(
                evidence_id=1,
                citation="Web Search Results",
                doc_id="web_search",
                doc_title="Current Web Information",
                doctype="web",
                date="current",
                page_range=[1],
                section_path=["web"],
                text="Information sourced from current web search results",
                source_url="web://search",
                chunk_ids=["web_1"],
                token_count=len(response_text) if response_text else 0
            )
            evidence_items.append(evidence_item)
        
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 8 - ✅ Evidence converted in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s)")
        
        # Step 9: Return structured response
        latency_ms = int((time.time() - start_time) * 1000)
        print(f"🟢 BACKEND: Step 9 - Building final response (total latency: {latency_ms}ms / {total_elapsed:.2f}s)...")
        
        return AnswerResponse(
            answer_md=response_text,
            sources=evidence_items,
            used_model=OPENROUTER_MODEL,
            latency_ms=latency_ms,
            metadata={
                "total_sources": len(evidence_items),
                "total_tokens": context_data['metadata'].get('total_tokens', 0),
                "target_tokens": context_data['metadata'].get('target_tokens', 0),
                "fill_ratio": context_data['metadata'].get('fill_ratio', 0),
                "blocks_truncated": context_data['metadata'].get('blocks_truncated', 0),
                "reranking_used": request.use_reranking,
                "citations_found": len(set(citations_found)) if citations_found else 0,
                "web_search_used": request.use_web_search
            },
            used_web_search=request.use_web_search
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        print(f"🟢 BACKEND: ❌ HTTPException occurred, re-raising")
        raise
    except Exception as e:
        # Log the error (in production, use proper logging)
        elapsed = time.time() - start_time
        print(f"🟢 BACKEND: ❌ Exception after {elapsed:.2f}s: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Internal server error",
                detail=str(e)
            ).dict()
        )


@router.post("/answer/stream")
async def answer_question_stream(request: AnswerRequest):
    """
    Stream answer using retrieval-augmented generation with hybrid search.
    
    Returns Server-Sent Events (SSE) stream with:
    - metadata: Initial metadata with sources
    - content: Text chunks as they're generated
    - done: Final completion message
    
    Args:
        request: AnswerRequest with prompt and options
        
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def generate_stream():
        start_time = time.time()
        print(f"\n🟢 BACKEND: ===== NEW STREAMING REQUEST =====")
        print(f"🟢 BACKEND: Received question: {request.prompt}")
        print(f"🟢 BACKEND: max_sources={request.max_sources}, use_reranking={request.use_reranking}, use_web_search={request.use_web_search}")
        
        try:
            # Step 1: Decide on search strategy
            if request.use_web_search:
                print(f"🟢 BACKEND: Step 1 - Web search mode enabled, skipping local retrieval")
                search_results = []
                context_data = {'evidence': [], 'metadata': {'total_sources': 0, 'message': 'Web search mode'}}
            else:
                # Step 1: Run hybrid retrieval
                print(f"🟢 BACKEND: Step 1 - Getting retriever...")
                retriever = get_retriever()
                print(f"🟢 BACKEND: Step 1 - Retriever obtained, running search...")
                step_start = time.time()
                search_results = retriever.retrieve(
                    request.prompt,
                    top_k=request.max_sources,
                    use_reranking=request.use_reranking
                )
                step_elapsed = time.time() - step_start
                total_elapsed = time.time() - start_time
                print(f"🟢 BACKEND: Step 1 - ✅ Search completed in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - found {len(search_results) if search_results else 0} results")
                
                # Step 2: Check if we have results
                if not search_results:
                    # Send error event
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant documents found for this query.'})}\n\n"
                    return
            
            # Step 3: Process context
            if not request.use_web_search:
                print(f"🟢 BACKEND: Step 3 - Processing context...")
                step_start = time.time()
                context_data = process_context(
                    search_results,
                    query=request.prompt,
                    max_context_tokens=30000,
                    context_fill_ratio=0.55,
                    max_evidence_blocks=7,
                    max_block_chars=800,
                    text_similarity_threshold=0.85
                )
                step_elapsed = time.time() - step_start
                total_elapsed = time.time() - start_time
                print(f"🟢 BACKEND: Step 3 - ✅ Context processed in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - {len(context_data['evidence'])} evidence blocks")
                
                if not context_data['evidence']:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Insufficient evidence after processing.'})}\n\n"
                    return
            else:
                print(f"🟢 BACKEND: Step 3 - Skipping context processing for web search mode")
            
            # Step 4: Convert evidence to EvidenceItem format
            evidence_items = []
            if not request.use_web_search:
                for ev in context_data['evidence']:
                    source_idx = ev['evidence_id'] - 1
                    orig_result = search_results[source_idx] if source_idx < len(search_results) else {}
                    
                    evidence_item = {
                        'evidence_id': ev['evidence_id'],
                        'citation': ev['citation'],
                        'doc_id': ev['doc_id'],
                        'doc_title': ev['doc_title'],
                        'doctype': ev.get('doctype'),
                        'date': ev.get('date'),
                        'page_range': ev['page_range'],
                        'section_path': ev.get('section_path', []),
                        'text': ev['text'],
                        'source_url': ev['source_url'],
                        'chunk_ids': ev['chunk_ids'],
                        'token_count': ev['token_count'],
                        'rerank_score': orig_result.get('rerank_score'),
                        'rrf_score': orig_result.get('rrf_score'),
                        'bm25_score': orig_result.get('bm25_score'),
                        'faiss_score': orig_result.get('faiss_score')
                    }
                    evidence_items.append(evidence_item)
            else:
                # For web search, create a placeholder evidence item
                evidence_item = {
                    'evidence_id': 1,
                    'citation': 'Web Search Results',
                    'doc_id': 'web_search',
                    'doc_title': 'Current Web Information',
                    'doctype': 'web',
                    'date': 'current',
                    'page_range': [1],
                    'section_path': ['web'],
                    'text': 'Information sourced from current web search results',
                    'source_url': 'web://search',
                    'chunk_ids': ['web_1'],
                    'token_count': 0
                }
                evidence_items.append(evidence_item)
            
            # Send metadata with sources first
            metadata = {
                'type': 'metadata',
                'sources': evidence_items,
                'used_model': OPENROUTER_MODEL,
                'total_sources': len(evidence_items),
                'total_tokens': context_data['metadata'].get('total_tokens', 0),
                'target_tokens': context_data['metadata'].get('target_tokens', 0)
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Step 5: Build context for LLM
            if request.use_web_search:
                # Step 6: Compose messages for web search LLM
                system_message = """You are a helpful assistant with access to current web information. Answer the user's question using your web search capabilities to find the most up-to-date and relevant information.

INSTRUCTIONS:
1. Search the web for current information related to the question
2. PRIORITIZE reliable sources: government websites (.gov), educational institutions (.edu), and reputable organizations (.org)
3. Avoid commercial websites (.com) unless they are well-established, authoritative sources
4. Provide accurate, well-sourced information with proper citations
5. Include relevant details and context
6. Format your response in clear markdown
7. If you find conflicting information, mention the different perspectives
8. Always cite your sources with clickable links
9. At the end of your response, always ask if the user would like you to search for additional information on the web"""

                user_message = f"""Please search the web for current information to answer this question comprehensively."""
            else:
                evidence_blocks = []
                for ev in context_data['evidence']:
                    evidence_blocks.append(
                        f"[{ev['evidence_id']}] {ev['citation']}\n{ev['text']}"
                    )
                
                context_block = "\n\n".join(evidence_blocks)
                
                # Step 6: Compose messages for LLM
                system_message = """You are a helpful assistant that answers questions using ONLY information from your knowledge base and the documents available to you.

CRITICAL RULES:
1. ONLY use information from the EVIDENCE blocks below (these are documents from your knowledge base)
2. Cite EVERY claim using [n] where n is the evidence number
3. If evidence is insufficient, explicitly say "Insufficient evidence"
4. Prefer newer sources when multiple sources cover the same topic
5. Use concise, clear language
6. Format response in markdown with bullet points where appropriate
7. When introducing your answer, say things like "Based on my knowledge base" or "According to the documents I have" rather than "Based on the provided evidence"

When citing:
- Place [n] immediately after the relevant statement
- You can cite multiple sources like [1][3] if needed
- Do not invent or assume information not in the evidence"""

                user_message = f"""Question: {request.prompt}

EVIDENCE FROM YOUR KNOWLEDGE BASE:
{context_block}

Please answer the question using ONLY information from your knowledge base above. Remember to cite every claim with [n]."""
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            # Step 7: Stream LLM response
            model_suffix = ":online" if request.use_web_search else ""
            print(f"🟢 BACKEND: Step 6 - Streaming LLM response (model: {OPENROUTER_MODEL}{model_suffix}, web_search: {request.use_web_search})...")
            
            async for chunk in openrouter_client.stream_messages(
                messages,
                max_tokens=4000,
                temperature=0.3,
                use_web_search=request.use_web_search
            ):
                if chunk:
                    # Send content chunk
                    yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            
            # Send completion
            total_elapsed = time.time() - start_time
            print(f"🟢 BACKEND: ✅ Stream complete (total latency: {total_elapsed:.2f}s)")
            yield f"data: {json.dumps({'type': 'done', 'latency_ms': int(total_elapsed * 1000)})}\n\n"
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"🟢 BACKEND: ❌ Exception after {elapsed:.2f}s: {str(e)}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
