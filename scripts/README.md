# Scripts

This directory contains utility scripts for data processing and setup.

## Database Setup

### `init_db.py`
Initialize the SQLite database with schema for hybrid RAG retrieval.

```bash
# Initialize database
python scripts/init_db.py

# Reset and reinitialize
python scripts/init_db.py --reset

# Show database statistics
python scripts/init_db.py --stats

# Use custom database path
python scripts/init_db.py --db /path/to/custom.db
```

## Data Processing

### `transcribe_raw_pdfs.py`
Process raw PDF files and convert them to JSON format for ingestion.

## Usage

All scripts should be run from the project root directory:

```bash
# From project root
python scripts/init_db.py --stats
```
