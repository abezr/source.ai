from pydantic import BaseModel


class BookBase(BaseModel):
    """
    Base schema for book data with common fields.
    """
    title: str
    author: str


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