from pydantic import BaseModel, Field
from typing import List, Optional


class BookBase(BaseModel):
    """
    Base schema for book data with common fields.
    """

    title: str = Field(..., min_length=1, description="Book title")
    author: str = Field(..., min_length=1, description="Book author")


class BookCreate(BookBase):
    """
    Schema for creating a new book.
    Inherits title and author from BookBase.
    """

    pass


class Book(BookBase):
    """
    Schema for reading book data, including the database ID.
    """

    id: int
    source_path: str | None = None

    class Config:
        orm_mode = True


class TOCNode(BaseModel):
    """
    Schema for Table of Contents node with hierarchical structure.
    """

    title: str
    page_number: int
    children: List["TOCNode"] = []

    class Config:
        orm_mode = True


class ChunkBase(BaseModel):
    """
    Base schema for chunk data with common fields.
    """

    book_id: int
    chunk_text: str
    page_number: int
    chunk_order: int


class ChunkCreate(ChunkBase):
    """
    Schema for creating a new chunk.
    Inherits all fields from ChunkBase.
    """

    pass


class Chunk(ChunkBase):
    """
    Schema for reading chunk data, including the database ID.
    """

    id: int

    class Config:
        orm_mode = True


class Claim(BaseModel):
    """
    Schema for a single claim made in an answer with its source citation.
    """

    text: str
    source_chunk_id: int
    page_number: int

    class Config:
        orm_mode = True


class Answer(BaseModel):
    """
    Schema for a structured answer with claims, confidence score, and summary.
    """

    answer_summary: str
    claims: List[Claim]
    confidence_score: float

    class Config:
        orm_mode = True


class QueryRequest(BaseModel):
    """
    Schema for query endpoint requests.
    """

    query: str
    book_id: Optional[int] = None  # Optional: filter to specific book
    top_k: Optional[int] = 10  # Number of chunks to retrieve

    class Config:
        orm_mode = True


class QueryResponse(BaseModel):
    """
    Schema for query endpoint responses.
    Either contains a structured Answer or a fallback message.
    """

    answer: Optional[Answer] = None
    fallback_message: Optional[str] = None

    class Config:
        orm_mode = True


class IndexEntry(BaseModel):
    """
    Schema for alphabetical index entries with term and page references.
    """

    term: str
    page_numbers: List[int]

    class Config:
        orm_mode = True


class RAGConfig(BaseModel):
    """
    Schema for RAG pipeline configuration parameters.
    These parameters control the behavior and quality thresholds of the RAG system.
    """

    retrieval_top_k: int = 10  # Number of chunks to retrieve in hybrid search
    min_chunks: int = 2  # Minimum number of chunks required for retrieval gate
    confidence_threshold: float = 0.7  # Minimum confidence score for generation gate
    relevance_threshold: float = 0.5  # Minimum relevance score for retrieved chunks
    max_context_length: int = 4000  # Maximum context length for LLM input
    temperature: float = 0.1  # LLM temperature for answer generation
    enable_fallback: bool = True  # Whether to provide fallback messages when gates fail

    class Config:
        orm_mode = True
