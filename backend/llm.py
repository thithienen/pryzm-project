import httpx
import json
from typing import Optional
from settings import OPENROUTER_API_KEY, OPENROUTER_MODEL

class OpenRouterClient:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",  # Optional: for tracking
            "X-Title": "Pryzm Project"  # Optional: for tracking
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

# Create a global instance
openrouter_client = OpenRouterClient()
