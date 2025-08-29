"""
Configuration store for dynamic RAG pipeline parameters.

This module provides a thread-safe, in-memory configuration store that allows
dynamic tuning of RAG pipeline parameters without requiring code deployment.
The configuration persists for the application lifetime.
"""

import logging
import threading
from typing import Optional
from .schemas import RAGConfig

# Global configuration store with thread safety
_config_store: Optional[RAGConfig] = None
_config_lock = threading.Lock()

# Default configuration values
DEFAULT_CONFIG = RAGConfig(
    retrieval_top_k=10,
    min_chunks=2,
    confidence_threshold=0.7,
    relevance_threshold=0.5,
    max_context_length=4000,
    temperature=0.1,
    enable_fallback=True
)


def get_rag_config() -> RAGConfig:
    """
    Get the current RAG configuration.

    Returns the current configuration if it exists, otherwise returns
    the default configuration and initializes the store.

    Returns:
        RAGConfig: Current RAG configuration
    """
    global _config_store

    with _config_lock:
        if _config_store is None:
            logging.info("Initializing RAG configuration with default values")
            _config_store = DEFAULT_CONFIG.copy()
        return _config_store


def update_rag_config(new_config: RAGConfig) -> RAGConfig:
    """
    Update the RAG configuration with new values.

    This function validates the new configuration and updates the global store.
    All parameters are validated to ensure they are within reasonable bounds.

    Args:
        new_config: New RAG configuration to apply

    Returns:
        RAGConfig: Updated configuration

    Raises:
        ValueError: If any configuration parameter is invalid
    """
    global _config_store

    # Validate configuration parameters
    _validate_config(new_config)

    with _config_lock:
        _config_store = new_config.copy()
        logging.info(f"RAG configuration updated: {new_config.dict()}")
        return _config_store


def reset_rag_config() -> RAGConfig:
    """
    Reset the RAG configuration to default values.

    Returns:
        RAGConfig: Default configuration
    """
    global _config_store

    with _config_lock:
        _config_store = DEFAULT_CONFIG.copy()
        logging.info("RAG configuration reset to default values")
        return _config_store


def _validate_config(config: RAGConfig) -> None:
    """
    Validate RAG configuration parameters.

    Args:
        config: Configuration to validate

    Raises:
        ValueError: If any parameter is invalid
    """
    if config.retrieval_top_k < 1:
        raise ValueError("retrieval_top_k must be at least 1")

    if config.min_chunks < 1:
        raise ValueError("min_chunks must be at least 1")

    if not 0.0 <= config.confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.0 and 1.0")

    if not 0.0 <= config.relevance_threshold <= 1.0:
        raise ValueError("relevance_threshold must be between 0.0 and 1.0")

    if config.max_context_length < 100:
        raise ValueError("max_context_length must be at least 100")

    if not 0.0 <= config.temperature <= 2.0:
        raise ValueError("temperature must be between 0.0 and 2.0")

    if config.min_chunks > config.retrieval_top_k:
        raise ValueError("min_chunks cannot be greater than retrieval_top_k")