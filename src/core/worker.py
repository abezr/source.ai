"""
Background task worker using arq for Redis-backed task queue with DLQ support.

This module defines the background tasks for processing book uploads, including:
- Book file processing with ToC parsing and chunking
- Automatic retries and Dead Letter Queue for failed jobs
- Redis-backed persistence and scalability
"""

import logging
import os
from typing import Any, Dict

from arq import ArqRedis
from arq.connections import RedisSettings
from arq.worker import Worker

# OpenTelemetry imports for worker metrics
from opentelemetry import metrics
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

try:
    from pydantic import BaseSettings
except ImportError:
    from pydantic_settings import BaseSettings

from .database import SessionLocal
from ..agents.parser import (
    parse_toc_from_pdf,
    extract_text_from_djvu,
    parse_index_from_text,
    identify_index_pages,
)
from ..core import crud

# Worker metrics
worker_meter = metrics.get_meter("hbi_worker")
tasks_processed = worker_meter.create_counter(
    name="hbi_worker_tasks_processed_total",
    description="Total number of tasks processed by the worker",
    unit="1",
)
tasks_failed = worker_meter.create_counter(
    name="hbi_worker_tasks_failed_total",
    description="Total number of tasks that failed",
    unit="1",
)
dlq_size = worker_meter.create_gauge(
    name="hbi_worker_dlq_size",
    description="Current size of the Dead Letter Queue",
    unit="1",
)
queue_depth = worker_meter.create_gauge(
    name="hbi_worker_queue_depth",
    description="Current depth of the task queue",
    unit="1",
)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for serving Prometheus metrics."""

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default HTTP server logs
        pass


def start_metrics_server(port=8000):
    """Start a simple HTTP server to expose metrics."""
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    logging.info(f"Starting metrics server on port {port}")
    server.serve_forever()


# Start metrics server in a separate thread
metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
metrics_thread.start()


class WorkerSettings(BaseSettings):
    """Worker configuration settings for arq."""

    redis_url: str = "redis://localhost:6379"
    max_jobs: int = 10
    job_timeout: int = 3600  # 1 hour timeout
    max_tries: int = 3  # Retry failed jobs up to 3 times
    health_check_interval: int = 60

    class Config:
        env_file = ".env"


async def process_book_file_arq(
    ctx: Dict[str, Any], book_id: int, object_key: str
) -> str:
    """
    Arq background task to process a book file: parse ToC, extract text, parse index, chunk content, generate embeddings, and store everything.

    This task includes automatic retries and DLQ functionality for failed jobs.
    Supports both PDF and DjVu file formats.

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

        # For development/testing, use the object_key as the local file path
        # In production, this would download the file from MinIO
        local_file_path = object_key

        # Detect file type
        file_extension = _detect_file_type(local_file_path)
        logging.info(f"Detected file type: {file_extension} for book {book_id}")

        # Step 1: Parse the ToC using the appropriate parser
        logging.info(f"Step 1: Parsing ToC for book {book_id}")
        if file_extension == "pdf":
            toc_nodes = parse_toc_from_pdf(local_file_path)
        elif file_extension == "djvu":
            # For DjVu files, we'll extract text and parse ToC from it
            # This is a simplified approach - in production, you might want specialized DjVu ToC parsing
            toc_nodes = []  # DjVu ToC parsing would need separate implementation
            logging.info(f"DjVu ToC parsing not implemented yet for book {book_id}")
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Store the hierarchical structure in Neo4j if ToC was found
        if toc_nodes:
            toc_success = crud.create_book_toc_graph(book_id, toc_nodes)
            if not toc_success:
                logging.error(f"Failed to store ToC graph for book {book_id}")
                raise RuntimeError(f"Failed to store ToC graph for book {book_id}")
            logging.info(
                f"Successfully processed ToC for book {book_id}: {len(toc_nodes)} entries"
            )
        else:
            logging.warning(
                f"No ToC found for book {book_id}, continuing with other processing"
            )

        # Step 2: Extract full text content for index parsing
        logging.info(f"Step 2: Extracting text content for book {book_id}")
        if file_extension == "pdf":
            # Use existing PDF text extraction
            from ..agents.parser import _extract_full_text_from_pdf

            full_text = _extract_full_text_from_pdf(local_file_path)
        elif file_extension == "djvu":
            # Use DjVu text extraction
            full_text = extract_text_from_djvu(local_file_path)
        else:
            raise ValueError(
                f"Unsupported file type for text extraction: {file_extension}"
            )

        if not full_text.strip():
            logging.warning(f"No text content found in book {book_id}")
            full_text = ""

        # Step 3: Parse alphabetical index if present
        logging.info(f"Step 3: Parsing alphabetical index for book {book_id}")
        index_entries = []

        if full_text:
            try:
                # Try to identify and parse index pages
                index_pages = identify_index_pages(
                    full_text, len(full_text.split("\n\n"))
                )
                if index_pages:
                    logging.info(
                        f"Found potential index pages: {index_pages} for book {book_id}"
                    )
                    # Extract text from index pages for parsing
                    index_text = _extract_index_text_from_pages(full_text, index_pages)
                    if index_text:
                        index_entries = parse_index_from_text(index_text)

                if index_entries:
                    # Store index in Neo4j graph
                    index_success = crud.create_book_index_graph(book_id, index_entries)
                    if index_success:
                        logging.info(
                            f"Successfully processed index for book {book_id}: {len(index_entries)} entries"
                        )
                    else:
                        logging.error(f"Failed to store index graph for book {book_id}")
                        raise RuntimeError(
                            f"Failed to store index graph for book {book_id}"
                        )
                else:
                    logging.info(f"No alphabetical index found for book {book_id}")

            except Exception as e:
                logging.warning(
                    f"Index parsing failed for book {book_id}: {str(e)}, continuing without index"
                )

        # Step 4: Chunk the book content and generate embeddings
        logging.info(f"Step 4: Chunking and embedding content for book {book_id}")

        # Get a database session for the chunking process
        db = SessionLocal()

        try:
            chunk_success = crud.process_book_chunks_and_embeddings(
                db, book_id, local_file_path
            )

            if chunk_success:
                logging.info(
                    f"Successfully processed chunks and embeddings for book {book_id}"
                )
            else:
                logging.error(
                    f"Failed to process chunks and embeddings for book {book_id}"
                )
                raise RuntimeError(
                    f"Failed to process chunks and embeddings for book {book_id}"
                )

        except Exception as e:
            logging.error(
                f"Error during chunking and embedding for book {book_id}: {str(e)}"
            )
            raise RuntimeError(
                f"Chunking and embedding failed for book {book_id}: {str(e)}"
            )
        finally:
            db.close()

        logging.info(f"Completed arq processing for book {book_id}")
        tasks_processed.add(1, {"status": "success"})
        return f"Successfully processed book {book_id}"

    except Exception as e:
        logging.error(f"Arq processing failed for book {book_id}: {str(e)}")
        tasks_failed.add(1, {"status": "failed"})

        # Check if this is the final retry attempt
        job_try = ctx.get("job_try", 1)
        max_tries = ctx.get("max_tries", 3)

        if job_try >= max_tries:
            logging.error(f"Final retry failed for book {book_id}, moving to DLQ")
            # Move to DLQ
            await move_to_dlq(ctx, book_id, object_key, str(e))

        # Re-raise to trigger retry or DLQ
        raise


async def move_to_dlq(
    ctx: Dict[str, Any], book_id: int, object_key: str, error_message: str
):
    """
    Move failed job to Dead Letter Queue for manual inspection and retry.

    Args:
        ctx: Arq context containing Redis connection and job metadata
        book_id: The ID of the book that failed processing
        object_key: MinIO object key for the uploaded file
        error_message: The error message from the failed job
    """
    redis: ArqRedis = ctx["redis"]
    dlq_key = "dlq:book_processing"

    dlq_entry = {
        "book_id": book_id,
        "object_key": object_key,
        "error_message": error_message,
        "timestamp": str(ctx.get("timestamp", "")),
        "retry_count": ctx.get("job_try", 1),
    }

    await redis.lpush(dlq_key, str(dlq_entry))

    # Update DLQ size metric
    dlq_length = await redis.llen(dlq_key)
    dlq_size.set(dlq_length)

    logging.info(f"Moved failed job for book {book_id} to DLQ")


def _detect_file_type(file_path: str) -> str:
    """
    Detect the file type based on file extension.

    Args:
        file_path: Path to the file

    Returns:
        File extension (lowercase) without the dot
    """
    if not os.path.exists(file_path):
        # Fallback to PDF if file doesn't exist (for development/testing)
        logging.warning(f"File {file_path} does not exist, assuming PDF")
        return "pdf"

    _, ext = os.path.splitext(file_path)
    return ext.lower().lstrip(".")


def _extract_index_text_from_pages(full_text: str, index_pages: list) -> str:
    """
    Extract text content from specific pages that are likely to contain the index.

    Args:
        full_text: Complete text content of the book
        index_pages: List of page numbers that likely contain index

    Returns:
        Concatenated text from index pages
    """
    if not index_pages:
        return ""

    # Split text by pages (assuming page markers are present)
    pages = full_text.split("\n\n")
    index_texts = []

    for page_num in index_pages:
        if 1 <= page_num <= len(pages):  # Page numbers are 1-based
            page_text = pages[page_num - 1]  # Convert to 0-based indexing
            if page_text.strip():
                index_texts.append(page_text)

    return "\n\n".join(index_texts)


async def health_check():
    """Health check function for the worker."""
    # Update queue depth metric
    try:
        redis = ArqRedis(redis_settings)
        queue_length = await redis.llen("arq:queue")
        queue_depth.set(queue_length)
    except Exception as e:
        logging.warning(f"Failed to get queue depth: {str(e)}")

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
