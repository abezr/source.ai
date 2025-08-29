from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .core.database import engine, Base, get_db
from .core import models, schemas, crud

app = FastAPI(
    title="Hybrid Book Index (HBI) System",
    description="API for indexing and querying book content.",
    version="0.1.0",
)

@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Simple health check endpoint to confirm the API is running.
    """
    return {"status": "ok"}

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

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# The AI Agent's task is to build out the rest of the API endpoints here.
# For example: /ingest, /query, /books/{book_id}/toc