from sqlalchemy.orm import Session
from . import models, schemas


def create_book(db: Session, book: schemas.BookCreate) -> models.Book:
    """
    Create a new book record in the database.

    Args:
        db: Database session
        book: Book creation data

    Returns:
        The created book instance
    """
    db_book = models.Book(
        title=book.title,
        author=book.author,
        source_path=None  # Initially None, can be set later
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


def get_book(db: Session, book_id: int) -> models.Book | None:
    """
    Retrieve a book by its ID.

    Args:
        db: Database session
        book_id: The book ID to retrieve

    Returns:
        The book instance if found, None otherwise
    """
    return db.query(models.Book).filter(models.Book.id == book_id).first()


def get_books(db: Session, skip: int = 0, limit: int = 100) -> list[models.Book]:
    """
    Retrieve a list of books with pagination.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of book instances
    """
    return db.query(models.Book).offset(skip).limit(limit).all()