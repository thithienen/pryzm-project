# Pryzm Project

A document retrieval and Q&A system that uses TF-IDF retrieval combined with Large Language Models (LLM) to answer questions based on a corpus of documents. The system provides both retrieval-augmented generation (RAG) capabilities and direct access to source documents.

## 🏗️ Project Structure

```
pryzm-project/
├── backend/                    # FastAPI backend application
│   ├── app.py                 # Main application entry point
│   ├── settings.py            # Configuration and environment variables
│   ├── schemas.py             # Pydantic models for API requests/responses
│   ├── retriever.py           # TF-IDF document retrieval implementation
│   ├── doc_repo.py            # Document repository for centralized data access
│   ├── llm.py                 # OpenRouter LLM client
│   └── routes/                # API route modules
│       ├── __init__.py
│       ├── answer.py          # Q&A endpoint implementation
│       ├── source.py          # Source document access endpoint
│       ├── health.py          # Health check endpoints
│       └── debug.py           # Debug and testing endpoints
├── data/                      # Data storage directory
│   └── docs.json             # Document corpus (moved from backend/)
├── frontend/                  # React frontend application
│   └── src/                  # React source code
└── scripts/                   # Data processing scripts
    └── out/                  # Processed document outputs
        ├── raw/              # Original PDF files
        ├── trimmed/          # Processed PDF files
        └── docs.json         # Generated corpus (source for data/docs.json)
```

## 🏛️ Architecture

### Core Components

1. **Document Repository (`doc_repo.py`)**: Centralized access to the document corpus with indexing for fast lookups
2. **TF-IDF Retriever (`retriever.py`)**: Implements TF-IDF algorithm for document similarity scoring
3. **LLM Client (`llm.py`)**: Handles communication with OpenRouter API
4. **API Routes**: Modular FastAPI routes for different functionalities

### Data Flow

1. Documents are processed and stored in `data/docs.json`
2. Document repository loads and indexes all documents on startup
3. TF-IDF retriever uses the repository to find relevant documents
4. LLM generates answers based on retrieved context
5. Source endpoint provides direct access to specific document pages

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_PATH` | `./data/docs.json` | Path to the document corpus |
| `OPENROUTER_API_KEY` | *required* | API key for OpenRouter service |
| `OPENROUTER_MODEL` | `anthropic/claude-3.5-sonnet` | LLM model to use |
| `SIM_THRESHOLD` | `0.05` | Minimum similarity score for document retrieval |
| `PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |

## 📡 API Endpoints

### Root Endpoint

#### `GET /`
Returns basic API information.

**Response:**
```json
{
  "message": "Pryzm Project API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

### Health Check Endpoints

#### `GET /health`
Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

#### `GET /llm/health`
Tests the LLM service connection.

**Response:**
```json
{
  "status": "ok|error",
  "model": "anthropic/claude-3.5-sonnet",
  "test_prompt": "This is a health check",
  "sample": "Response from LLM or error message"
}
```

### Q&A Endpoints

#### `POST /answer`
**Legacy endpoint** - Answer questions using retrieval-augmented generation.

**Request Body:**
```json
{
  "prompt": "What is the organizational structure of SSC?"
}
```

**Response:**
```json
{
  "answer_md": "## SSC Organizational Structure\n\nBased on the available documents...",
  "context": [
    {
      "rank": 1,
      "doc_id": "1e9f7f65d4",
      "title": "SSC External Org Chart (Apr 2025)",
      "url": "",
      "doc_date": "2025-04-30",
      "pageno": 2,
      "snippet": "SPACE SYSTEMS COMMAND #SpaceStartsHere..."
    }
  ],
  "used_model": "anthropic/claude-3.5-sonnet",
  "latency_ms": 1250
}
```

#### `POST /v1/answer`
**Versioned endpoint** - Same functionality as `/answer` but under versioned API.

### Source Document Endpoints

#### `GET /source/{doc_id}/{pageno}`
**Legacy endpoint** - Get full page text and metadata for a specific document page.

**Parameters:**
- `doc_id` (string): Document ID from the corpus
- `pageno` (integer): 1-indexed page number (must be >= 1)

**Response:**
```json
{
  "doc_id": "1e9f7f65d4",
  "title": "SSC External Org Chart (Apr 2025)",
  "doc_date": "2025-04-30",
  "url": "",
  "pageno": 2,
  "text": "SPACE SYSTEMS COMMAND #SpaceStartsHere Assured Access to Space..."
}
```

**Error Responses:**
- `400 Bad Request`: Invalid page number (< 1)
- `404 Not Found`: Document or page not found

#### `GET /v1/source/{doc_id}/{pageno}`
**Versioned endpoint** - Same functionality as `/source/{doc_id}/{pageno}` but under versioned API.

### Debug Endpoints

#### `POST /v1/context-debug`
Debug endpoint that returns retrieval results without calling the LLM.

**Request Body:**
```json
{
  "query": "What is the organizational structure?",
  "top_k": 10
}
```

**Response:**
```json
{
  "query": "What is the organizational structure?",
  "top_k": 10,
  "context_count": 5,
  "context": [
    {
      "rank": 1,
      "doc_id": "1e9f7f65d4",
      "title": "SSC External Org Chart (Apr 2025)",
      "url": "",
      "doc_date": "2025-04-30",
      "pageno": 2,
      "snippet": "SPACE SYSTEMS COMMAND #SpaceStartsHere..."
    }
  ]
}
```

## 📊 Data Models

### Request Models

#### `AnswerRequest`
```json
{
  "prompt": "string"
}
```

#### `DebugRequest`
```json
{
  "query": "string",
  "top_k": 10
}
```

### Response Models

#### `AnswerResponse`
```json
{
  "answer_md": "string",
  "context": [ContextItem],
  "used_model": "string",
  "latency_ms": 0
}
```

#### `SourceResponse`
```json
{
  "doc_id": "string",
  "title": "string",
  "doc_date": "string",
  "url": "string",
  "pageno": 0,
  "text": "string"
}
```

#### `ContextItem`
```json
{
  "rank": 0,
  "doc_id": "string",
  "title": "string",
  "url": "string",
  "doc_date": "string",
  "pageno": 0,
  "snippet": "string"
}
```

#### `ErrorResponse`
```json
{
  "error": "string",
  "detail": "string"
}
```

## 📄 Document Corpus Format

The document corpus (`data/docs.json`) follows this structure:

```json
[
  {
    "id": "unique_document_id",
    "title": "Document Title",
    "url": "optional_url",
    "doc_date": "YYYY-MM-DD",
    "pages": [
      {
        "pageno": 1,
        "text": "Full page text content..."
      }
    ]
  }
]
```
