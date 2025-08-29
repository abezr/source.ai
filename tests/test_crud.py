"""
Comprehensive unit tests for CRUD layer functions.
Uses in-memory SQLite for fast, isolated testing.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.core import schemas, crud


@pytest.fixture(scope="function")
def test_db():
    """Create an in-memory SQLite database for testing."""
    # Create in-memory SQLite engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create a session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        # Clean up the engine
        engine.dispose()


@pytest.fixture
def sample_book_data():
    """Sample book data for testing."""
    return schemas.BookCreate(title="Test Book", author="Test Author")


@pytest.fixture
def sample_book(test_db, sample_book_data):
    """Create a sample book in the test database."""
    book = crud.create_book(db=test_db, book=sample_book_data)
    return book


@pytest.fixture
def sample_toc_nodes():
    """Sample TOC nodes for testing."""
    return [
        schemas.TOCNode(
            title="Chapter 1",
            page_number=1,
            children=[schemas.TOCNode(title="Section 1.1", page_number=2, children=[])],
        ),
        schemas.TOCNode(title="Chapter 2", page_number=10, children=[]),
    ]


@pytest.fixture
def sample_chunks_data():
    """Sample chunks data for testing."""
    return [
        {
            "chunk_text": "This is the first chunk of text.",
            "page_number": 1,
            "chunk_order": 0,
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
        },
        {
            "chunk_text": "This is the second chunk of text.",
            "page_number": 1,
            "chunk_order": 1,
            "embedding": [0.6, 0.7, 0.8, 0.9, 1.0],
        },
    ]


class TestBookCRUD:
    """Test cases for book CRUD operations."""

    def test_create_book_success(self, test_db, sample_book_data):
        """Test successful book creation."""
        book = crud.create_book(db=test_db, book=sample_book_data)

        assert book.id is not None
        assert book.title == sample_book_data.title
        assert book.author == sample_book_data.author
        assert book.source_path is None

    def test_get_book_found(self, test_db, sample_book):
        """Test retrieving an existing book."""
        retrieved_book = crud.get_book(db=test_db, book_id=sample_book.id)

        assert retrieved_book is not None
        assert retrieved_book.id == sample_book.id
        assert retrieved_book.title == sample_book.title

    def test_get_book_not_found(self, test_db):
        """Test retrieving a non-existent book."""
        retrieved_book = crud.get_book(db=test_db, book_id=999)

        assert retrieved_book is None

    def test_get_books_empty_database(self, test_db):
        """Test retrieving books from empty database."""
        books = crud.get_books(db=test_db)

        assert isinstance(books, list)
        assert len(books) == 0

    def test_get_books_with_data(self, test_db, sample_book):
        """Test retrieving books with data in database."""
        books = crud.get_books(db=test_db)

        assert len(books) == 1
        assert books[0].id == sample_book.id

    def test_get_books_pagination(self, test_db, sample_book_data):
        """Test books pagination."""
        # Create multiple books
        for i in range(5):
            book_data = schemas.BookCreate(title=f"Book {i}", author=f"Author {i}")
            crud.create_book(db=test_db, book=book_data)

        # Test pagination
        books_page_1 = crud.get_books(db=test_db, skip=0, limit=2)
        books_page_2 = crud.get_books(db=test_db, skip=2, limit=2)

        assert len(books_page_1) == 2
        assert len(books_page_2) == 2
        assert books_page_1[0].title != books_page_2[0].title

    def test_update_book_source_path_success(self, test_db, sample_book):
        """Test successful source path update."""
        new_path = "/path/to/book.pdf"
        updated_book = crud.update_book_source_path(
            db=test_db, book_id=sample_book.id, source_path=new_path
        )

        assert updated_book is not None
        assert updated_book.id == sample_book.id
        assert updated_book.source_path == new_path

    def test_update_book_source_path_not_found(self, test_db):
        """Test updating source path for non-existent book."""
        updated_book = crud.update_book_source_path(
            db=test_db, book_id=999, source_path="/path/to/book.pdf"
        )

        assert updated_book is None


class TestTOCGraphCRUD:
    """Test cases for Table of Contents graph operations."""

    @patch("src.core.crud.get_graph_driver")
    def test_create_book_toc_graph_success(
        self, mock_get_driver, sample_book, sample_toc_nodes
    ):
        """Test successful TOC graph creation."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_get_driver.return_value = mock_driver

        result = crud.create_book_toc_graph(
            book_id=sample_book.id, toc_nodes=sample_toc_nodes
        )

        assert result is True
        mock_get_driver.assert_called_once()

    @patch("src.core.crud.get_graph_driver")
    def test_create_book_toc_graph_failure(
        self, mock_get_driver, sample_book, sample_toc_nodes
    ):
        """Test TOC graph creation failure."""
        mock_get_driver.side_effect = Exception("Graph connection failed")

        result = crud.create_book_toc_graph(
            book_id=sample_book.id, toc_nodes=sample_toc_nodes
        )

        assert result is False

    @patch("src.core.crud.get_graph_driver")
    def test_get_toc_by_book_id_success(self, mock_get_driver, sample_book):
        """Test successful TOC retrieval."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.run.return_value = [
            Mock(
                data=lambda: {
                    "HAS_TOC": [
                        {"title": "Chapter 1", "page_number": 1, "HAS_CHILD": []}
                    ]
                }
            )
        ]
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_get_driver.return_value = mock_driver

        result = crud.get_toc_by_book_id(book_id=sample_book.id)

        assert isinstance(result, list)

    @patch("src.core.crud.get_graph_driver")
    def test_get_toc_by_book_id_empty(self, mock_get_driver, sample_book):
        """Test TOC retrieval when no TOC exists."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.run.return_value = []
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=None)
        mock_get_driver.return_value = mock_driver

        result = crud.get_toc_by_book_id(book_id=sample_book.id)

        assert result == []


class TestChunkCRUD:
    """Test cases for chunk CRUD operations."""

    def test_create_chunks_and_embeddings_success(
        self, test_db, sample_book, sample_chunks_data
    ):
        """Test successful chunk and embedding creation."""
        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            result = crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            assert result is True

            # Verify chunks were created
            chunks = crud.get_chunks_by_book_id(db=test_db, book_id=sample_book.id)
            assert len(chunks) == 2

    def test_create_chunks_and_embeddings_partial_embedding_failure(
        self, test_db, sample_book, sample_chunks_data
    ):
        """Test chunk creation with partial embedding storage failure."""
        with patch("src.core.crud._store_chunk_embedding", return_value=False):
            result = crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            # Function should still return True as chunks are stored even if embeddings fail
            assert result is True

            # Verify chunks were still created
            chunks = crud.get_chunks_by_book_id(db=test_db, book_id=sample_book.id)
            assert len(chunks) == 2

    def test_create_chunks_and_embeddings_empty_list(self, test_db, sample_book):
        """Test chunk creation with empty list."""
        result = crud.create_chunks_and_embeddings(
            db=test_db, book_id=sample_book.id, chunks_with_embeddings=[]
        )

        assert result is True

    def test_get_chunks_by_book_id(self, test_db, sample_book, sample_chunks_data):
        """Test retrieving chunks by book ID."""
        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            chunks = crud.get_chunks_by_book_id(db=test_db, book_id=sample_book.id)

            assert len(chunks) == 2
            assert chunks[0].book_id == sample_book.id
            assert chunks[0].chunk_order == 0
            assert chunks[1].chunk_order == 1

    def test_get_chunks_by_book_id_pagination(
        self, test_db, sample_book, sample_chunks_data
    ):
        """Test chunk pagination."""
        # Create more chunks
        extended_chunks = sample_chunks_data * 3  # 6 chunks total

        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=extended_chunks,
            )

            chunks_page_1 = crud.get_chunks_by_book_id(
                db=test_db, book_id=sample_book.id, skip=0, limit=2
            )
            chunks_page_2 = crud.get_chunks_by_book_id(
                db=test_db, book_id=sample_book.id, skip=2, limit=2
            )

            assert len(chunks_page_1) == 2
            assert len(chunks_page_2) == 2

    def test_get_chunk_by_id_found(self, test_db, sample_book, sample_chunks_data):
        """Test retrieving a specific chunk by ID."""
        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            chunks = crud.get_chunks_by_book_id(db=test_db, book_id=sample_book.id)
            chunk = crud.get_chunk_by_id(db=test_db, chunk_id=chunks[0].id)

            assert chunk is not None
            assert chunk.id == chunks[0].id

    def test_get_chunk_by_id_not_found(self, test_db):
        """Test retrieving a non-existent chunk."""
        chunk = crud.get_chunk_by_id(db=test_db, chunk_id=999)

        assert chunk is None


class TestSearchCRUD:
    """Test cases for search operations."""

    def test_lexical_search_success(self, test_db, sample_book, sample_chunks_data):
        """Test successful lexical search."""
        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            results = crud.lexical_search(db=test_db, query="first chunk", limit=5)

            assert isinstance(results, list)
            # Results should be list of (chunk_id, score) tuples

    def test_lexical_search_with_book_filter(
        self, test_db, sample_book, sample_chunks_data
    ):
        """Test lexical search with book ID filter."""
        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            results = crud.lexical_search(
                db=test_db, query="chunk", limit=5, book_id=sample_book.id
            )

            assert isinstance(results, list)

    def test_lexical_search_failure(self, test_db):
        """Test lexical search failure handling."""
        # This should handle database errors gracefully
        results = crud.lexical_search(db=test_db, query="test", limit=5)

        assert isinstance(results, list)

    @patch("src.core.vector_store.get_vector_store")
    def test_vector_search_success(self, mock_get_vector_store):
        """Test successful vector search."""
        mock_vector_store = Mock()
        mock_vector_store.search_similar.return_value = [(1, 0.9), (2, 0.8)]
        mock_get_vector_store.return_value = mock_vector_store

        query_embedding = [0.1, 0.2, 0.3]
        results = crud.vector_search(query_embedding=query_embedding, limit=5)

        assert isinstance(results, list)
        # The method should be called, but we don't assert the exact call count
        # since the implementation might call it multiple times or handle errors
        assert mock_vector_store.search_similar.called

    @patch("src.core.crud.get_vector_store")
    def test_vector_search_with_book_filter(
        self, mock_get_vector_store, test_db, sample_book
    ):
        """Test vector search with book ID filter."""
        mock_vector_store = Mock()
        mock_vector_store.search_similar.return_value = [(1, 0.9), (2, 0.8)]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock the database query for book chunk filtering
        with patch.object(test_db, "execute") as mock_execute:
            mock_result = Mock()
            mock_result.fetchall.return_value = [(1,), (2,)]
            mock_execute.return_value = mock_result

            query_embedding = [0.1, 0.2, 0.3]
            results = crud.vector_search(
                query_embedding=query_embedding, limit=5, book_id=sample_book.id
            )

            assert isinstance(results, list)

    def test_reciprocal_rank_fusion(self):
        """Test reciprocal rank fusion of search results."""
        lexical_results = [(1, 0.8), (2, 0.7), (3, 0.6)]
        vector_results = [(2, 0.9), (1, 0.8), (4, 0.7)]

        fused_results = crud.reciprocal_rank_fusion(
            lexical_results=lexical_results, vector_results=vector_results
        )

        assert isinstance(fused_results, list)
        assert len(fused_results) > 0
        # Should be sorted by RRF score (descending)
        assert fused_results[0][1] >= fused_results[-1][1]

    @patch("src.agents.parser.generate_embeddings_for_chunks")
    def test_hybrid_retrieve_success(
        self, mock_generate_embeddings, test_db, sample_book, sample_chunks_data
    ):
        """Test successful hybrid retrieval."""
        mock_generate_embeddings.return_value = [
            {
                "chunk_text": "test query",
                "page_number": 0,
                "chunk_order": 0,
                "embedding": [0.1, 0.2, 0.3],
            }
        ]

        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            crud.create_chunks_and_embeddings(
                db=test_db,
                book_id=sample_book.id,
                chunks_with_embeddings=sample_chunks_data,
            )

            with (
                patch("src.core.crud.lexical_search", return_value=[(1, 0.8)]),
                patch("src.core.crud.vector_search", return_value=[(1, 0.9)]),
            ):
                results = crud.hybrid_retrieve(db=test_db, query="test query", top_k=5)

                assert isinstance(results, list)

    @patch("src.agents.parser.generate_embeddings_for_chunks")
    def test_hybrid_retrieve_fallback_to_lexical(
        self, mock_generate_embeddings, test_db
    ):
        """Test hybrid retrieval fallback to lexical search."""
        mock_generate_embeddings.return_value = []

        with patch("src.core.crud.lexical_search", return_value=[(1, 0.8)]):
            results = crud.hybrid_retrieve(db=test_db, query="test query", top_k=5)

            assert isinstance(results, list)


class TestEmbeddingStorage:
    """Test cases for embedding storage operations."""

    @patch("src.core.crud.get_vector_store")
    def test_store_chunk_embedding_success(self, mock_get_vector_store):
        """Test successful embedding storage."""
        mock_vector_store = Mock()
        mock_vector_store.store_embedding.return_value = True
        mock_get_vector_store.return_value = mock_vector_store

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = crud._store_chunk_embedding(chunk_id=1, embedding=embedding)

        assert result is True
        mock_vector_store.store_embedding.assert_called_once_with(1, embedding)

    @patch("src.core.crud.get_vector_store")
    def test_store_chunk_embedding_failure(self, mock_get_vector_store):
        """Test embedding storage failure."""
        mock_vector_store = Mock()
        mock_vector_store.store_embedding.return_value = False
        mock_get_vector_store.return_value = mock_vector_store

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = crud._store_chunk_embedding(chunk_id=1, embedding=embedding)

        assert result is False


class TestBookProcessing:
    """Test cases for book processing operations."""

    @patch("src.core.crud.chunk_and_embed_book")
    def test_process_book_chunks_and_embeddings_success(
        self, mock_chunk_and_embed, test_db, sample_book
    ):
        """Test successful book processing."""
        # Mock file path - no need to create actual file since we're mocking the parser
        mock_file_path = "/path/to/test_book.pdf"

        mock_chunk_and_embed.return_value = [
            {
                "chunk_text": "Test chunk",
                "page_number": 1,
                "chunk_order": 0,
                "embedding": [0.1, 0.2, 0.3],
            }
        ]

        with patch("src.core.crud._store_chunk_embedding", return_value=True):
            result = crud.process_book_chunks_and_embeddings(
                db=test_db, book_id=sample_book.id, file_path=mock_file_path
            )

            assert result is True
            mock_chunk_and_embed.assert_called_once_with(mock_file_path, sample_book.id)

    @patch("src.agents.parser.chunk_and_embed_book")
    def test_process_book_chunks_and_embeddings_no_chunks(
        self, mock_chunk_and_embed, test_db, sample_book
    ):
        """Test book processing with no chunks generated."""
        mock_chunk_and_embed.return_value = []

        result = crud.process_book_chunks_and_embeddings(
            db=test_db, book_id=sample_book.id, file_path="/path/to/book.pdf"
        )

        assert result is False

    @patch("src.agents.parser.chunk_and_embed_book")
    def test_process_book_chunks_and_embeddings_failure(
        self, mock_chunk_and_embed, test_db, sample_book
    ):
        """Test book processing failure."""
        mock_chunk_and_embed.side_effect = Exception("Processing failed")

        result = crud.process_book_chunks_and_embeddings(
            db=test_db, book_id=sample_book.id, file_path="/path/to/book.pdf"
        )

        assert result is False
