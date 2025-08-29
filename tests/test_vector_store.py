"""
Comprehensive unit tests for the vector store module.
Tests SQLite-vec operations, embedding storage, and similarity search.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock
import sqlite3

from src.core.vector_store import VectorStore, get_vector_store


class TestVectorStoreInitialization:
    """Test cases for VectorStore initialization."""

    def test_init_with_default_path(self):
        """Test initialization with default database path."""
        with patch(
            "src.core.vector_store.SQLALCHEMY_DATABASE_URL", "sqlite:///./test.db"
        ):
            with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value.__enter__.return_value = mock_conn
                store = VectorStore()
                assert store.db_path == "./test.db"

    def test_init_with_custom_path(self):
        """Test initialization with custom database path."""
        with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            store = VectorStore(db_path="/custom/path.db")
            assert store.db_path == "/custom/path.db"

    def test_init_with_sqlalchemy_url(self):
        """Test initialization with SQLAlchemy URL parsing."""
        with patch(
            "src.core.vector_store.SQLALCHEMY_DATABASE_URL", "sqlite:///./data/test.db"
        ):
            with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value.__enter__.return_value = mock_conn
                store = VectorStore()
                assert store.db_path == "./data/test.db"

    def test_init_creates_tables(self):
        """Test that initialization creates vector tables."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    VectorStore(db_path=f.name)

                    # Verify sqlite-vec extension was loaded
                    mock_conn.enable_load_extension.assert_called_with(True)
                    mock_conn.load_extension.assert_called_with("sqlite_vec")

                    # Verify table creation SQL was executed
                    assert mock_conn.execute.called
                    calls = [call[0][0] for call in mock_conn.execute.call_args_list]

                    # Check for vector table creation
                    vector_table_sql = any(
                        "CREATE VIRTUAL TABLE" in call and "vec0" in call
                        for call in calls
                    )
                    assert vector_table_sql, "Vector table creation SQL not found"

                    # Check for regular table creation
                    regular_table_sql = any(
                        "CREATE TABLE" in call and "chunk_embeddings" in call
                        for call in calls
                    )
                    assert regular_table_sql, "Regular table creation SQL not found"

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    def test_init_handles_sqlite_extension_error(self):
        """Test handling of sqlite-vec extension loading errors."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.load_extension.side_effect = sqlite3.Error(
                        "Extension not found"
                    )
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    with pytest.raises(sqlite3.Error):
                        VectorStore(db_path=f.name)

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestEmbeddingStorage:
    """Test cases for embedding storage operations."""

    def test_store_embedding_success(self):
        """Test successful embedding storage."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    embedding = [0.1, 0.2, 0.3, 0.4]

                    result = store.store_embedding(123, embedding)

                    assert result is True
                    assert mock_conn.execute.call_count >= 2  # Both tables updated
                    mock_conn.commit.assert_called()

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    def test_store_embedding_database_error(self):
        """Test handling of database errors during embedding storage."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()

                    # Make execute fail only on actual INSERT operations, not on table creation
                    def selective_side_effect(*args, **kwargs):
                        if args and len(args) > 0:
                            sql = args[0]
                            if "INSERT" in sql and "chunk_embeddings" in sql:
                                raise sqlite3.Error("Database error")
                        return MagicMock()

                    mock_conn.execute.side_effect = selective_side_effect
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    embedding = [0.1, 0.2, 0.3]

                    result = store.store_embedding(123, embedding)

                    assert result is False

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    def test_store_embedding_json_serialization(self):
        """Test that embeddings are properly JSON serialized."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

                    store.store_embedding(123, embedding)

                    # Check that JSON serialization was called
                    execute_calls = mock_conn.execute.call_args_list

                    # Look for the INSERT statement that stores the JSON embedding
                    json_found = False
                    for call in execute_calls:
                        if len(call.args) >= 2:
                            sql = call.args[0]
                            params = call.args[1]
                            if "INSERT" in sql and "chunk_embeddings" in sql:
                                # Check if any parameter is a JSON string containing our embedding
                                for param in params:
                                    if isinstance(param, str):
                                        try:
                                            parsed = json.loads(param)
                                            if isinstance(parsed, list) and len(
                                                parsed
                                            ) == len(embedding):
                                                # Check if the values match (approximately for floats)
                                                if all(
                                                    abs(a - b) < 1e-10
                                                    for a, b in zip(parsed, embedding)
                                                ):
                                                    json_found = True
                                                    break
                                        except (json.JSONDecodeError, TypeError):
                                            continue
                                if json_found:
                                    break

                    assert json_found, (
                        "JSON serialization of embedding not found in database calls"
                    )

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestSimilaritySearch:
    """Test cases for vector similarity search."""

    def test_search_similar_success(self):
        """Test successful similarity search."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchall.return_value = [(1, 0.1), (2, 0.2), (3, 0.3)]
                    mock_conn.execute.return_value = mock_cursor
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    query_embedding = [0.1, 0.2, 0.3]

                    results = store.search_similar(query_embedding, limit=5)

                    assert len(results) == 3
                    assert results == [(1, 0.1), (2, 0.2), (3, 0.3)]
                    mock_conn.load_extension.assert_called_with("sqlite_vec")

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    def test_search_similar_empty_results(self):
        """Test similarity search with no results."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchall.return_value = []
                    mock_conn.execute.return_value = mock_cursor
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    query_embedding = [0.1, 0.2, 0.3]

                    results = store.search_similar(query_embedding)

                    assert results == []

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    def test_search_similar_database_error(self):
        """Test handling of database errors during similarity search."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                call_count = 0

                def selective_error(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:  # Fail after table creation
                        raise sqlite3.Error("Search error")
                    return MagicMock()

                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.execute.side_effect = selective_error
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)
                    query_embedding = [0.1, 0.2, 0.3]

                    results = store.search_similar(query_embedding)

                    assert results == []

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestEmbeddingRetrieval:
    """Test cases for embedding retrieval operations."""

    def test_get_embedding_success(self):
        """Test successful embedding retrieval."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    embedding = [0.1, 0.2, 0.3, 0.4]
                    mock_cursor.fetchone.return_value = (json.dumps(embedding),)
                    mock_conn.execute.return_value = mock_cursor
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    result = store.get_embedding(123)

                    assert result == embedding

            finally:
                os.unlink(f.name)

    def test_get_embedding_not_found(self):
        """Test retrieval of non-existent embedding."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.return_value = None
                    mock_conn.execute.return_value = mock_cursor
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    result = store.get_embedding(999)

                    assert result is None

            finally:
                os.unlink(f.name)

    def test_get_embedding_database_error(self):
        """Test handling of database errors during embedding retrieval."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                call_count = 0

                def selective_error(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:  # Fail after table creation
                        raise sqlite3.Error("Retrieval error")
                    return MagicMock()

                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.execute.side_effect = selective_error
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    result = store.get_embedding(123)

                    assert result is None

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestEmbeddingDeletion:
    """Test cases for embedding deletion operations."""

    def test_delete_embedding_success(self):
        """Test successful embedding deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    result = store.delete_embedding(123)

                    assert result is True
                    assert mock_conn.execute.call_count >= 2  # Both tables affected
                    mock_conn.commit.assert_called()

            finally:
                os.unlink(f.name)

    def test_delete_embedding_database_error(self):
        """Test handling of database errors during embedding deletion."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                call_count = 0

                def selective_error(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:  # Fail after table creation
                        raise sqlite3.Error("Deletion error")
                    return MagicMock()

                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.execute.side_effect = selective_error
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    result = store.delete_embedding(123)

                    assert result is False

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestVectorStoreStats:
    """Test cases for vector store statistics."""

    def test_get_stats_success(self):
        """Test successful statistics retrieval."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_cursor.fetchone.return_value = (42,)
                    mock_conn.execute.return_value = mock_cursor
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    stats = store.get_stats()

                    assert stats["total_embeddings"] == 42
                    assert stats["embedding_dimension"] == 384
                    assert stats["database_path"] == f.name

            finally:
                os.unlink(f.name)

    def test_get_stats_database_error(self):
        """Test handling of database errors during statistics retrieval."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                call_count = 0

                def selective_error(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count > 2:  # Fail after table creation
                        raise sqlite3.Error("Stats error")
                    return MagicMock()

                with patch("src.core.vector_store.sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_conn.execute.side_effect = selective_error
                    mock_connect.return_value.__enter__.return_value = mock_conn

                    store = VectorStore(db_path=f.name)

                    stats = store.get_stats()

                    assert "error" in stats
                    assert "Stats error" in stats["error"]

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestGlobalVectorStore:
    """Test cases for global vector store instance management."""

    def test_get_vector_store_singleton(self):
        """Test that get_vector_store returns a singleton instance."""
        with patch("src.core.vector_store.VectorStore") as mock_store_class:
            mock_instance = MagicMock()
            mock_store_class.return_value = mock_instance

            # First call
            instance1 = get_vector_store()
            # Second call
            instance2 = get_vector_store()

            # Should be the same instance
            assert instance1 is instance2
            assert instance1 is mock_instance

            # VectorStore should only be instantiated once
            mock_store_class.assert_called_once()

    def test_get_vector_store_initialization(self):
        """Test that get_vector_store properly initializes the store."""
        with patch("src.core.vector_store.VectorStore") as mock_store_class:
            mock_instance = MagicMock()
            mock_store_class.return_value = mock_instance

            # Reset global state
            import src.core.vector_store as vs_module

            vs_module._vector_store = None

            instance = get_vector_store()

            assert instance is mock_instance
            mock_store_class.assert_called_once_with()
