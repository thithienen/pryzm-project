"""
OpenAI Embeddings utility for encoding text.
Used both for query-time encoding and corpus building.
"""
import os
import numpy as np
from openai import OpenAI
from typing import List, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
EMBED_MODEL = "text-embedding-3-small"  # 1536 dimensions
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate API key
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single text string using OpenAI's embedding model.
    
    Args:
        text: The text to embed
        
    Returns:
        numpy array of shape (1536,) containing the embedding vector
    """
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    embedding = response.data[0].embedding
    return np.array(embedding, dtype="float32")


def embed_batch(texts: List[str], batch_size: int = 256) -> np.ndarray:
    """
    Embed a batch of texts using OpenAI's embedding model.
    Handles large batches by chunking into smaller API calls.
    
    Args:
        texts: List of text strings to embed
        batch_size: Maximum number of texts per API call (default: 256)
        
    Returns:
        numpy array of shape (len(texts), 1536) containing embedding vectors
    """
    all_embeddings = []
    
    # Process in batches to respect API limits
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=batch
        )
        batch_embeddings = [data.embedding for data in response.data]
        all_embeddings.extend(batch_embeddings)
    
    return np.array(all_embeddings, dtype="float32")


def embed_query(query: str) -> np.ndarray:
    """
    Convenience function to embed a user query.
    Returns embedding ready for FAISS search (shape: (1, 1536))
    
    Args:
        query: The query text to embed
        
    Returns:
        numpy array of shape (1, 1536) for FAISS search
    """
    embedding = embed_text(query)
    return embedding[np.newaxis, :]  # Add batch dimension for FAISS


# For testing/validation
if __name__ == "__main__":
    # Test single embedding
    test_text = "What is the FY2025 budget for Navy procurement?"
    embedding = embed_text(test_text)
    print(f"Single embedding shape: {embedding.shape}")
    print(f"First 5 values: {embedding[:5]}")
    
    # Test batch embedding
    test_batch = [
        "ASA(ALT) organizational structure",
        "PEO programs and offices",
        "Defense budget overview"
    ]
    batch_embeddings = embed_batch(test_batch)
    print(f"\nBatch embeddings shape: {batch_embeddings.shape}")
    
    # Test query embedding (for FAISS)
    query_embedding = embed_query(test_text)
    print(f"\nQuery embedding shape: {query_embedding.shape}")

