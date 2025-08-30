"""
Pytest configuration and fixtures for HBI system tests.
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

# Import models to ensure they are registered with SQLAlchemy
from src.core import models  # noqa: F401
from src.core.database import initialize_database


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up test database for all tests."""
    # Use a temporary database for tests
    test_db_path = tempfile.mktemp(suffix=".db")

    # Patch the database URL to use our test database
    with patch(
        "src.core.database.SQLALCHEMY_DATABASE_URL", f"sqlite:///{test_db_path}"
    ):
        # Initialize the database
        initialize_database()

        yield

        # Clean up - close any open connections first
        try:
            from src.core.database import engine

            if engine:
                engine.dispose()
        except Exception:
            pass  # Ignore cleanup errors

        # Clean up file
        try:
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
        except (OSError, PermissionError):
            # If we can't delete it, just leave it
            pass


@pytest.fixture
def mock_db_session():
    """Mock database session for individual tests."""
    mock_session = MagicMock(spec=Session)

    # Mock LLM configurations
    mock_config = MagicMock()
    mock_config.role_name = "rag_generator"
    mock_config.provider_name = "gemini"
    mock_config.model_name = "gemini-1.5-pro"
    mock_config.is_active = 1

    mock_config_parser = MagicMock()
    mock_config_parser.role_name = "parser"
    mock_config_parser.provider_name = "gemini"
    mock_config_parser.model_name = "gemini-1.5-pro"
    mock_config_parser.is_active = 1

    # Set up query chain for configurations
    mock_query = MagicMock()
    mock_query.filter_by.return_value.first.return_value = mock_config
    mock_query.all.return_value = [mock_config, mock_config_parser]

    mock_session.query.return_value = mock_query
    mock_session.query.return_value.filter_by.return_value.first.return_value = (
        mock_config
    )
    mock_session.query.return_value.all.return_value = [mock_config, mock_config_parser]

    return mock_session


@pytest.fixture
def mock_get_db(mock_db_session):
    """Mock get_db generator that yields mock session."""

    def _mock_get_db():
        yield mock_db_session

    return _mock_get_db
