"""
OpenRouter LLM Client for Pryzm Project

Provides async interface to OpenRouter API for LLM completions.
Supports various models through OpenRouter (Claude, GPT-4, etc.)
"""

import httpx
import json
from typing import Optional, List, Dict, Any
from settings import OPENROUTER_API_KEY, OPENROUTER_MODEL


class OpenRouterClient:
    """
    Async client for OpenRouter API.
    
    Handles chat completion requests with proper error handling
    and configurable parameters.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_timeout: float = 60.0
    ):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key (defaults to settings.OPENROUTER_API_KEY)
            model: Model to use (defaults to settings.OPENROUTER_MODEL)
            default_timeout: Default timeout for requests in seconds
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or OPENROUTER_MODEL
        self.default_timeout = default_timeout
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Pryzm Project"
        }
    
    async def send_message(self, message: str) -> Optional[str]:
        """
        Send a message to the OpenRouter model and return the response text.
        
        Args:
            message: The prompt/message to send to the model
            
        Returns:
            The model's response text, or None if there was an error
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            return None
        except KeyError as e:
            print(f"Unexpected response format: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    async def send_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.3,
        timeout: Optional[float] = None
    ) -> Optional[str]:
        """
        Send a list of messages to the OpenRouter model and return the response text.
        
        This is the main method for RAG applications where you need to send
        system messages with context and user queries.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
                     Example: [{"role": "system", "content": "..."}, 
                              {"role": "user", "content": "..."}]
            max_tokens: Maximum tokens for the response (default: 2000)
            temperature: Temperature for response generation (default: 0.3)
                        Lower = more focused, Higher = more creative
            timeout: Request timeout in seconds (uses default_timeout if None)
            
        Returns:
            The model's response text, or None if there was an error
            
        Raises:
            May log errors but returns None instead of raising exceptions
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        request_timeout = timeout if timeout is not None else self.default_timeout
        
        import time
        llm_start = time.time()
        
        print(f"🟡 LLM: Preparing to call OpenRouter API")
        print(f"🟡 LLM: Model: {self.model}")
        print(f"🟡 LLM: Timeout: {request_timeout}s")
        print(f"🟡 LLM: Messages: {len(messages)} messages")
        print(f"🟡 LLM: Total prompt chars: {sum(len(m['content']) for m in messages)}")
        
        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                print(f"🟡 LLM: Sending POST request to OpenRouter...")
                api_start = time.time()
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                api_time = time.time() - api_start
                print(f"🟡 LLM: ✅ Received response with status: {response.status_code} in {api_time:.2f}s")
                response.raise_for_status()
                
                data = response.json()
                
                # Validate response structure
                if "choices" not in data or len(data["choices"]) == 0:
                    print(f"🟡 LLM: ❌ Invalid response structure: {data}")
                    return None
                
                content = data["choices"][0]["message"]["content"]
                total_time = time.time() - llm_start
                print(f"🟡 LLM: ✅ Extracted content, length: {len(content)} chars (total LLM time: {total_time:.2f}s)")
                return content
                
        except httpx.TimeoutException as e:
            print(f"🟡 LLM: ❌ Request timeout after {request_timeout}s: {e}")
            return None
        except httpx.HTTPStatusError as e:
            print(f"🟡 LLM: ❌ HTTP status error {e.response.status_code}: {e}")
            print(f"🟡 LLM: Response body: {e.response.text}")
            if e.response.status_code == 429:
                print("🟡 LLM: Rate limit exceeded. Please try again later.")
            return None
        except httpx.HTTPError as e:
            print(f"🟡 LLM: ❌ HTTP error occurred: {e}")
            return None
        except KeyError as e:
            print(f"🟡 LLM: ❌ Unexpected response format, missing key: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"🟡 LLM: ❌ Failed to decode JSON response: {e}")
            return None
        except Exception as e:
            print(f"🟡 LLM: ❌ Unexpected error in send_messages: {e}")
            import traceback
            traceback.print_exc()
            return None

# Create a global instance
openrouter_client = OpenRouterClient()
