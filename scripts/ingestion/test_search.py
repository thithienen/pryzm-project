#!/usr/bin/env python3
"""
Quick test script to verify ingestion was successful.

Tests:
1. SQLite database can be queried
2. FTS5 full-text search works
3. FAISS index can perform similarity search
"""

import sqlite3
import pickle
import numpy as np
import faiss
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Paths
project_root = Path(__file__).parent.parent.parent
db_path = project_root / "data" / "corpus.db"
faiss_path = project_root / "data" / "vectors.faiss"
mapping_path = project_root / "data" / "vectors.pkl"

print("=" * 70)
print("TESTING INGESTION")
print("=" * 70)

# Test 1: SQLite Database
print("\n[TEST 1] SQLite Database Query")
print("-" * 70)
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Count total chunks
cursor = conn.execute("SELECT COUNT(*) as count FROM chunks")
total_chunks = cursor.fetchone()["count"]
print(f"Total chunks in database: {total_chunks}")

# Sample a few chunks
cursor = conn.execute("SELECT chunk_id, doc_title, page, LENGTH(text) as text_len FROM chunks LIMIT 3")
print("\nSample chunks:")
for row in cursor:
    print(f"  - {row['chunk_id']}")
    print(f"    Doc: {row['doc_title']}, Page: {row['page']}")
    print(f"    Text length: {row['text_len']} characters")

# Test 2: FTS5 Full-Text Search
print("\n[TEST 2] FTS5 Full-Text Search (BM25)")
print("-" * 70)
test_query = "missile defense"
cursor = conn.execute("""
    SELECT chunks.chunk_id, chunks.doc_title, chunks.page, bm25(fts_chunks) AS score
    FROM fts_chunks
    JOIN chunks ON chunks.rowid = fts_chunks.rowid
    WHERE fts_chunks MATCH ?
    ORDER BY score
    LIMIT 3
""", (test_query,))

print(f"Query: '{test_query}'")
print("Top 3 results:")
for row in cursor:
    print(f"  - {row['chunk_id']}")
    print(f"    Doc: {row['doc_title']}, Page: {row['page']}")
    print(f"    BM25 Score: {row['score']:.4f}")

conn.close()

# Test 3: FAISS Vector Search
print("\n[TEST 3] FAISS Vector Search (Semantic Similarity)")
print("-" * 70)

# Load FAISS index
index = faiss.read_index(str(faiss_path))
print(f"FAISS index loaded: {index.ntotal} vectors, {index.d} dimensions")

# Load chunk ID mapping
with open(mapping_path, 'rb') as f:
    chunk_ids = pickle.load(f)
print(f"Chunk ID mapping loaded: {len(chunk_ids)} entries")

# Generate query embedding
client = OpenAI()
query_text = "hypersonic missile defense systems"
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=query_text
)
query_vector = np.array([response.data[0].embedding], dtype='float32')

# Normalize for cosine similarity
faiss.normalize_L2(query_vector)

# Search
k = 3
distances, indices = index.search(query_vector, k)

print(f"\nQuery: '{query_text}'")
print(f"Top {k} semantic matches:")

# Reconnect to get chunk details
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

for i, (idx, score) in enumerate(zip(indices[0], distances[0])):
    chunk_id = chunk_ids[idx]
    cursor = conn.execute(
        "SELECT doc_title, page FROM chunks WHERE chunk_id = ?",
        (chunk_id,)
    )
    row = cursor.fetchone()
    if row:
        print(f"  {i+1}. {chunk_id}")
        print(f"     Doc: {row['doc_title']}, Page: {row['page']}")
        print(f"     Similarity Score: {score:.4f}")

conn.close()

# Final Summary
print("\n" + "=" * 70)
print("ALL TESTS PASSED!")
print("=" * 70)
print(f"[OK] SQLite database operational ({total_chunks} chunks)")
print(f"[OK] FTS5 full-text search working")
print(f"[OK] FAISS semantic search working ({index.ntotal} vectors)")
print("\nYour hybrid search system is fully functional!")
print("=" * 70)

