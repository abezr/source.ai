from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class Book(Base):
    """
    SQLAlchemy ORM model for storing book metadata.
    """

    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    author = Column(String, nullable=False)
    source_path = Column(
        String, nullable=True
    )  # Path to the source file, can be null initially

    # Relationship to chunks
    chunks = relationship("Chunk", back_populates="book")


class Chunk(Base):
    """
    SQLAlchemy ORM model for storing text chunks and their metadata.
    Used for both lexical search (FTS5) and vector search (sqlite-vec).
    """

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)  # The actual text content of the chunk
    page_number = Column(Integer, nullable=False)  # Page number where chunk originates
    chunk_order = Column(
        Integer, nullable=False, index=True
    )  # Order within the book for sequential reading

    # Relationship to book
    book = relationship("Book", back_populates="chunks")


class LLMConfiguration(Base):
    """
    SQLAlchemy ORM model for storing LLM provider configurations.
    Maps roles to specific providers and models for flexible routing.
    """

    __tablename__ = "llm_configurations"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(
        String, nullable=False, index=True
    )  # e.g., "rag_generator", "parser"
    provider_name = Column(String, nullable=False)  # e.g., "gemini", "ollama"
    model_name = Column(String, nullable=False)  # e.g., "gemini-2.5-pro", "llama2"
    is_active = Column(
        Integer, default=1, nullable=False
    )  # 1 for active, 0 for inactive
