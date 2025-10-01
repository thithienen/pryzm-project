from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import time
import re
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
    print(f"🟢 BACKEND: max_sources={request.max_sources}, use_reranking={request.use_reranking}")
    
    try:
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
                answer_md="Insufficient evidence in current corpus. No relevant documents found for this query.",
                sources=[],
                used_model=OPENROUTER_MODEL,
                latency_ms=int((time.time() - start_time) * 1000),
                metadata={
                    "total_sources": 0,
                    "reranking_used": request.use_reranking,
                    "message": "No search results found"
                }
            )
        
        # Step 3: Process context (merge chunks, format citations, pack within budget)
        print(f"🟢 BACKEND: Step 3 - Processing context...")
        step_start = time.time()
        context_data = process_context(
            search_results,
            query=request.prompt,
            max_context_tokens=60000,  # Budget for Claude/GPT-4
            context_fill_ratio=0.70  # Use 70% for evidence, leave 30% for reasoning
        )
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 3 - ✅ Context processed in {step_elapsed:.2f}s (total: {total_elapsed:.2f}s) - {len(context_data['evidence'])} evidence blocks")
        
        if not context_data['evidence']:
            print(f"🟢 BACKEND: Step 3 - ⚠️ No evidence after processing")
            return AnswerResponse(
                answer_md="Insufficient evidence in current corpus after processing.",
                sources=[],
                used_model=OPENROUTER_MODEL,
                latency_ms=int((time.time() - start_time) * 1000),
                metadata=context_data['metadata']
            )
        
        # Step 4: Build context for LLM with citations
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
        system_message = """You are a helpful assistant that answers questions using ONLY the provided evidence.

CRITICAL RULES:
1. ONLY use information from the EVIDENCE blocks below
2. Cite EVERY claim using [n] where n is the evidence number
3. If evidence is insufficient, explicitly say "Insufficient evidence"
4. Prefer newer sources when multiple sources cover the same topic
5. Use concise, clear language
6. Format response in markdown with bullet points where appropriate

When citing:
- Place [n] immediately after the relevant statement
- You can cite multiple sources like [1][3] if needed
- Do not invent or assume information not in the evidence"""

        user_message = f"""Question: {request.prompt}

EVIDENCE:
{context_block}

Please answer the question using ONLY the evidence above. Remember to cite every claim with [n]."""
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 5 - ✅ Messages composed in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s)")
        
        # Step 6: Call LLM
        print(f"🟢 BACKEND: Step 6 - Calling LLM (model: {OPENROUTER_MODEL})...")
        step_start = time.time()
        response_text = await openrouter_client.send_messages(
            messages,
            max_tokens=4000,
            temperature=0.3
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
            # No citations found - return warning
            response_text = "⚠️ The model did not provide proper citations. Here's the response, but verify against sources:\n\n" + response_text
        else:
            # Validate that citation numbers are valid
            max_evidence_num = len(context_data['evidence'])
            invalid_citations = []
            
            for citation_str in set(citations_found):  # Use set to check unique citations
                citation_num = int(citation_str)
                if citation_num < 1 or citation_num > max_evidence_num:
                    invalid_citations.append(citation_num)
            
            if invalid_citations:
                response_text = f"⚠️ The model cited invalid evidence numbers {invalid_citations}. Treating as insufficient evidence.\n\nInsufficient evidence or missing citations. Please refine the query."
        
        step_elapsed = time.time() - step_start
        total_elapsed = time.time() - start_time
        print(f"🟢 BACKEND: Step 7 - ✅ Citations validated in {step_elapsed:.3f}s (total: {total_elapsed:.2f}s) - {len(set(citations_found)) if citations_found else 0} unique citations")
        
        # Step 8: Convert evidence to EvidenceItem format
        print(f"🟢 BACKEND: Step 8 - Converting evidence to response format...")
        step_start = time.time()
        evidence_items = []
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
                "total_tokens": context_data['metadata']['total_tokens'],
                "target_tokens": context_data['metadata']['target_tokens'],
                "fill_ratio": context_data['metadata']['fill_ratio'],
                "blocks_truncated": context_data['metadata']['blocks_truncated'],
                "reranking_used": request.use_reranking,
                "citations_found": len(set(citations_found)) if citations_found else 0
            }
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
