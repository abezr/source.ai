"""
Comprehensive unit tests for the worker module background job processing.
Tests the arq worker functions, configuration, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

from src.core.worker import (
    WorkerSettings,
    _detect_file_type,
    _extract_index_text_from_pages,
    process_book_file_arq,
    move_to_dlq,
    health_check,
    worker_settings,
    redis_settings,
    functions,
    worker,
)


class TestWorkerSettings:
    """Test cases for WorkerSettings configuration."""

    def test_default_settings(self):
        """Test default worker settings."""
        settings = WorkerSettings()
        assert settings.redis_url == "redis://localhost:6379"
        assert settings.max_jobs == 10
        assert settings.job_timeout == 3600
        assert settings.max_tries == 3
        assert settings.health_check_interval == 60

    def test_custom_settings(self):
        """Test custom worker settings."""
        settings = WorkerSettings(
            redis_url="redis://custom:6379",
            max_jobs=5,
            job_timeout=1800,
            max_tries=2,
            health_check_interval=30,
        )
        assert settings.redis_url == "redis://custom:6379"
        assert settings.max_jobs == 5
        assert settings.job_timeout == 1800
        assert settings.max_tries == 2
        assert settings.health_check_interval == 30

    @patch.dict(os.environ, {"REDIS_URL": "redis://env:6379"})
    def test_env_settings(self):
        """Test settings loaded from environment variables."""
        settings = WorkerSettings()
        assert settings.redis_url == "redis://env:6379"


class TestFileTypeDetection:
    """Test cases for file type detection."""

    def test_detect_pdf_file(self):
        """Test PDF file detection."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                result = _detect_file_type(f.name)
                assert result == "pdf"
            finally:
                os.unlink(f.name)

    def test_detect_djvu_file(self):
        """Test DjVu file detection."""
        with tempfile.NamedTemporaryFile(suffix=".djvu", delete=False) as f:
            try:
                result = _detect_file_type(f.name)
                assert result == "djvu"
            finally:
                os.unlink(f.name)

    def test_detect_uppercase_extension(self):
        """Test case-insensitive file extension detection."""
        with tempfile.NamedTemporaryFile(suffix=".PDF", delete=False) as f:
            try:
                result = _detect_file_type(f.name)
                assert result == "pdf"
            finally:
                os.unlink(f.name)

    def test_detect_nonexistent_file(self):
        """Test fallback behavior for nonexistent files."""
        result = _detect_file_type("/nonexistent/file.pdf")
        assert result == "pdf"  # Should fallback to PDF

    def test_detect_no_extension(self):
        """Test file without extension."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            try:
                result = _detect_file_type(f.name)
                assert result == ""  # Empty extension
            finally:
                os.unlink(f.name)


class TestIndexTextExtraction:
    """Test cases for index text extraction from pages."""

    def test_extract_index_text_single_page(self):
        """Test extracting text from a single index page."""
        full_text = (
            "Page 1 content\n\nPage 2 content\n\nPage 3 content\n\nIndex: Apple, Banana"
        )
        index_pages = [4]  # Index is on page 4 (1-indexed)

        result = _extract_index_text_from_pages(full_text, index_pages)
        assert "Index: Apple, Banana" in result

    def test_extract_index_text_multiple_pages(self):
        """Test extracting text from multiple index pages."""
        full_text = (
            "Page 1\n\nPage 2\n\nPage 3: Index part 1\n\nPage 4: Index part 2\n\nPage 5"
        )
        index_pages = [3, 4]

        result = _extract_index_text_from_pages(full_text, index_pages)
        assert "Index part 1" in result
        assert "Index part 2" in result
        assert "\n\n" in result  # Should join with double newlines

    def test_extract_index_text_empty_pages(self):
        """Test extracting from empty page list."""
        full_text = "Some content"
        index_pages = []

        result = _extract_index_text_from_pages(full_text, index_pages)
        assert result == ""

    def test_extract_index_text_out_of_bounds(self):
        """Test extracting from pages beyond text length."""
        full_text = "Page 1\n\nPage 2"
        index_pages = [5]  # Page beyond available content

        result = _extract_index_text_from_pages(full_text, index_pages)
        assert result == ""

    def test_extract_index_text_empty_content(self):
        """Test extracting from pages with empty content."""
        full_text = "Page 1\n\n\n\nPage 2"  # Empty page
        index_pages = [2]

        result = _extract_index_text_from_pages(full_text, index_pages)
        assert result == ""  # Empty pages should be skipped


class TestHealthCheck:
    """Test cases for health check function."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        result = await health_check()
        assert result == {"status": "healthy", "worker": "arq"}
        assert result["status"] == "healthy"
        assert result["worker"] == "arq"


class TestMoveToDLQ:
    """Test cases for Dead Letter Queue functionality."""

    @pytest.mark.asyncio
    async def test_move_to_dlq_success(self):
        """Test successful move to DLQ."""
        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis, "job_try": 3, "timestamp": "2024-01-01T00:00:00Z"}

        await move_to_dlq(ctx, 123, "test_key", "Test error")

        # Verify Redis LPUSH was called
        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args
        assert call_args[0][0] == "dlq:book_processing"

        # Verify the DLQ entry structure
        dlq_entry_str = call_args[0][1]
        assert "book_id" in dlq_entry_str
        assert "object_key" in dlq_entry_str
        assert "error_message" in dlq_entry_str
        assert "123" in dlq_entry_str  # book_id
        assert "test_key" in dlq_entry_str
        assert "Test error" in dlq_entry_str

    @pytest.mark.asyncio
    async def test_move_to_dlq_minimal_context(self):
        """Test DLQ move with minimal context."""
        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis}  # Minimal context

        await move_to_dlq(ctx, 456, "minimal_key", "Minimal error")

        mock_redis.lpush.assert_called_once()


class TestProcessBookFileArq:
    """Test cases for the main book processing function."""

    @pytest.mark.asyncio
    async def test_process_book_file_unsupported_format(self):
        """Test processing with unsupported file format."""
        ctx = {"job_try": 1, "max_tries": 3}

        with pytest.raises(ValueError, match="Unsupported file type"):
            with patch("src.core.worker._detect_file_type", return_value="txt"):
                await process_book_file_arq(ctx, 123, "test.txt")

    @pytest.mark.asyncio
    async def test_process_book_file_final_retry_dlq(self):
        """Test that final retry moves job to DLQ."""
        ctx = {"job_try": 3, "max_tries": 3}

        with patch("src.core.worker._detect_file_type", return_value="txt"):
            with patch("src.core.worker.move_to_dlq") as mock_move_to_dlq:
                with pytest.raises(ValueError):
                    await process_book_file_arq(ctx, 123, "test.txt")

                # Should attempt to move to DLQ on final retry
                mock_move_to_dlq.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_book_file_non_final_retry(self):
        """Test that non-final retry doesn't move to DLQ."""
        ctx = {"job_try": 2, "max_tries": 3}

        with patch("src.core.worker._detect_file_type", return_value="txt"):
            with patch("src.core.worker.move_to_dlq") as mock_move_to_dlq:
                with pytest.raises(ValueError):
                    await process_book_file_arq(ctx, 123, "test.txt")

                # Should NOT move to DLQ on non-final retry
                mock_move_to_dlq.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_book_file_pdf_success_path(self):
        """Test successful PDF processing path."""
        ctx = {"job_try": 1, "max_tries": 3}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                with (
                    patch("src.core.worker._detect_file_type", return_value="pdf"),
                    patch("src.agents.parser.parse_toc_from_pdf", return_value=[]),
                    patch(
                        "src.agents.parser._extract_toc_text_from_pdf", return_value=""
                    ),
                    patch(
                        "src.agents.parser._extract_full_text_from_pdf",
                        return_value="Test content",
                    ),
                    patch("src.agents.parser.identify_index_pages", return_value=[]),
                    patch(
                        "src.core.crud.process_book_chunks_and_embeddings",
                        return_value=True,
                    ),
                    patch("src.core.worker.SessionLocal") as mock_session,
                    patch(
                        "os.path.exists", return_value=True
                    ),  # Mock file existence check
                ):
                    mock_db = Mock()
                    mock_session.return_value = mock_db

                    result = await process_book_file_arq(ctx, 123, f.name)

                    assert "Successfully processed book 123" in result
                    mock_db.close.assert_called_once()

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    @pytest.mark.asyncio
    async def test_process_book_file_djvu_success_path(self):
        """Test successful DjVu processing path."""
        ctx = {"job_try": 1, "max_tries": 3}

        with tempfile.NamedTemporaryFile(suffix=".djvu", delete=False) as f:
            try:
                with (
                    patch("src.core.worker._detect_file_type", return_value="djvu"),
                    patch(
                        "src.agents.parser.extract_text_from_djvu",
                        return_value="Test DjVu content",
                    ),
                    patch("src.agents.parser.identify_index_pages", return_value=[]),
                    patch(
                        "src.core.crud.process_book_chunks_and_embeddings",
                        return_value=True,
                    ),
                    patch("src.core.worker.SessionLocal") as mock_session,
                ):
                    mock_db = Mock()
                    mock_session.return_value = mock_db

                    # Mock the subprocess.run call to avoid djvutxt dependency
                    with patch("src.agents.parser.subprocess.run") as mock_subprocess:
                        mock_subprocess.return_value = Mock(
                            stdout="Test DjVu content", stderr="", returncode=0
                        )
                        result = await process_book_file_arq(ctx, 456, f.name)

                        assert "Successfully processed book 456" in result
                        mock_db.close.assert_called_once()

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    @pytest.mark.asyncio
    async def test_process_book_file_empty_text_handling(self):
        """Test handling of empty text content."""
        ctx = {"job_try": 1, "max_tries": 3}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                with (
                    patch("src.core.worker._detect_file_type", return_value="pdf"),
                    patch("src.agents.parser.parse_toc_from_pdf", return_value=[]),
                    patch(
                        "src.agents.parser._extract_toc_text_from_pdf", return_value=""
                    ),
                    patch(
                        "src.agents.parser._extract_full_text_from_pdf",
                        return_value="   \n\t  ",
                    ),  # Empty/whitespace only
                    patch("src.agents.parser.identify_index_pages", return_value=[]),
                    patch(
                        "src.core.crud.process_book_chunks_and_embeddings",
                        return_value=True,
                    ),
                    patch("src.core.worker.SessionLocal") as mock_session,
                    patch(
                        "os.path.exists", return_value=True
                    ),  # Mock file existence check
                ):
                    mock_db = Mock()
                    mock_session.return_value = mock_db

                    result = await process_book_file_arq(ctx, 789, f.name)

                    assert "Successfully processed book 789" in result

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows

    @pytest.mark.asyncio
    async def test_process_book_file_chunking_failure(self):
        """Test handling of chunking/embedding failure."""
        ctx = {"job_try": 1, "max_tries": 3}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            try:
                with (
                    patch("src.core.worker._detect_file_type", return_value="pdf"),
                    patch("src.agents.parser.parse_toc_from_pdf", return_value=[]),
                    patch(
                        "src.agents.parser._extract_toc_text_from_pdf", return_value=""
                    ),
                    patch(
                        "src.agents.parser._extract_full_text_from_pdf",
                        return_value="Test content",
                    ),
                    patch("src.agents.parser.identify_index_pages", return_value=[]),
                    patch(
                        "src.core.crud.process_book_chunks_and_embeddings",
                        return_value=False,
                    ),  # Failure
                    patch("src.core.worker.SessionLocal") as mock_session,
                    patch(
                        "os.path.exists", return_value=True
                    ),  # Mock file existence check
                ):
                    mock_db = Mock()
                    mock_session.return_value = mock_db

                    with pytest.raises(
                        RuntimeError, match="Failed to process chunks and embeddings"
                    ):
                        await process_book_file_arq(ctx, 999, f.name)

            finally:
                try:
                    os.unlink(f.name)
                except (OSError, PermissionError):
                    pass  # File may be locked on Windows


class TestWorkerConfiguration:
    """Test cases for worker configuration and setup."""

    def test_worker_settings_instance(self):
        """Test that worker_settings is properly instantiated."""
        assert isinstance(worker_settings, WorkerSettings)
        assert worker_settings.redis_url == "redis://localhost:6379"

    def test_redis_settings_creation(self):
        """Test Redis settings creation."""
        from arq.connections import RedisSettings

        assert isinstance(redis_settings, RedisSettings)

    def test_functions_list(self):
        """Test that functions list contains expected functions."""
        assert len(functions) == 2
        assert process_book_file_arq in functions
        assert health_check in functions

    def test_worker_instance(self):
        """Test that worker instance is properly configured."""
        from arq.worker import Worker

        assert isinstance(worker, Worker)
        # Worker.functions returns a dict mapping function names to function objects
        # So we check that our functions are present in the worker's function registry
        assert len(worker.functions) == len(functions)
        for func in functions:
            assert func.__name__ in worker.functions
