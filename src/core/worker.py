"""
Background task worker using arq for Redis-backed task queue with DLQ support.

This module defines the background tasks for processing book uploads, including:
- Book file processing with ToC parsing and chunking
- Automatic retries and Dead Letter Queue for failed jobs
- Redis-backed persistence and scalability
"""

import logging
from typing import Any, Dict

from arq import ArqRedis
from arq.connections import RedisSettings
from arq.worker import Worker
from pydantic import BaseSettings

from .database import SessionLocal
from ..agents.parser import parse_toc_from_pdf
from ..core import crud


class WorkerSettings(BaseSettings):
    """Worker configuration settings for arq."""

    redis_url: str = "redis://localhost:6379"
    max_jobs: int = 10
    job_timeout: int = 3600  # 1 hour timeout
    max_tries: int = 3  # Retry failed jobs up to 3 times
    health_check_interval: int = 60

    class Config:
        env_file = ".env"


async def process_book_file_arq(ctx: Dict[str, Any], book_id: int, object_key: str) -> str:
    """
    Arq background task to process a book file: parse ToC, chunk content, generate embeddings, and store everything.

    This task includes automatic retries and DLQ functionality for failed jobs.

    Args:
        ctx: Arq context containing Redis connection and job metadata
        book_id: The ID of the book to process
        object_key: MinIO object key for the uploaded file

    Returns:
        Success message or raises exception for retry/DLQ
    """
    try:
        logging.info(f"Starting arq processing for book {book_id}, file: {object_key}")

        # TODO: In production, download file from MinIO first
        # For now, assume the file is locally accessible
        # local_file_path = download_from_minio(object_key)

        # For development/testing, we'll use a placeholder
        # In production, this would download the file from MinIO
        local_file_path = f"/tmp/book_{book_id}.pdf"  # Placeholder

        # Step 1: Parse the ToC using the parser agent
        logging.info(f"Step 1: Parsing ToC for book {book_id}")
        toc_nodes = parse_toc_from_pdf(local_file_path)

        if not toc_nodes:
            logging.warning(f"No ToC found for book {book_id}")
            raise ValueError(f"No table of contents found in book {book_id}")

        # Store the hierarchical structure in Neo4j
        toc_success = crud.create_book_toc_graph(book_id, toc_nodes)

        if not toc_success:
            logging.error(f"Failed to store ToC graph for book {book_id}")
            raise RuntimeError(f"Failed to store ToC graph for book {book_id}")

        logging.info(f"Successfully processed ToC for book {book_id}: {len(toc_nodes)} entries")

        # Step 2: Chunk the book content and generate embeddings
        logging.info(f"Step 2: Chunking and embedding content for book {book_id}")

        # Get a database session for the chunking process
        db = SessionLocal()

        try:
            chunk_success = crud.process_book_chunks_and_embeddings(db, book_id, local_file_path)

            if chunk_success:
                logging.info(f"Successfully processed chunks and embeddings for book {book_id}")
            else:
                logging.error(f"Failed to process chunks and embeddings for book {book_id}")
                raise RuntimeError(f"Failed to process chunks and embeddings for book {book_id}")

        except Exception as e:
            logging.error(f"Error during chunking and embedding for book {book_id}: {str(e)}")
            raise RuntimeError(f"Chunking and embedding failed for book {book_id}: {str(e)}")
        finally:
            db.close()

        logging.info(f"Completed arq processing for book {book_id}")
        return f"Successfully processed book {book_id}"

    except Exception as e:
        logging.error(f"Arq processing failed for book {book_id}: {str(e)}")

        # Check if this is the final retry attempt
        job_try = ctx.get('job_try', 1)
        max_tries = ctx.get('max_tries', 3)

        if job_try >= max_tries:
            logging.error(f"Final retry failed for book {book_id}, moving to DLQ")
            # Move to DLQ
            await move_to_dlq(ctx, book_id, object_key, str(e))

        # Re-raise to trigger retry or DLQ
        raise


async def move_to_dlq(ctx: Dict[str, Any], book_id: int, object_key: str, error_message: str):
    """
    Move failed job to Dead Letter Queue for manual inspection and retry.

    Args:
        ctx: Arq context containing Redis connection and job metadata
        book_id: The ID of the book that failed processing
        object_key: MinIO object key for the uploaded file
        error_message: The error message from the failed job
    """
    redis: ArqRedis = ctx['redis']
    dlq_key = "dlq:book_processing"

    dlq_entry = {
        "book_id": book_id,
        "object_key": object_key,
        "error_message": error_message,
        "timestamp": str(ctx.get('timestamp', '')),
        "retry_count": ctx.get('job_try', 1)
    }

    await redis.lpush(dlq_key, str(dlq_entry))
    logging.info(f"Moved failed job for book {book_id} to DLQ")


async def health_check():
    """Health check function for the worker."""
    return {"status": "healthy", "worker": "arq"}


# Worker configuration
worker_settings = WorkerSettings()
redis_settings = RedisSettings.from_dsn(worker_settings.redis_url)

# Define the functions that will be executed by the worker
functions = [process_book_file_arq, health_check]

# Worker instance - this will be started by the worker service
worker = Worker(
    functions=functions,
    redis_settings=redis_settings,
    max_jobs=worker_settings.max_jobs,
    job_timeout=worker_settings.job_timeout,
    max_tries=worker_settings.max_tries,
    health_check_interval=worker_settings.health_check_interval,
)