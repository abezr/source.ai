"""
Parser agent for HBI system.
Handles PDF parsing, Table of Contents extraction, and content chunking with embeddings.
"""

import logging
import subprocess
from typing import List, Optional, Dict, Any
import fitz  # PyMuPDF
from pydantic import ValidationError
from fastembed import TextEmbedding

from ..core.schemas import TOCNode, IndexEntry
from ..core.llm_client import get_llm_client
from ..core.sanitizer import sanitize_text_with_audit

# Set up logging
logger = logging.getLogger(__name__)


def parse_toc_from_pdf(file_path: str) -> List[TOCNode]:
    """
    Extract and parse Table of Contents from a PDF file.

    Args:
        file_path: Path to the PDF file (can be local path or MinIO object key)

    Returns:
        List of TOCNode objects representing the hierarchical structure

    Raises:
        FileNotFoundError: If the PDF file cannot be found or opened
        Exception: If parsing fails
    """
    try:
        # Extract raw ToC text from PDF
        toc_text = _extract_toc_text_from_pdf(file_path)

        if not toc_text.strip():
            logger.warning(f"No ToC text found in {file_path}")
            return []

        # Sanitize text before LLM processing for security
        sanitized_result = sanitize_text_with_audit(toc_text, context="toc")
        if sanitized_result.is_modified:
            logger.info(
                f"ToC text sanitized for {file_path}: {sanitized_result.changes_made}"
            )

        # Parse the sanitized text using LLM
        llm_client = get_llm_client()
        structured_data = llm_client.get_structured_toc(sanitized_result.sanitized_text)

        # Validate and convert to Pydantic models
        toc_nodes = _validate_and_convert_toc_data(structured_data)

        logger.info(
            f"Successfully parsed {len(toc_nodes)} ToC entries from {file_path}"
        )
        return toc_nodes

    except FileNotFoundError:
        logger.error(f"PDF file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to parse ToC from {file_path}: {str(e)}")
        # Return empty list instead of raising to allow graceful degradation
        return []


def _extract_toc_text_from_pdf(file_path: str) -> str:
    """
    Extract table of contents text from PDF using heuristic approach.

    Args:
        file_path: Path to the PDF file

    Returns:
        Raw text content from potential ToC pages

    Raises:
        FileNotFoundError: If the PDF cannot be opened
    """
    try:
        # Open the PDF document
        doc = fitz.open(file_path)

        toc_text_parts = []

        # Heuristic: Check pages 2-5 for ToC (common locations)
        # In production, this could be enhanced with ML-based ToC detection
        potential_toc_pages = range(min(2, doc.page_count), min(6, doc.page_count))

        for page_num in potential_toc_pages:
            try:
                page = doc.load_page(page_num)
                text = page.get_text()

                # Basic heuristic to identify ToC content
                if _is_likely_toc_page(text):
                    toc_text_parts.append(text)
                    logger.debug(f"Found potential ToC content on page {page_num + 1}")

            except Exception as e:
                logger.warning(
                    f"Failed to extract text from page {page_num + 1}: {str(e)}"
                )
                continue

        doc.close()

        # Join all potential ToC text
        full_toc_text = "\n".join(toc_text_parts)

        if not full_toc_text.strip():
            logger.warning("No text content found in potential ToC pages")

        return full_toc_text

    except Exception as e:
        logger.error(f"Failed to open or read PDF {file_path}: {str(e)}")
        raise FileNotFoundError(f"Cannot open PDF file: {file_path}")


def _is_likely_toc_page(text: str) -> bool:
    """
    Heuristic to determine if a page likely contains table of contents.

    Args:
        text: Extracted text from the page

    Returns:
        True if page appears to contain ToC content
    """
    text_lower = text.lower()

    # Common ToC indicators
    toc_indicators = [
        "table of contents",
        "contents",
        "chapter",
        "section",
        "part",
        "introduction",
        "preface",
    ]

    # Check for multiple ToC indicators
    indicator_count = sum(1 for indicator in toc_indicators if indicator in text_lower)

    # Check for page number patterns (e.g., "Chapter 1 ........ 5")
    page_pattern_indicators = ["...", " . . . ", "—", "–"]

    has_page_patterns = any(pattern in text for pattern in page_pattern_indicators)

    # Consider it a ToC page if it has multiple indicators or page patterns
    return indicator_count >= 2 or has_page_patterns


def _validate_and_convert_toc_data(data: dict) -> List[TOCNode]:
    """
    Validate LLM response data and convert to TOCNode objects.

    Args:
        data: Structured data from LLM (expected to be a list of dicts)

    Returns:
        List of validated TOCNode objects

    Raises:
        ValidationError: If data doesn't match expected schema
    """
    try:
        if not isinstance(data, list):
            logger.warning("LLM response is not a list, attempting to wrap in list")
            if isinstance(data, dict):
                data = [data]
            else:
                raise ValidationError("LLM response must be a list or dict")

        toc_nodes = []
        for item in data:
            try:
                # Ensure children is a list
                if "children" not in item:
                    item["children"] = []
                elif not isinstance(item["children"], list):
                    item["children"] = []

                # Recursively validate children
                if item["children"]:
                    item["children"] = _validate_and_convert_toc_data(item["children"])

                # Create TOCNode
                node = TOCNode(**item)
                toc_nodes.append(node)

            except ValidationError as e:
                logger.warning(f"Skipping invalid ToC item: {item}, error: {str(e)}")
                continue

        return toc_nodes

    except Exception as e:
        logger.error(f"Failed to validate ToC data: {str(e)}")
        raise ValidationError(f"Invalid ToC structure: {str(e)}")


def download_pdf_from_minio(object_key: str, local_path: str) -> str:
    """
    Download a PDF from MinIO to local filesystem for processing.

    Args:
        object_key: MinIO object key
        local_path: Local path to save the file

    Returns:
        Local path to the downloaded file

    Note:
        This function would be implemented when integrating with MinIO,
        but for now it's a placeholder for the complete workflow.
    """
    # TODO: Implement MinIO download functionality
    # This would use the object_store client to download the file
    logger.info(f"Would download {object_key} to {local_path}")
    return local_path


def chunk_book_content(file_path: str, book_id: int) -> List[dict]:
    """
    Extract and chunk the full text content of a PDF book into semantic chunks.

    Args:
        file_path: Path to the PDF file
        book_id: ID of the book being processed

    Returns:
        List of dictionaries containing chunk data:
        {
            'chunk_text': str,
            'page_number': int,
            'chunk_order': int
        }

    Raises:
        FileNotFoundError: If the PDF file cannot be found or opened
        Exception: If chunking fails
    """
    try:
        # Extract full text content from PDF
        full_text = _extract_full_text_from_pdf(file_path)

        if not full_text.strip():
            logger.warning(f"No text content found in {file_path}")
            return []

        # Perform semantic chunking
        chunks = _perform_semantic_chunking(full_text)

        logger.info(f"Successfully created {len(chunks)} chunks from {file_path}")
        return chunks

    except FileNotFoundError:
        logger.error(f"PDF file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to chunk content from {file_path}: {str(e)}")
        raise


def _extract_full_text_from_pdf(file_path: str) -> str:
    """
    Extract the full text content from a PDF file, page by page.

    Args:
        file_path: Path to the PDF file

    Returns:
        Complete text content of the PDF

    Raises:
        FileNotFoundError: If the PDF cannot be opened
    """
    try:
        doc = fitz.open(file_path)
        full_text_parts = []

        for page_num in range(doc.page_count):
            try:
                page = doc.load_page(page_num)
                text = page.get_text()

                if text.strip():  # Only include pages with content
                    # Add page marker for better chunk attribution
                    full_text_parts.append(f"[PAGE {page_num + 1}]\n{text.strip()}")

            except Exception as e:
                logger.warning(
                    f"Failed to extract text from page {page_num + 1}: {str(e)}"
                )
                continue

        doc.close()

        full_text = "\n\n".join(full_text_parts)

        if not full_text.strip():
            logger.warning("No text content found in any pages")

        return full_text

    except Exception as e:
        logger.error(f"Failed to open or read PDF {file_path}: {str(e)}")
        raise FileNotFoundError(f"Cannot open PDF file: {file_path}")


def _perform_semantic_chunking(
    text: str, chunk_size: int = 1000, overlap: int = 200
) -> List[dict]:
    """
    Perform semantic chunking on text content using paragraph and sentence boundaries.

    Args:
        text: Full text content to chunk
        chunk_size: Target size for each chunk in characters
        overlap: Number of characters to overlap between chunks

    Returns:
        List of chunk dictionaries with text, page_number, and chunk_order
    """
    # Split text into paragraphs first (more semantic than fixed-size chunks)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""
    current_page = 1
    chunk_order = 0

    for paragraph in paragraphs:
        # Extract page number from paragraph if present
        page_num = _extract_page_number_from_paragraph(paragraph)
        if page_num:
            current_page = page_num

        # Check if adding this paragraph would exceed chunk size
        if len(current_chunk + paragraph) > chunk_size and current_chunk:
            # Create chunk from current content
            chunk_data = {
                "chunk_text": current_chunk.strip(),
                "page_number": current_page,
                "chunk_order": chunk_order,
            }
            chunks.append(chunk_data)
            chunk_order += 1

            # Start new chunk with overlap from previous chunk
            words = current_chunk.split()
            if len(words) > 10:  # Ensure we have enough content for overlap
                overlap_text = " ".join(words[-50:])  # Last ~50 words as overlap
                current_chunk = overlap_text + " " + paragraph
            else:
                current_chunk = paragraph
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    # Add final chunk if it has content
    if current_chunk.strip():
        chunk_data = {
            "chunk_text": current_chunk.strip(),
            "page_number": current_page,
            "chunk_order": chunk_order,
        }
        chunks.append(chunk_data)

    return chunks


def _extract_page_number_from_paragraph(paragraph: str) -> Optional[int]:
    """
    Extract page number from paragraph text if present.

    Args:
        paragraph: Text paragraph that may contain page marker

    Returns:
        Page number if found, None otherwise
    """
    import re

    # Look for [PAGE X] markers
    page_match = re.search(r"\[PAGE (\d+)\]", paragraph)
    if page_match:
        try:
            return int(page_match.group(1))
        except ValueError:
            pass

    return None


def generate_embeddings_for_chunks(chunks: List[dict]) -> List[Dict[str, Any]]:
    """
    Generate vector embeddings for text chunks using FastEmbed.

    Args:
        chunks: List of chunk dictionaries from chunk_book_content()

    Returns:
        List of chunk dictionaries with added 'embedding' field containing the vector

    Raises:
        Exception: If embedding generation fails
    """
    try:
        if not chunks:
            logger.warning("No chunks provided for embedding generation")
            return []

        # Initialize FastEmbed model (using a CPU-optimized model)
        embedding_model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # Extract text content from chunks
        texts = [chunk["chunk_text"] for chunk in chunks]

        logger.info(f"Generating embeddings for {len(texts)} text chunks")

        # Generate embeddings in batches for efficiency
        embeddings = list(embedding_model.embed(texts))

        # Add embeddings to chunk data
        chunks_with_embeddings = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_with_embedding = chunk.copy()
            chunk_with_embedding["embedding"] = (
                embedding.tolist()
            )  # Convert numpy array to list
            chunks_with_embeddings.append(chunk_with_embedding)

        logger.info(
            f"Successfully generated embeddings for {len(chunks_with_embeddings)} chunks"
        )
        return chunks_with_embeddings

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {str(e)}")
        raise


def chunk_and_embed_book(file_path: str, book_id: int) -> List[Dict[str, Any]]:
    """
    Complete pipeline: chunk book content and generate embeddings.

    Args:
        file_path: Path to the PDF file
        book_id: ID of the book being processed

    Returns:
        List of chunk dictionaries with embeddings ready for storage

    Raises:
        Exception: If any step in the pipeline fails
    """
    try:
        logger.info(f"Starting chunk and embed pipeline for book {book_id}")

        # Step 1: Chunk the book content
        chunks = chunk_book_content(file_path, book_id)

        if not chunks:
            logger.warning(f"No chunks generated for book {book_id}")
            return []

        # Step 2: Generate embeddings for chunks
        chunks_with_embeddings = generate_embeddings_for_chunks(chunks)

        logger.info(
            f"Successfully completed chunk and embed pipeline for book {book_id}: {len(chunks_with_embeddings)} chunks with embeddings"
        )
        return chunks_with_embeddings

    except Exception as e:
        logger.error(f"Failed chunk and embed pipeline for book {book_id}: {str(e)}")
        raise


def extract_text_from_djvu(file_path: str) -> str:
    """
    Extract text content from a DjVu file using djvutxt command.

    Args:
        file_path: Path to the DjVu file

    Returns:
        Complete text content of the DjVu file

    Raises:
        FileNotFoundError: If the DjVu file cannot be found or opened
        Exception: If text extraction fails
    """
    try:
        logger.info(f"Extracting text from DjVu file: {file_path}")

        # Use djvutxt command to extract text
        result = subprocess.run(
            ["djvutxt", file_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error"
            raise Exception(f"djvutxt command failed: {error_msg}")

        text_content = result.stdout

        if not text_content.strip():
            logger.warning(f"No text content found in DjVu file: {file_path}")
            return ""

        logger.info(
            f"Successfully extracted {len(text_content)} characters from DjVu file"
        )
        return text_content

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout extracting text from DjVu file: {file_path}")
        raise Exception(f"Text extraction timed out for DjVu file: {file_path}")
    except FileNotFoundError:
        logger.error(f"DjVu file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to extract text from DjVu file {file_path}: {str(e)}")
        raise


def parse_index_from_text(text: str) -> List[IndexEntry]:
    """
    Parse alphabetical index from text content using LLM.

    Args:
        text: Raw text content that may contain an index

    Returns:
        List of IndexEntry objects representing the parsed index

    Raises:
        Exception: If index parsing fails
    """
    try:
        logger.info("Parsing alphabetical index from text content")

        # Sanitize text before LLM processing for security
        sanitized_result = sanitize_text_with_audit(text, context="index")
        if sanitized_result.is_modified:
            logger.info(f"Index text sanitized: {sanitized_result.changes_made}")

        # Use LLM to parse the sanitized index
        llm_client = get_llm_client()
        structured_data = llm_client.get_structured_index(
            sanitized_result.sanitized_text
        )

        # Validate and convert to Pydantic models
        index_entries = _validate_and_convert_index_data(structured_data)

        logger.info(f"Successfully parsed {len(index_entries)} index entries")
        return index_entries

    except Exception as e:
        logger.error(f"Failed to parse index from text: {str(e)}")
        # Return empty list instead of raising to allow graceful degradation
        return []


def _validate_and_convert_index_data(data: dict) -> List[IndexEntry]:
    """
    Validate LLM response data and convert to IndexEntry objects.

    Args:
        data: Structured data from LLM (expected to be a list of dicts)

    Returns:
        List of validated IndexEntry objects

    Raises:
        ValidationError: If data doesn't match expected schema
    """
    try:
        if not isinstance(data, list):
            logger.warning("LLM response is not a list, attempting to wrap in list")
            if isinstance(data, dict):
                data = [data]
            else:
                raise ValidationError("LLM response must be a list or dict")

        index_entries = []
        for item in data:
            try:
                # Ensure page_numbers is a list
                if "page_numbers" not in item:
                    item["page_numbers"] = []
                elif not isinstance(item["page_numbers"], list):
                    item["page_numbers"] = []

                # Convert page numbers to integers
                item["page_numbers"] = [
                    int(page) for page in item["page_numbers"] if str(page).isdigit()
                ]

                # Create IndexEntry
                entry = IndexEntry(**item)
                index_entries.append(entry)

            except ValidationError as e:
                logger.warning(f"Skipping invalid index item: {item}, error: {str(e)}")
                continue

        return index_entries

    except Exception as e:
        logger.error(f"Failed to validate index data: {str(e)}")
        raise ValidationError(f"Invalid index structure: {str(e)}")


def identify_index_pages(text: str, total_pages: int) -> List[int]:
    """
    Heuristic to identify pages that likely contain the alphabetical index.

    Args:
        text: Full text content of the book
        total_pages: Total number of pages in the book

    Returns:
        List of page numbers that likely contain the index
    """
    # Heuristic: Check last 5% of pages for index-like content
    index_pages = []
    pages_to_check = max(5, int(total_pages * 0.05))  # At least 5 pages, or 5% of total
    start_page = max(0, total_pages - pages_to_check)

    # Split text by pages (assuming page markers are present)
    pages = text.split("\n\n")

    for i in range(start_page, min(total_pages, len(pages))):
        page_text = pages[i] if i < len(pages) else ""

        if _is_likely_index_page(page_text):
            index_pages.append(i + 1)  # Convert to 1-based page numbering

    return index_pages


def _is_likely_index_page(text: str) -> bool:
    """
    Heuristic to determine if a page likely contains an alphabetical index.

    Args:
        text: Extracted text from the page

    Returns:
        True if page appears to contain index content
    """
    text_lower = text.lower()

    # Common index indicators
    index_indicators = [
        "index",
        "subject index",
        "name index",
        "author index",
        "alphabetical index",
    ]

    # Check for multiple index indicators
    indicator_count = sum(
        1 for indicator in index_indicators if indicator in text_lower
    )

    # Check for alphabetical patterns (A, B, C, etc.)
    import re

    alphabetical_pattern = re.findall(r"\b[A-Z]\b", text)

    # Check for page number patterns in index format
    page_pattern = re.findall(r"\d+(?:,\s*\d+)*", text)

    # Consider it an index page if it has indicators or alphabetical/page patterns
    return (
        indicator_count >= 1 or len(alphabetical_pattern) >= 3 or len(page_pattern) >= 5
    )
