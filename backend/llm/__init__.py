"""
LLM Module for Pryzm Project

Contains LLM-related functionality:
- OpenAI embeddings
- Context processing
- LLM client wrapper
"""

from .embeddings import embed_text, embed_batch, embed_query
from .context_processor import ContextProcessor, process_context, EvidenceBlock
from .retriever import HybridRetriever, get_retriever, RetrievalConfig, SearchResult
from .llm import OpenRouterClient

__all__ = [
    'embed_text',
    'embed_batch', 
    'embed_query',
    'ContextProcessor',
    'process_context',
    'EvidenceBlock',
    'HybridRetriever',
    'get_retriever',
    'RetrievalConfig',
    'SearchResult',
    'OpenRouterClient'
]
