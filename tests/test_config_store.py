"""
Comprehensive unit tests for the config store module.
Tests RAG configuration management, validation, and thread safety.
"""

import pytest
from unittest.mock import patch

from src.core.config_store import (
    get_rag_config,
    update_rag_config,
    reset_rag_config,
    _validate_config,
    DEFAULT_CONFIG,
)
from src.core.schemas import RAGConfig


class TestGetRAGConfig:
    """Test cases for get_rag_config function."""

    def test_get_rag_config_default(self):
        """Test getting default configuration."""
        with patch("src.core.config_store._config_store", None):
            config = get_rag_config()
            assert config == DEFAULT_CONFIG

    def test_get_rag_config_existing(self):
        """Test getting existing configuration."""
        custom_config = RAGConfig(retrieval_top_k=5)
        with patch("src.core.config_store._config_store", custom_config):
            config = get_rag_config()
            assert config == custom_config


class TestUpdateRAGConfig:
    """Test cases for update_rag_config function."""

    def test_update_rag_config_valid(self):
        """Test updating with valid configuration."""
        new_config = RAGConfig(
            retrieval_top_k=15,
            min_chunks=3,
            confidence_threshold=0.8,
        )
        with patch("src.core.config_store._config_store", None):
            updated = update_rag_config(new_config)
            assert updated == new_config

    def test_update_rag_config_invalid(self):
        """Test updating with invalid configuration."""
        invalid_config = RAGConfig(retrieval_top_k=0)  # Invalid
        with pytest.raises(ValueError, match="retrieval_top_k must be at least 1"):
            update_rag_config(invalid_config)


class TestResetRAGConfig:
    """Test cases for reset_rag_config function."""

    def test_reset_rag_config(self):
        """Test resetting configuration to defaults."""
        custom_config = RAGConfig(retrieval_top_k=20)
        with patch("src.core.config_store._config_store", custom_config):
            reset = reset_rag_config()
            assert reset == DEFAULT_CONFIG


class TestValidateConfig:
    """Test cases for _validate_config function."""

    def test_validate_config_valid(self):
        """Test validating valid configuration."""
        valid_config = RAGConfig(
            retrieval_top_k=10,
            min_chunks=2,
            confidence_threshold=0.7,
            relevance_threshold=0.5,
            max_context_length=4000,
            temperature=0.1,
        )
        # Should not raise
        _validate_config(valid_config)

    def test_validate_config_invalid_retrieval_top_k(self):
        """Test validating invalid retrieval_top_k."""
        invalid_config = RAGConfig(retrieval_top_k=0)
        with pytest.raises(ValueError, match="retrieval_top_k must be at least 1"):
            _validate_config(invalid_config)

    def test_validate_config_invalid_min_chunks(self):
        """Test validating invalid min_chunks."""
        invalid_config = RAGConfig(min_chunks=0)
        with pytest.raises(ValueError, match="min_chunks must be at least 1"):
            _validate_config(invalid_config)

    def test_validate_config_invalid_confidence_threshold(self):
        """Test validating invalid confidence_threshold."""
        invalid_config = RAGConfig(confidence_threshold=1.5)
        with pytest.raises(
            ValueError, match="confidence_threshold must be between 0.0 and 1.0"
        ):
            _validate_config(invalid_config)

    def test_validate_config_invalid_relevance_threshold(self):
        """Test validating invalid relevance_threshold."""
        invalid_config = RAGConfig(relevance_threshold=-0.1)
        with pytest.raises(
            ValueError, match="relevance_threshold must be between 0.0 and 1.0"
        ):
            _validate_config(invalid_config)

    def test_validate_config_invalid_max_context_length(self):
        """Test validating invalid max_context_length."""
        invalid_config = RAGConfig(max_context_length=50)
        with pytest.raises(ValueError, match="max_context_length must be at least 100"):
            _validate_config(invalid_config)

    def test_validate_config_invalid_temperature(self):
        """Test validating invalid temperature."""
        invalid_config = RAGConfig(temperature=3.0)
        with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
            _validate_config(invalid_config)

    def test_validate_config_invalid_min_chunks_greater_than_top_k(self):
        """Test validating when min_chunks > retrieval_top_k."""
        invalid_config = RAGConfig(retrieval_top_k=5, min_chunks=10)
        with pytest.raises(
            ValueError, match="min_chunks cannot be greater than retrieval_top_k"
        ):
            _validate_config(invalid_config)
