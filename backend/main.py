from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import time
import re
from llm import openrouter_client
from retriever import get_retriever
from settings import OPENROUTER_MODEL

# Pydantic models
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

app = FastAPI(title="Pryzm Project API", version="1.0.0")

@app.get("/")
async def read_root():
    return {"message": "Hello World!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/llm/health")
async def llm_health():
    """
    Health check endpoint for the LLM service.
    Tests the OpenRouter connection with a simple prompt.
    """
    try:
        # Send a simple test prompt
        test_prompt = "This is a health check"
        response = await openrouter_client.send_message(test_prompt)
        
        if response and len(response.strip()) > 0:
            return {
                "status": "ok",
                "model": OPENROUTER_MODEL,
                "test_prompt": test_prompt,
                "sample": response.strip()
            }
        else:
            return {
                "status": "error",
                "model": OPENROUTER_MODEL,
                "test_prompt": test_prompt,
                "sample": "No response received from model"
            }
    except Exception as e:
        return {
            "status": "error",
            "model": OPENROUTER_MODEL,
            "test_prompt": test_prompt,
            "sample": f"Error: {str(e)}"
        }

@app.post("/answer", response_model=AnswerResponse)
async def answer_question(request: AnswerRequest) -> AnswerResponse:
    """
    Answer a question using retrieval-augmented generation.
    
    Process:
    1. Run TF-IDF retrieval over docs.json
    2. Build numbered context list with doc metadata and snippets
    3. If no good hits, return "Insufficient evidence" message
    4. Compose system + user messages for LLM
    5. Call model and capture response
    6. Enforce citation rule - if no [n] citations, return error message
    7. Return structured response with answer and context
    """
    start_time = time.time()
    
    try:
        # Step 1: Run TF-IDF retrieval
        retriever = get_retriever()
        retrieved_docs = retriever.retrieve(request.prompt, top_k=10, min_score=0.05)
        
        # Step 2: Check if we have good hits
        if not retrieved_docs:
            return AnswerResponse(
                answer_md="Insufficient evidence in current corpus.",
                context=[],
                used_model=OPENROUTER_MODEL,
                latency_ms=int((time.time() - start_time) * 1000)
            )
        
        # Step 3: Build context list
        context_items = []
        context_text_parts = []
        
        for i, doc in enumerate(retrieved_docs, 1):  # Start numbering from 1
            context_item = ContextItem(
                rank=i,  # Use sequential numbering starting from 1
                doc_id=doc['doc_id'],
                title=doc['title'],
                url=doc['url'],
                doc_date=doc['doc_date'],
                pageno=doc['pageno'],
                snippet=doc['snippet']
            )
            context_items.append(context_item)
            
            # Build context text for LLM - use the same numbering
            context_text_parts.append(
                f"[{i}] {doc['title']} (Page {doc['pageno']}, {doc['doc_date']}): {doc['snippet']}"
            )
        
        context_block = "\n\n".join(context_text_parts)
        
        # Step 4: Compose messages for LLM
        system_message = (
            "ONLY use CONTEXT; end every claim with [n]; if unsupported, say 'insufficient evidence'; "
            "prefer newer official sources; concise bullets."
        )
        
        user_message = f"""Question: {request.prompt}

CONTEXT:
{context_block}"""
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # Step 5: Call model
        response_text = await openrouter_client.send_messages(messages, max_tokens=2000, temperature=0.3)
        
        if not response_text:
            raise HTTPException(status_code=500, detail="Failed to get response from LLM")
        
        # Step 6: Enforce citation rule and validate citation numbers
        citation_pattern = r'\[(\d+)\]'
        citations_found = re.findall(citation_pattern, response_text)
        
        if not citations_found:
            response_text = "Insufficient evidence or missing citations. Refine the corpus or query."
        else:
            # Validate that all citation numbers are within valid range
            max_context_num = len(context_items)
            invalid_citations = []
            
            for citation_str in citations_found:
                citation_num = int(citation_str)
                if citation_num < 1 or citation_num > max_context_num:
                    invalid_citations.append(citation_num)
            
            if invalid_citations:
                response_text = "Insufficient evidence or missing citations. Refine the corpus or query."
        
        # Step 7: Return structured response
        latency_ms = int((time.time() - start_time) * 1000)
        
        return AnswerResponse(
            answer_md=response_text,
            context=context_items,
            used_model=OPENROUTER_MODEL,
            latency_ms=latency_ms
        )
        
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Error in answer_question: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
