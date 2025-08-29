# HBI System API Documentation

This document provides comprehensive documentation for all API endpoints in the Hybrid Book Index (HBI) system.

## Base URL
```
http://localhost:8000
```

## Authentication
Currently, no authentication is required for API access.

## Response Format
All responses are in JSON format. Error responses include an appropriate HTTP status code and error details.

---

## Health & Monitoring

### GET /health

Simple health check endpoint to confirm the API is running.

**Response:**
```json
{
  "status": "ok",
  "background_tasks": "enabled"
}
```

---

## Configuration Management

### GET /config

Retrieve the current RAG configuration parameters.

**Response:**
```json
{
  "retrieval_top_k": 10,
  "min_chunks": 2,
  "confidence_threshold": 0.7,
  "relevance_threshold": 0.5,
  "max_context_length": 4000,
  "temperature": 0.1,
  "enable_fallback": true
}
```

**Response Schema:**
- `retrieval_top_k` (int): Number of chunks to retrieve in hybrid search
- `min_chunks` (int): Minimum chunks required for retrieval gate
- `confidence_threshold` (float): Minimum confidence score for generation gate (0.0-1.0)
- `relevance_threshold` (float): Minimum relevance score for retrieved chunks (0.0-1.0)
- `max_context_length` (int): Maximum context length for LLM input
- `temperature` (float): LLM temperature for answer generation (0.0-2.0)
- `enable_fallback` (bool): Whether to provide fallback messages when gates fail

### PUT /config

Update the RAG configuration dynamically without requiring code deployment.

**Request Body:**
```json
{
  "retrieval_top_k": 15,
  "min_chunks": 3,
  "confidence_threshold": 0.8,
  "temperature": 0.2
}
```

**Response:** Same as GET /config

**Error Responses:**
- `400 Bad Request`: Invalid configuration parameters
- `422 Unprocessable Entity`: Validation errors with parameter details

---

## Book Management

### POST /books/

Create a new book record.

**Request Body:**
```json
{
  "title": "Sample Book Title",
  "author": "Author Name"
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Sample Book Title",
  "author": "Author Name",
  "source_path": null
}
```

### GET /books/

Retrieve a list of books with pagination support.

**Query Parameters:**
- `skip` (int, optional): Number of books to skip (default: 0)
- `limit` (int, optional): Maximum number of books to return (default: 100, max: 1000)

**Response:**
```json
[
  {
    "id": 1,
    "title": "Book Title 1",
    "author": "Author 1",
    "source_path": "books/book1.pdf"
  },
  {
    "id": 2,
    "title": "Book Title 2",
    "author": "Author 2",
    "source_path": null
  }
]
```

### GET /books/{book_id}

Retrieve details for a specific book.

**Path Parameters:**
- `book_id` (int): The ID of the book to retrieve

**Response:** Same as individual book object from GET /books/

**Error Responses:**
- `404 Not Found`: Book not found

### POST /books/{book_id}/upload

Upload a PDF or DjVu file for a specific book and queue it for background processing.

**Path Parameters:**
- `book_id` (int): The ID of the book to upload file for

**Request Body:** Multipart form data
- `file`: PDF or DjVu file (required)

**Response:** Updated book object with new source_path

**Processing Flow:**
1. File is uploaded to MinIO object storage
2. Background job is queued in Redis/arq
3. Worker processes the file asynchronously:
   - Extracts text content
   - Parses Table of Contents (if available)
   - Parses alphabetical index (if available)
   - Generates embeddings
   - Stores chunks in SQLite with FTS5
   - Stores embeddings in sqlite-vec
   - Stores graph data in Neo4j

**Supported File Types:**
- PDF (.pdf)
- DjVu (.djvu, .djv)

**Error Responses:**
- `404 Not Found`: Book not found
- `400 Bad Request`: Unsupported file type or invalid file
- `500 Internal Server Error`: Upload or processing failed

### GET /books/{book_id}/toc

Retrieve the hierarchical Table of Contents for a specific book.

**Path Parameters:**
- `book_id` (int): The ID of the book to retrieve ToC for

**Response:**
```json
[
  {
    "title": "Chapter 1: Introduction",
    "page_number": 1,
    "children": [
      {
        "title": "1.1 Background",
        "page_number": 2,
        "children": []
      },
      {
        "title": "1.2 Objectives",
        "page_number": 5,
        "children": []
      }
    ]
  },
  {
    "title": "Chapter 2: Methodology",
    "page_number": 10,
    "children": []
  }
]
```

**Response Schema:**
- `title` (string): Section or chapter title
- `page_number` (int): Page number where section begins
- `children` (array): Nested subsections (recursive structure)

**Notes:**
- Returns empty array if no ToC is available
- ToC is extracted during file processing and stored in Neo4j graph database

---

## Query & Search

### POST /query

Query books using hybrid retrieval and grounded generation with quality gates.

**Request Body:**
```json
{
  "query": "What is the main topic of chapter 3?",
  "book_id": 1,
  "top_k": 10
}
```

**Request Parameters:**
- `query` (string, required): The search query or question
- `book_id` (int, optional): Filter to specific book (null for all books)
- `top_k` (int, optional): Override default number of chunks to retrieve

**Response - Successful Query:**
```json
{
  "answer": {
    "answer_summary": "Chapter 3 discusses the fundamental principles of machine learning algorithms...",
    "claims": [
      {
        "text": "Machine learning algorithms learn patterns from data",
        "source_chunk_id": 45,
        "page_number": 67
      },
      {
        "text": "Supervised learning requires labeled training data",
        "source_chunk_id": 46,
        "page_number": 68
      }
    ],
    "confidence_score": 0.89
  }
}
```

**Response - Fallback (Quality Gates Failed):**
```json
{
  "fallback_message": "I couldn't find enough relevant information in the available documents to answer your question confidently. Please try rephrasing your query or check if the information you're looking for is in the uploaded books."
}
```

**RAG Pipeline Process:**

1. **Retrieval Phase:**
   - Performs hybrid search (lexical + vector)
   - Uses configured `retrieval_top_k` parameter
   - Filters by `book_id` if specified

2. **Retrieval Gate:**
   - Checks if `min_chunks` threshold is met
   - Returns fallback if insufficient context found

3. **Generation Phase:**
   - Formats retrieved chunks as context
   - Calls LLM with query and context
   - Applies `temperature` and `max_context_length` settings

4. **Generation Gate:**
   - Validates `confidence_threshold` is met
   - Returns fallback if confidence too low

5. **Success Response:**
   - Returns structured answer with claims and citations
   - Each claim links to source chunk and page number

**Error Responses:**
- `500 Internal Server Error`: Processing failed (includes fallback message)

---

## Error Response Format

All error responses follow this format:

```json
{
  "detail": "Error description message"
}
```

Common HTTP status codes:
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation errors
- `500 Internal Server Error`: Server-side processing errors

---

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing rate limiting for production deployments.

## Data Types

### Book
```typescript
interface Book {
  id: number;
  title: string;
  author: string;
  source_path: string | null;
}
```

### TOCNode
```typescript
interface TOCNode {
  title: string;
  page_number: number;
  children: TOCNode[];
}
```

### QueryRequest
```typescript
interface QueryRequest {
  query: string;
  book_id?: number;
  top_k?: number;
}
```

### QueryResponse
```typescript
interface QueryResponse {
  answer?: {
    answer_summary: string;
    claims: Array<{
      text: string;
      source_chunk_id: number;
      page_number: number;
    }>;
    confidence_score: number;
  };
  fallback_message?: string;
}
```

### RAGConfig
```typescript
interface RAGConfig {
  retrieval_top_k: number;
  min_chunks: number;
  confidence_threshold: number;
  relevance_threshold: number;
  max_context_length: number;
  temperature: number;
  enable_fallback: boolean;
}
```

---

## Background Processing

The system uses Redis/arq for background task processing:

- **Queue**: `redis://localhost:6379`
- **Worker**: Separate container (`hbi_worker`)
- **Retry Policy**: 3 attempts with exponential backoff
- **Dead Letter Queue**: Failed jobs moved to `dlq:book_processing`

Background tasks include:
- File processing (PDF/DjVu parsing)
- Text extraction and chunking
- Embedding generation
- Database storage operations

Monitor background job status through application logs and Redis insights.