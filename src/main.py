from fastapi import FastAPI, Depends, BackgroundTasks, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
import os
from arq import ArqRedis
from arq.connections import RedisSettings
from .core.database import get_db, initialize_database
from .core import models, schemas, crud
from .core.object_store import get_object_store_client
from .core.llm_client import get_llm_client
from .core.config_store import get_rag_config, update_rag_config


def get_redis_client() -> ArqRedis:
    """Get Redis client for enqueuing background jobs."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_settings = RedisSettings.from_dsn(redis_url)
    return ArqRedis(redis_settings)


app = FastAPI(
    title="Hybrid Book Index (HBI) System",
    description="API for indexing and querying book content.",
    version="0.1.0",
)

@app.get("/health", tags=["Monitoring"])
async def health_check(background_tasks: BackgroundTasks):
    """
    Simple health check endpoint to confirm the API is running.
    Also demonstrates background task capability.
    """
    # Add a simple background task to demonstrate functionality
    background_tasks.add_task(log_health_check_request)
    return {"status": "ok", "background_tasks": "enabled"}


def log_health_check_request():
    """
    Simple background task that logs when health check is called.
    This demonstrates the background task processing capability.
    """
    import logging
    logging.info("Health check triggered a background task!")
    print("Health check triggered a background task!")


@app.get("/config", response_model=schemas.RAGConfig, tags=["Configuration"])
async def get_config():
    """
    Get the current RAG configuration.

    Returns the current configuration parameters used by the RAG pipeline.
    These parameters control retrieval, generation, and quality thresholds.

    Returns:
        RAGConfig: Current RAG configuration
    """
    return get_rag_config()


@app.put("/config", response_model=schemas.RAGConfig, tags=["Configuration"])
async def update_config(config: schemas.RAGConfig):
    """
    Update the RAG configuration.

    Allows dynamic tuning of RAG pipeline parameters without requiring code deployment.
    Changes take effect immediately for all subsequent queries.

    - **config**: New RAG configuration parameters
    - **retrieval_top_k**: Number of chunks to retrieve in hybrid search
    - **min_chunks**: Minimum chunks required for retrieval gate
    - **confidence_threshold**: Minimum confidence score for generation gate
    - **relevance_threshold**: Minimum relevance score for retrieved chunks
    - **max_context_length**: Maximum context length for LLM input
    - **temperature**: LLM temperature for answer generation
    - **enable_fallback**: Whether to provide fallback messages when gates fail

    Returns:
        RAGConfig: Updated configuration

    Raises:
        HTTPException: If configuration parameters are invalid
    """
    try:
        updated_config = update_rag_config(config)
        logging.info(f"Configuration updated via API: {config.dict()}")
        return updated_config
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/books/", response_model=schemas.Book, tags=["Books"])
async def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    """
    Create a new book record.

    - **book**: Book data to create
    - **db**: Database session (injected automatically)
    """
    return crud.create_book(db=db, book=book)

@app.get("/books/", response_model=list[schemas.Book], tags=["Books"])
async def read_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of books.

    - **skip**: Number of books to skip (pagination)
    - **limit**: Maximum number of books to return (default: 100)
    """
    books = crud.get_books(db, skip=skip, limit=limit)
    return books

@app.get("/books/{book_id}", response_model=schemas.Book, tags=["Books"])
async def read_book(book_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific book by ID.

    - **book_id**: The ID of the book to retrieve
    """
    db_book = crud.get_book(db, book_id=book_id)
    if db_book is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Book not found")
    return db_book


@app.post("/books/{book_id}/upload", response_model=schemas.Book, tags=["Books"])
async def upload_book_file(
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a book file (PDF) for a specific book record.

    - **book_id**: The ID of the book to upload file for
    - **file**: The PDF file to upload
    - **db**: Database session (injected automatically)

    The file will be stored in MinIO and the book's source_path will be updated.
    Background processing will be handled by Redis/arq workers.
    """
    # Validate that the book exists
    db_book = crud.get_book(db, book_id=book_id)
    if db_book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    # Validate file type (basic check)
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    try:
        # Get object store client
        object_store = get_object_store_client()

        # Generate unique object name
        object_name = object_store.generate_unique_object_name(file.filename, book_id)

        # Upload file to MinIO
        object_store.upload_file_to_books_bucket(
            file_object=file.file,
            object_name=object_name,
            content_type='application/pdf'
        )

        # Update book's source_path in database
        updated_book = crud.update_book_source_path(db, book_id, object_name)
        if updated_book is None:
            raise HTTPException(status_code=500, detail="Failed to update book record")

        # Enqueue background processing job with arq
        redis_client = get_redis_client()
        await redis_client.enqueue_job(
            'process_book_file_arq',
            book_id,
            object_name
        )

        logging.info(f"Enqueued background processing job for book {book_id}, file: {object_name}")
        return updated_book

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )


    
    
    @app.get("/books/{book_id}/toc", response_model=List[schemas.TOCNode], tags=["Books"])
    async def get_book_toc(book_id: int, db: Session = Depends(get_db)):
        """
        Retrieve the hierarchical Table of Contents for a specific book.
    
        - **book_id**: The ID of the book to retrieve ToC for
        - **db**: Database session (injected automatically)
    
        Returns the hierarchical ToC structure as parsed from the book's PDF.
        If no ToC is available, returns an empty list.
        """
        # First verify the book exists
        db_book = crud.get_book(db, book_id=book_id)
        if db_book is None:
            raise HTTPException(status_code=404, detail="Book not found")
    
        # Retrieve ToC from Neo4j graph database
        toc_nodes = crud.get_toc_by_book_id(book_id)
    
        return toc_nodes


@app.post("/query", response_model=schemas.QueryResponse, tags=["Query"])
async def query_books(
    request: schemas.QueryRequest,
    db: Session = Depends(get_db)
):
    """
    Query books using hybrid retrieval and grounded generation with quality gates.

    This endpoint implements the complete RAG pipeline with anti-hallucination gates:
    1. Retrieval Gate: Ensures sufficient relevant context is found
    2. Generation Gate: Ensures high-confidence grounded answers
    3. Fallback: Provides helpful messages when gates prevent answering

    - **request**: Query request with question and optional filters
    - **db**: Database session (injected automatically)

    Returns a structured answer with citations or a fallback message.
    """
    try:
        logging.info(f"Processing query: '{request.query}' (book_id: {request.book_id}, top_k: {request.top_k})")

        # Get current RAG configuration
        config = get_rag_config()

        # Step 1: Retrieval Phase
        logging.info("Step 1: Performing hybrid retrieval")
        retrieved_chunks = crud.hybrid_retrieve(
            db=db,
            query=request.query,
            top_k=config.retrieval_top_k if request.top_k is None else request.top_k,
            book_id=request.book_id
        )

        # Step 2: Retrieval Gate
        if len(retrieved_chunks) < config.min_chunks:
            fallback_msg = "I couldn't find enough relevant information in the available documents to answer your question confidently. Please try rephrasing your query or check if the information you're looking for is in the uploaded books."
            logging.warning(f"Retrieval gate failed: only {len(retrieved_chunks)} chunks found (minimum: {config.min_chunks})")
            return schemas.QueryResponse(fallback_message=fallback_msg)

        logging.info(f"Retrieval gate passed: {len(retrieved_chunks)} chunks retrieved")

        # Step 3: Format context for LLM
        context = _format_chunks_for_llm(retrieved_chunks)

        # Step 4: Generation Phase
        logging.info("Step 4: Generating grounded answer")
        llm_client = get_llm_client()
        answer = llm_client.generate_grounded_answer(
            query=request.query,
            context=context
        )

        # Step 5: Generation Gate
        if answer.confidence_score < config.confidence_threshold:
            fallback_msg = "I'm not confident enough in my answer to provide it accurately. The available information doesn't sufficiently support a reliable response to your question."
            logging.warning(f"Generation gate failed: confidence {answer.confidence_score:.2f} below threshold {config.confidence_threshold}")
            return schemas.QueryResponse(fallback_message=fallback_msg)

        # Step 6: Success - return structured answer
        logging.info(f"Generation gate passed: confidence {answer.confidence_score:.2f}, returning structured answer")
        return schemas.QueryResponse(answer=answer)

    except Exception as e:
        error_msg = "I encountered an error while processing your query. Please try again."
        logging.error(f"Query processing failed: {str(e)}")
        return schemas.QueryResponse(fallback_message=error_msg)


def _format_chunks_for_llm(chunks: List[models.Chunk]) -> str:
    """
    Format retrieved chunks into context string for LLM consumption.

    Args:
        chunks: List of Chunk objects from retrieval

    Returns:
        Formatted context string with chunk IDs and page numbers
    """
    if not chunks:
        return "No context available."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Chunk {i} - ID: {chunk.id}, Page: {chunk.page_number}]\n"
            f"{chunk.chunk_text}\n"
        )

    return "\n".join(context_parts)


# Initialize database with tables and FTS5 virtual tables
initialize_database()