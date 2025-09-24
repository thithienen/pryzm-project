from fastapi import APIRouter, HTTPException
from llm import openrouter_client
from settings import OPENROUTER_MODEL

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@router.get("/llm/health")
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
