#!/usr/bin/env python3
"""
Ingestion script for Pryzm project.

Performs complete data ingestion pipeline:
1. Load chunks.jsonl into SQLite database
2. Generate OpenAI embeddings for all chunks
3. Build FAISS vector index for semantic search
"""

import json
import sqlite3
import pickle
import os
from pathlib import Path
from typing import List, Dict, Any, Iterator
import numpy as np
import faiss
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseIngestor:
    """Handles SQLite database ingestion"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.row_factory = sqlite3.Row
        print(f"Connected to database: {self.db_path}")
        
    def ingest_chunks(self, chunks_path: str) -> int:
        """
        Load chunks from JSONL file into SQLite.
        
        Returns:
            Number of chunks inserted
        """
        print(f"\nIngesting chunks from {chunks_path}...")
        
        chunks_inserted = 0
        batch = []
        batch_size = 500
        
        with open(chunks_path, 'r', encoding='utf-8') as f:
            for line in tqdm(f, desc="Reading chunks", unit=" chunks"):
                chunk = json.loads(line)
                batch.append(chunk)
                
                if len(batch) >= batch_size:
                    self._insert_batch(batch)
                    chunks_inserted += len(batch)
                    batch = []
        
        # Insert remaining chunks
        if batch:
            self._insert_batch(batch)
            chunks_inserted += len(batch)
        
        self.conn.commit()
        print(f"[OK] Inserted {chunks_inserted} chunks into database")
        return chunks_inserted
    
    def _insert_batch(self, batch: List[Dict[str, Any]]):
        """Insert a batch of chunks into database"""
        self.conn.executemany(
            """INSERT OR REPLACE INTO chunks
               (chunk_id, doc_id, doc_title, source_url, date, doctype, page, 
                section_path, text, is_table)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    chunk["chunk_id"],
                    chunk["doc_id"],
                    chunk["doc_title"],
                    chunk.get("source_url"),
                    chunk.get("date"),
                    chunk.get("doctype"),
                    chunk["page"],
                    json.dumps(chunk.get("section_path", [])),
                    chunk["text"],
                    int(chunk.get("is_table", False))
                )
                for chunk in batch
            ]
        )
    
    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieve all chunks from database"""
        cursor = self.conn.execute(
            "SELECT chunk_id, text FROM chunks ORDER BY rowid"
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")


class EmbeddingGenerator:
    """Handles OpenAI embedding generation"""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client = OpenAI()  # Uses OPENAI_API_KEY env var
        print(f"Initialized OpenAI client with model: {model}")
        
    def generate_embeddings(
        self, 
        chunks: List[Dict[str, Any]], 
        batch_size: int = 2048
    ) -> tuple[List[str], np.ndarray]:
        """
        Generate embeddings for all chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'chunk_id' and 'text'
            batch_size: Number of texts to send in each API call
            
        Returns:
            Tuple of (chunk_ids, embedding_matrix)
        """
        print(f"\nGenerating embeddings for {len(chunks)} chunks...")
        
        chunk_ids = [c["chunk_id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        
        all_embeddings = []
        
        # Process in batches
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                print(f"\n[ERROR] Error generating embeddings for batch {i//batch_size}: {e}")
                raise
        
        # Convert to numpy array
        embedding_matrix = np.array(all_embeddings, dtype='float32')
        
        print(f"[OK] Generated embeddings with shape: {embedding_matrix.shape}")
        return chunk_ids, embedding_matrix


class FAISSIndexBuilder:
    """Handles FAISS index creation"""
    
    def __init__(self):
        pass
        
    def build_index(
        self, 
        embeddings: np.ndarray,
        use_hnsw: bool = True
    ) -> faiss.Index:
        """
        Build FAISS index from embeddings.
        
        Args:
            embeddings: Numpy array of embeddings (N x D)
            use_hnsw: If True, use HNSW index (approximate), else use flat index (exact)
            
        Returns:
            FAISS index
        """
        print(f"\nBuilding FAISS index for {embeddings.shape[0]} vectors...")
        
        dimension = embeddings.shape[1]
        
        if use_hnsw:
            # HNSW index - faster search, approximate results
            print("Using HNSW index (approximate nearest neighbor)")
            index = faiss.IndexHNSWFlat(dimension, 32)  # 32 = M parameter
            index.hnsw.efConstruction = 200  # Higher = better quality, slower build
            index.hnsw.efSearch = 100  # Higher = better search quality
        else:
            # Flat index - exact search, slower for large datasets
            print("Using Flat index (exact nearest neighbor)")
            index = faiss.IndexFlatIP(dimension)  # IP = Inner Product (cosine similarity)
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add vectors to index
        index.add(embeddings)
        
        print(f"[OK] FAISS index built with {index.ntotal} vectors")
        return index
    
    def save_index(self, index: faiss.Index, chunk_ids: List[str], output_dir: str):
        """
        Save FAISS index and chunk ID mapping.
        
        Args:
            index: FAISS index
            chunk_ids: List of chunk IDs in same order as index
            output_dir: Directory to save files
        """
        output_path = Path(output_dir)
        
        # Save FAISS index
        index_path = output_path / "vectors.faiss"
        faiss.write_index(index, str(index_path))
        print(f"[OK] Saved FAISS index to {index_path}")
        
        # Save chunk ID mapping
        mapping_path = output_path / "vectors.pkl"
        with open(mapping_path, 'wb') as f:
            pickle.dump(chunk_ids, f)
        print(f"[OK] Saved chunk ID mapping to {mapping_path}")


def main():
    """Main ingestion pipeline"""
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key'  # Linux/Mac")
        print("  $env:OPENAI_API_KEY='your-api-key'   # Windows PowerShell")
        return
    
    # Paths
    project_root = Path(__file__).parent.parent.parent
    chunks_path = project_root / "data" / "chunks.jsonl"
    db_path = project_root / "data" / "corpus.db"
    output_dir = project_root / "data"
    
    print("=" * 70)
    print("PRYZM INGESTION PIPELINE")
    print("=" * 70)
    print(f"Chunks file: {chunks_path}")
    print(f"Database: {db_path}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Task 1: Ingest chunks into SQLite
    print("TASK 1: Ingesting chunks into SQLite database")
    print("-" * 70)
    db_ingestor = DatabaseIngestor(str(db_path))
    db_ingestor.connect()
    chunks_inserted = db_ingestor.ingest_chunks(str(chunks_path))
    
    # Retrieve all chunks for embedding generation
    print("\nRetrieving chunks from database...")
    chunks = db_ingestor.get_all_chunks()
    print(f"Retrieved {len(chunks)} chunks")
    
    # Task 2: Generate OpenAI embeddings
    print("\n" + "=" * 70)
    print("TASK 2: Generating OpenAI embeddings")
    print("-" * 70)
    embedder = EmbeddingGenerator(model="text-embedding-3-small")
    chunk_ids, embeddings = embedder.generate_embeddings(chunks, batch_size=256)
    
    # Task 3: Build FAISS index
    print("\n" + "=" * 70)
    print("TASK 3: Building FAISS vector index")
    print("-" * 70)
    index_builder = FAISSIndexBuilder()
    index = index_builder.build_index(embeddings, use_hnsw=True)
    index_builder.save_index(index, chunk_ids, str(output_dir))
    
    # Cleanup
    db_ingestor.close()
    
    # Final summary
    print("\n" + "=" * 70)
    print("INGESTION COMPLETE!")
    print("=" * 70)
    print(f"[OK] {chunks_inserted} chunks in SQLite database")
    print(f"[OK] {embeddings.shape[0]} embeddings generated")
    print(f"[OK] FAISS index with {index.ntotal} vectors")
    print("\nYour search system is ready to use!")
    print("=" * 70)


if __name__ == "__main__":
    main()

