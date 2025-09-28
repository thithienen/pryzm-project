"""
Initialize the SQLite database with schema for hybrid RAG retrieval.
Creates the chunks table, FTS5 index, and sync triggers.
"""
import sqlite3
from pathlib import Path

# Database path - stored in data directory
DB_PATH = Path(__file__).parent.parent / "data" / "corpus.db"


def init_database(db_path: Path = DB_PATH, reset: bool = False):
    """
    Initialize the corpus database with schema.
    
    Args:
        db_path: Path to the database file
        reset: If True, drops existing tables before creating new ones
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")  # Write-Ahead Logging for better concurrency
    
    cursor = conn.cursor()
    
    # Optionally reset database
    if reset:
        print("Resetting database...")
        cursor.execute("DROP TABLE IF EXISTS fts_chunks;")
        cursor.execute("DROP TABLE IF EXISTS chunks;")
        conn.commit()
    
    # Create main chunks table
    print("Creating chunks table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            doc_title TEXT NOT NULL,
            source_url TEXT,
            date TEXT,
            doctype TEXT,
            page INTEGER,
            section_path TEXT,        -- JSON string of headings
            text TEXT NOT NULL,
            is_table INTEGER DEFAULT 0
        )
    """)
    
    # Create FTS5 virtual table for full-text search (BM25)
    print("Creating FTS5 index...")
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
            text, 
            doc_title, 
            section_path, 
            content='chunks', 
            content_rowid='rowid',
            tokenize = 'porter'
        )
    """)
    
    # Create trigger to keep FTS in sync on INSERT
    print("Creating FTS sync triggers...")
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO fts_chunks(rowid, text, doc_title, section_path)
            VALUES (new.rowid, new.text, new.doc_title, new.section_path);
        END
    """)
    
    # Create trigger to keep FTS in sync on DELETE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO fts_chunks(fts_chunks, rowid, text, doc_title, section_path)
            VALUES('delete', old.rowid, old.text, old.doc_title, old.section_path);
        END
    """)
    
    # Create trigger to keep FTS in sync on UPDATE
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO fts_chunks(fts_chunks, rowid, text, doc_title, section_path)
            VALUES('delete', old.rowid, old.text, old.doc_title, old.section_path);
            INSERT INTO fts_chunks(rowid, text, doc_title, section_path)
            VALUES (new.rowid, new.text, new.doc_title, new.section_path);
        END
    """)
    
    # Create indexes for common queries
    print("Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_id ON chunks(doc_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_doctype ON chunks(doctype)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_date ON chunks(date)
    """)
    
    conn.commit()
    
    # Verify schema
    print("\nVerifying schema...")
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'trigger', 'index') ORDER BY type, name")
    objects = cursor.fetchall()
    
    print("\nDatabase objects created:")
    current_type = None
    for name, obj_type in objects:
        if obj_type != current_type:
            current_type = obj_type
            print(f"\n{obj_type.upper()}S:")
        print(f"  - {name}")
    
    # Get row count
    cursor.execute("SELECT COUNT(*) FROM chunks")
    count = cursor.fetchone()[0]
    print(f"\nChunks in database: {count}")
    
    conn.close()
    print(f"\n[OK] Database initialized successfully at: {db_path}")
    return db_path


def get_db_stats(db_path: Path = DB_PATH):
    """Get statistics about the database."""
    if not db_path.exists():
        print(f"Database not found at: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total chunks
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cursor.fetchone()[0]
    
    # Chunks by doctype
    cursor.execute("SELECT doctype, COUNT(*) FROM chunks GROUP BY doctype ORDER BY COUNT(*) DESC")
    by_doctype = cursor.fetchall()
    
    # Unique documents
    cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks")
    unique_docs = cursor.fetchone()[0]
    
    print(f"\n=== Database Statistics ===")
    print(f"Database: {db_path}")
    print(f"Total chunks: {total_chunks}")
    print(f"Unique documents: {unique_docs}")
    
    if by_doctype:
        print(f"\nChunks by document type:")
        for doctype, count in by_doctype:
            print(f"  {doctype or '(null)'}: {count}")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize corpus database")
    parser.add_argument("--reset", action="store_true", help="Reset database (drop existing tables)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")
    
    args = parser.parse_args()
    db_path = Path(args.db)
    
    if args.stats:
        get_db_stats(db_path)
    else:
        init_database(db_path, reset=args.reset)

