# HBI System Advanced Ingestion Guide

This guide covers the advanced document ingestion capabilities of the Hybrid Book Index (HBI) system, including DjVu format support and LLM-powered alphabetical index processing.

## Overview

The HBI system supports advanced document ingestion with multiple file formats and intelligent content extraction. The ingestion pipeline includes text extraction, table of contents parsing, alphabetical index processing, and semantic chunking with embeddings.

## Supported File Formats

### PDF Format Support

**Standard Features:**
- Text extraction using PyMuPDF (Fitz)
- Table of Contents (ToC) parsing with LLM assistance
- Page-based chunking with semantic boundaries
- Embedding generation for vector search

**Processing Pipeline:**
1. PDF parsing with page-by-page text extraction
2. ToC identification and hierarchical parsing
3. Alphabetical index detection and parsing
4. Semantic chunking with overlap
5. Embedding generation and storage

### DjVu Format Support

**New in Sprint 4:**
- Full DjVu text extraction using `djvulibre-bin`
- Native DjVu ToC support (when available)
- Index processing with LLM assistance
- Seamless integration with existing pipeline

**Technical Implementation:**
```python
def extract_text_from_djvu(file_path: str) -> str:
    """Extract text content from DjVu using djvutxt command."""
    result = subprocess.run(
        ['djvutxt', file_path],
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    return result.stdout
```

**Requirements:**
- `djvulibre-bin` package installed in Docker container
- Subprocess execution with timeout handling
- Error handling for corrupted DjVu files

## Table of Contents Processing

### ToC Extraction Strategy

**Heuristic Approach:**
- Scan pages 2-5 for common ToC patterns
- Look for structural indicators (chapter, section, part)
- Identify page number patterns and formatting

**LLM-Powered Parsing:**
- Sanitized text input for security
- Structured output parsing with validation
- Hierarchical relationship extraction
- Error handling and graceful degradation

### ToC Data Structure

**Hierarchical Storage:**
```python
class TOCNode(BaseModel):
    title: str
    page_number: int
    children: List['TOCNode'] = []
```

**Neo4j Graph Storage:**
- `Book` nodes with ToC relationships
- `TOCSection` nodes with hierarchical connections
- Page number indexing for quick access
- Full-text search integration

## Alphabetical Index Processing

### Index Detection and Extraction

**Heuristic Page Identification:**
- Scan last 5% of document pages
- Look for alphabetical patterns (A, B, C...)
- Identify page number references
- Detect index-specific terminology

**Algorithm:**
```python
def identify_index_pages(text: str, total_pages: int) -> List[int]:
    """Identify pages likely containing alphabetical index."""
    pages_to_check = max(5, int(total_pages * 0.05))
    start_page = max(0, total_pages - pages_to_check)

    for page_num in range(start_page, total_pages):
        if _is_likely_index_page(page_text):
            return page_num
```

### LLM-Powered Index Parsing

**Specialized Prompting:**
- Context-aware index parsing prompts
- Multiple format support (numbered, bulleted, etc.)
- Term normalization and deduplication
- Page reference validation

**Index Entry Schema:**
```python
class IndexEntry(BaseModel):
    term: str
    page_numbers: List[int]
```

**Supported Index Formats:**
- Standard alphabetical indexes
- Subject-specific indexes
- Author and name indexes
- Cross-referenced entries
- Multi-page term references

### Index Graph Storage

**Neo4j Implementation:**
- `IndexTerm` nodes for each index entry
- `APPEARS_ON_PAGE` relationships
- `BELONGS_TO_BOOK` connections
- Full-text search indexing

**Query Capabilities:**
- Term-based index lookup
- Page number retrieval
- Cross-reference navigation
- Fuzzy term matching

## Content Processing Pipeline

### Step-by-Step Processing

**1. File Upload and Validation:**
```python
# File type detection
file_extension = _detect_file_type(file_path)

# Format-specific processing
if file_extension == 'pdf':
    text_content = extract_text_from_pdf(file_path)
elif file_extension == 'djvu':
    text_content = extract_text_from_djvu(file_path)
```

**2. ToC Extraction:**
```python
# Heuristic ToC identification
toc_text = _extract_toc_text_from_pdf(file_path)

# LLM-powered parsing
toc_nodes = parse_toc_from_pdf(file_path)
```

**3. Index Processing:**
```python
# Index page identification
index_pages = identify_index_pages(text_content, total_pages)

# LLM-powered index parsing
index_entries = parse_index_from_text(index_text)
```

**4. Content Chunking:**
```python
# Semantic chunking with overlap
chunks = _perform_semantic_chunking(text_content)

# Embedding generation
chunks_with_embeddings = generate_embeddings_for_chunks(chunks)
```

**5. Storage Operations:**
```python
# SQLite storage for chunks and embeddings
crud.process_book_chunks_and_embeddings(db, book_id, chunks)

# Neo4j storage for ToC and index
crud.create_book_toc_graph(book_id, toc_nodes)
crud.create_book_index_graph(book_id, index_entries)
```

## Background Processing Architecture

### Redis/arq Integration

**Task Queue Benefits:**
- Asynchronous processing for large documents
- Scalable worker pool architecture
- Automatic retry mechanism (3 attempts)
- Dead Letter Queue for failed jobs

**Worker Configuration:**
```python
class WorkerSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    max_jobs: int = 10
    job_timeout: int = 3600  # 1 hour
    max_tries: int = 3
```

### Error Handling and Recovery

**Retry Logic:**
- Exponential backoff for transient failures
- Different retry strategies per error type
- Maximum retry limits to prevent infinite loops

**Dead Letter Queue:**
```python
async def move_to_dlq(ctx, book_id, object_key, error_message):
    """Move failed jobs to DLQ for manual inspection."""
    dlq_entry = {
        "book_id": book_id,
        "object_key": object_key,
        "error_message": error_message,
        "timestamp": ctx.get('timestamp'),
        "retry_count": ctx.get('job_try', 1)
    }
    await redis.lpush("dlq:book_processing", str(dlq_entry))
```

## Performance Optimization

### Chunking Strategies

**Semantic Chunking:**
- Paragraph and sentence boundary detection
- Configurable chunk size (default: 1000 characters)
- Overlap between chunks (default: 200 characters)
- Page number preservation for citations

**Embedding Optimization:**
- Batch processing for efficiency
- CPU-optimized models (`sentence-transformers/all-MiniLM-L6-v2`)
- Memory-efficient processing
- Progress tracking and logging

### Database Optimization

**SQLite FTS5 Integration:**
- Full-text search for lexical queries
- Fast prefix and fuzzy matching
- Efficient storage with compression

**Neo4j Graph Performance:**
- Optimized Cypher queries
- Index usage for fast lookups
- Connection pooling and caching

## Monitoring and Observability

### Processing Metrics

**Background Job Monitoring:**
- Job queue length and processing rates
- Success/failure rates by file type
- Processing time per document
- Worker utilization statistics

**Quality Metrics:**
- ToC parsing accuracy
- Index extraction completeness
- Chunk quality and relevance
- Embedding generation success rates

### Logging and Debugging

**Structured Logging:**
```python
logger.info(
    f"Processing completed for book {book_id}: "
    f"chunks={len(chunks)}, "
    f"toc_entries={len(toc_nodes)}, "
    f"index_entries={len(index_entries)}"
)
```

**Error Tracking:**
- Detailed error messages with context
- Stack traces for debugging
- Performance bottleneck identification
- Resource usage monitoring

## File Format Limitations and Workarounds

### PDF Limitations

**Text Extraction Issues:**
- Scanned documents without OCR
- Complex layouts and multi-column text
- Embedded images and graphics
- Encrypted or password-protected files

**Workarounds:**
- Pre-processing with OCR tools
- Layout analysis for complex documents
- Fallback to image-based processing

### DjVu Limitations

**Compatibility Issues:**
- Older DjVu format variations
- Corrupted or incomplete files
- Missing text layers in image-only DjVu
- Encoding issues with special characters

**Workarounds:**
- File validation before processing
- Fallback text extraction methods
- Error recovery and retry logic

## Best Practices

### Document Preparation

**Pre-Processing Recommendations:**
1. Ensure text is selectable (not image-only)
2. Verify ToC and index are properly formatted
3. Check for OCR quality in scanned documents
4. Validate file integrity before upload

### Processing Optimization

**Performance Tuning:**
1. Adjust chunk size based on document type
2. Configure worker pool size for load
3. Monitor Redis queue depth
4. Optimize embedding model selection

### Quality Assurance

**Validation Steps:**
1. Verify ToC extraction accuracy
2. Check index term completeness
3. Validate chunk semantic coherence
4. Test search relevance with sample queries

## Troubleshooting Common Issues

### ToC Extraction Problems

**Symptoms:**
- Empty or incomplete ToC
- Incorrect hierarchical structure
- Missing page numbers

**Solutions:**
- Check document ToC formatting
- Adjust page scanning range
- Review LLM prompt effectiveness
- Verify text extraction quality

### Index Processing Issues

**Symptoms:**
- Missing index entries
- Incorrect page number parsing
- Poor term normalization

**Solutions:**
- Verify index page identification
- Check LLM parsing prompts
- Review text sanitization impact
- Validate page number formats

### Performance Issues

**Symptoms:**
- Slow processing times
- High memory usage
- Worker timeouts

**Solutions:**
- Reduce chunk size or overlap
- Increase worker timeout limits
- Optimize embedding batch sizes
- Monitor system resource usage

## Future Enhancements

### Planned Features

**Advanced Format Support:**
- EPUB and MOBI format support
- OCR integration for image-based PDFs
- Multi-language document processing
- Mathematical formula extraction

**Processing Improvements:**
- ML-based ToC detection
- Advanced chunking algorithms
- Real-time processing status
- Parallel processing optimization

**Quality Enhancements:**
- Automated quality scoring
- Content validation pipelines
- Duplicate detection and merging
- Semantic relationship extraction

## Integration Examples

### API Integration

**Upload and Process Document:**
```python
# Upload file
response = requests.post(
    "http://localhost:8000/books/1/upload",
    files={"file": open("document.pdf", "rb")}
)

# Check processing status (future enhancement)
# status = requests.get(f"http://localhost:8000/books/1/status")
```

**Query with Index Support:**
```python
# Query using index terms
response = requests.post(
    "http://localhost:8000/query",
    json={
        "query": "machine learning algorithms",
        "book_id": 1
    }
)
```

### Monitoring Integration

**Health Checks:**
```python
# Worker health
response = requests.get("http://localhost:8000/health")

# Queue status (Redis)
# queue_length = redis.llen("arq:queue")
```

This comprehensive ingestion system provides robust document processing capabilities with support for multiple formats, intelligent content extraction, and scalable background processing.