import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Data configuration
DATA_PATH = os.getenv("DATA_PATH", "./data/docs.json")

# OpenAI configuration (for embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenRouter configuration (for LLM completions)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

# Retrieval configuration
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", "0.05"))

# Server configuration
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Validate required environment variables
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")
