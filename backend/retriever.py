"""
Hybrid Retrieval System for Pryzm Project

Combines BM25 (FTS5) keyword search with FAISS semantic search,
using RRF fusion and cross-encoder reranking.
"""

import sqlite3
import pickle
import numpy as np
import faiss
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sentence_transformers import CrossEncoder
from embeddings import embed_query
import json


@dataclass
class RetrievalConfig:
    """Configuration for retrieval system"""
    db_path: str = "data/corpus.db"
    faiss_index_path: str = "data/vectors.faiss"
    chunk_mapping_path: str = "data/vectors.pkl"
    
    # Retrieval parameters
    bm25_top_k: int = 120
    faiss_top_k: int = 120
    rrf_k: int = 60
    fusion_top_k: int = 200
    rerank_top_k: int = 32
    
    # Cross-encoder model
    reranker_model: str = "BAAI/bge-reranker-v2-m3"


@dataclass
class SearchResult:
    """Single search result with metadata"""
    chunk_id: str
    doc_id: str
    doc_title: str
    source_url: Optional[str]
    date: Optional[str]
    doctype: Optional[str]
    page: int
    section_path: List[str]
    text: str
    is_table: bool
    
    # Scores
    bm25_score: Optional[float] = None
    faiss_score: Optional[float] = None
    rrf_score: Optional[float] = None
    rerank_score: Optional[float] = None
    final_rank: Optional[int] = None


class HybridRetriever:
    """
    Hybrid retrieval system combining BM25 and FAISS vector search.
    
    This class manages:
    - SQLite database connection (with FTS5 for BM25)
    - FAISS vector index (for semantic search)
    - Cross-encoder reranking
    """
    
    def __init__(self, config: Optional[RetrievalConfig] = None):
        """
        Initialize the hybrid retriever.
        
        Args:
            config: Configuration object (uses defaults if None)
        """
        self.config = config or RetrievalConfig()
        
        # Resolve paths relative to backend directory
        backend_dir = Path(__file__).parent
        project_root = backend_dir.parent
        
        self.db_path = project_root / self.config.db_path
        self.faiss_path = project_root / self.config.faiss_index_path
        self.mapping_path = project_root / self.config.chunk_mapping_path
        
        # Initialize components
        self.conn: Optional[sqlite3.Connection] = None
        self.faiss_index: Optional[faiss.Index] = None
        self.chunk_ids: Optional[List[str]] = None
        self.reranker: Optional[CrossEncoder] = None
        
        # Load everything on initialization
        self._connect_database()
        self._load_faiss_index()
        self._load_reranker()
        
        print(f"[HybridRetriever] Initialized successfully")
        print(f"  - Database: {self.db_path}")
        print(f"  - FAISS vectors: {self.faiss_index.ntotal if self.faiss_index else 0}")
        print(f"  - Chunk mappings: {len(self.chunk_ids) if self.chunk_ids else 0}")
    
    def _connect_database(self):
        """Connect to SQLite database with FTS5"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        print(f"[HybridRetriever] Connected to database")
    
    def _load_faiss_index(self):
        """Load FAISS index and chunk ID mapping"""
        if not self.faiss_path.exists():
            raise FileNotFoundError(f"FAISS index not found: {self.faiss_path}")
        if not self.mapping_path.exists():
            raise FileNotFoundError(f"Chunk mapping not found: {self.mapping_path}")
        
        # Load FAISS index
        self.faiss_index = faiss.read_index(str(self.faiss_path))
        print(f"[HybridRetriever] Loaded FAISS index: {self.faiss_index.ntotal} vectors")
        
        # Load chunk ID mapping
        with open(self.mapping_path, 'rb') as f:
            self.chunk_ids = pickle.load(f)
        print(f"[HybridRetriever] Loaded {len(self.chunk_ids)} chunk mappings")
    
    def _load_reranker(self):
        """Load cross-encoder reranking model"""
        print(f"[HybridRetriever] Loading reranker model: {self.config.reranker_model}")
        self.reranker = CrossEncoder(self.config.reranker_model)
        print(f"[HybridRetriever] Reranker loaded")
    
    def bm25_search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Perform BM25 full-text search using FTS5.
        
        Args:
            query: Search query
            top_k: Number of results to return (uses config default if None)
            
        Returns:
            List of search results with BM25 scores
        """
        if top_k is None:
            top_k = self.config.bm25_top_k
        
        cursor = self.conn.execute("""
            SELECT chunks.rowid, chunks.chunk_id, chunks.doc_id, chunks.doc_title, 
                   chunks.source_url, chunks.date, chunks.doctype, chunks.page,
                   chunks.section_path, chunks.text, chunks.is_table,
                   bm25(fts_chunks) AS score
            FROM fts_chunks
            JOIN chunks ON chunks.rowid = fts_chunks.rowid
            WHERE fts_chunks MATCH ?
            ORDER BY score
            LIMIT ?
        """, (query, top_k))
        
        results = []
        for row in cursor.fetchall():
            result = {
                'chunk_id': row['chunk_id'],
                'doc_id': row['doc_id'],
                'doc_title': row['doc_title'],
                'source_url': row['source_url'],
                'date': row['date'],
                'doctype': row['doctype'],
                'page': row['page'],
                'section_path': json.loads(row['section_path']) if row['section_path'] else [],
                'text': row['text'],
                'is_table': bool(row['is_table']),
                'bm25_score': float(row['score'])
            }
            results.append(result)
        
        return results
    
    def faiss_search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Perform semantic search using FAISS vector index.
        
        Args:
            query: Search query
            top_k: Number of results to return (uses config default if None)
            
        Returns:
            List of search results with similarity scores
        """
        if top_k is None:
            top_k = self.config.faiss_top_k
        
        # Get query embedding
        query_vector = embed_query(query)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(query_vector)
        
        # Search FAISS index
        distances, indices = self.faiss_index.search(query_vector, top_k)
        
        # Hydrate results with chunk metadata
        results = []
        for idx, score in zip(indices[0], distances[0]):
            chunk_id = self.chunk_ids[idx]
            
            # Get chunk details from database
            cursor = self.conn.execute(
                """SELECT chunk_id, doc_id, doc_title, source_url, date, doctype,
                          page, section_path, text, is_table
                   FROM chunks WHERE chunk_id = ?""",
                (chunk_id,)
            )
            row = cursor.fetchone()
            
            if row:
                result = {
                    'chunk_id': row['chunk_id'],
                    'doc_id': row['doc_id'],
                    'doc_title': row['doc_title'],
                    'source_url': row['source_url'],
                    'date': row['date'],
                    'doctype': row['doctype'],
                    'page': row['page'],
                    'section_path': json.loads(row['section_path']) if row['section_path'] else [],
                    'text': row['text'],
                    'is_table': bool(row['is_table']),
                    'faiss_score': float(score)
                }
                results.append(result)
        
        return results
    
    def rrf_fuse(
        self, 
        bm25_results: List[Dict[str, Any]], 
        faiss_results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fuse BM25 and FAISS results using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score(d) = sum( 1 / (k + rank_i(d)) ) for each ranker i
        
        Args:
            bm25_results: Results from BM25 search
            faiss_results: Results from FAISS search
            top_k: Number of fused results to return (uses config default if None)
            
        Returns:
            Fused and re-ranked results
        """
        if top_k is None:
            top_k = self.config.fusion_top_k
        
        k = self.config.rrf_k
        
        # Calculate RRF scores for each result set
        def get_rrf_scores(results: List[Dict[str, Any]]) -> Dict[str, float]:
            scores = {}
            for rank, result in enumerate(results, start=1):
                chunk_id = result['chunk_id']
                scores[chunk_id] = 1.0 / (k + rank)
            return scores
        
        bm25_scores = get_rrf_scores(bm25_results)
        faiss_scores = get_rrf_scores(faiss_results)
        
        # Combine scores
        all_chunk_ids = set(bm25_scores.keys()) | set(faiss_scores.keys())
        fused_scores = {}
        
        for chunk_id in all_chunk_ids:
            fused_scores[chunk_id] = (
                bm25_scores.get(chunk_id, 0.0) + 
                faiss_scores.get(chunk_id, 0.0)
            )
        
        # Sort by combined RRF score
        sorted_chunks = sorted(
            fused_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_k]
        
        # Hydrate full chunk data from database
        results = []
        for chunk_id, rrf_score in sorted_chunks:
            cursor = self.conn.execute(
                """SELECT chunk_id, doc_id, doc_title, source_url, date, doctype,
                          page, section_path, text, is_table
                   FROM chunks WHERE chunk_id = ?""",
                (chunk_id,)
            )
            row = cursor.fetchone()
            
            if row:
                result = {
                    'chunk_id': row['chunk_id'],
                    'doc_id': row['doc_id'],
                    'doc_title': row['doc_title'],
                    'source_url': row['source_url'],
                    'date': row['date'],
                    'doctype': row['doctype'],
                    'page': row['page'],
                    'section_path': json.loads(row['section_path']) if row['section_path'] else [],
                    'text': row['text'],
                    'is_table': bool(row['is_table']),
                    'rrf_score': rrf_score,
                    'bm25_score': bm25_scores.get(chunk_id),
                    'faiss_score': faiss_scores.get(chunk_id)
                }
                results.append(result)
        
        return results
    
    def rerank(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using cross-encoder model.
        
        Args:
            query: Original search query
            candidates: List of candidate chunks to rerank
            top_k: Number of top results to return (uses config default if None)
            
        Returns:
            Reranked results with rerank scores
        """
        if top_k is None:
            top_k = self.config.rerank_top_k
        
        if not candidates:
            return []
        
        # Prepare query-text pairs (truncate text for speed)
        pairs = [(query, c['text'][:2000]) for c in candidates]
        
        # Get reranking scores
        scores = self.reranker.predict(pairs)
        
        # Add scores to candidates
        for candidate, score in zip(candidates, scores):
            candidate['rerank_score'] = float(score)
        
        # Sort by rerank score and return top-k
        reranked = sorted(
            candidates,
            key=lambda x: x['rerank_score'],
            reverse=True
        )[:top_k]
        
        # Add final rank
        for rank, result in enumerate(reranked, start=1):
            result['final_rank'] = rank
        
        return reranked
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_reranking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Complete hybrid retrieval pipeline.
        
        Pipeline:
        1. BM25 search (FTS5)
        2. FAISS semantic search
        3. RRF fusion
        4. Cross-encoder reranking (optional)
        
        Args:
            query: Search query
            top_k: Number of final results (uses config default if None)
            use_reranking: Whether to apply cross-encoder reranking
            
        Returns:
            List of top-ranked search results
        """
        if top_k is None:
            top_k = self.config.rerank_top_k
        
        # Step 1: BM25 search
        bm25_results = self.bm25_search(query)
        print(f"[Retrieve] BM25 search: {len(bm25_results)} results")
        
        # Step 2: FAISS semantic search
        faiss_results = self.faiss_search(query)
        print(f"[Retrieve] FAISS search: {len(faiss_results)} results")
        
        # Step 3: RRF fusion
        fused_results = self.rrf_fuse(bm25_results, faiss_results)
        print(f"[Retrieve] RRF fusion: {len(fused_results)} candidates")
        
        # Step 4: Reranking (optional)
        if use_reranking and self.reranker:
            final_results = self.rerank(query, fused_results, top_k)
            print(f"[Retrieve] Reranked: {len(final_results)} final results")
        else:
            final_results = fused_results[:top_k]
            for rank, result in enumerate(final_results, start=1):
                result['final_rank'] = rank
        
        return final_results
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("[HybridRetriever] Database connection closed")


# Global retriever instance (singleton)
_retriever_instance: Optional[HybridRetriever] = None


def get_retriever(config: Optional[RetrievalConfig] = None) -> HybridRetriever:
    """
    Get the global retriever instance (singleton pattern).
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        HybridRetriever instance
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever(config)
    return _retriever_instance
