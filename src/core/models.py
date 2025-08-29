from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

from .database import Base


class Book(Base):
    """
    SQLAlchemy ORM model for storing book metadata.
    """
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    author = Column(String, nullable=False)
    source_path = Column(String, nullable=True)  # Path to the source file, can be null initially