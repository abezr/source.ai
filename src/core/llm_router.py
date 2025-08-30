"""
LLM Router service for HBI system.
Provides configuration-driven routing to different LLM providers.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from .database import get_db
from .models import LLMConfiguration
from .llm_client import LLMProvider, GeminiProvider, OllamaProvider


class LLMRouter:
    """
    Router service for managing LLM provider selection based on configuration.
    """

    def __init__(self):
        """Initialize the router."""
        self._provider_cache = {}  # Cache for instantiated providers

    def get_provider_for_role(self, role_name: str) -> LLMProvider:
        """
        Get the appropriate LLM provider for a given role.

        Args:
            role_name: The role name (e.g., "rag_generator", "parser")

        Returns:
            LLMProvider instance configured for the role

        Raises:
            Exception: If no configuration found or provider unavailable
        """
        # Check cache first
        if role_name in self._provider_cache:
            provider = self._provider_cache[role_name]
            if provider.validate_connection():
                return provider
            else:
                # Remove invalid provider from cache
                del self._provider_cache[role_name]

        # Get configuration from database
        db = next(get_db())
        config = self._get_active_configuration(db, role_name)

        if not config:
            raise Exception(f"No active configuration found for role: {role_name}")

        # Instantiate provider
        provider = self._create_provider(config)

        # Validate connection
        if not provider.validate_connection():
            # Try fallback to default Gemini
            logging.warning(
                f"Provider for role {role_name} is unavailable, trying fallback"
            )
            fallback_config = self._get_fallback_configuration(db, role_name)
            if fallback_config:
                provider = self._create_provider(fallback_config)
                if not provider.validate_connection():
                    raise Exception(
                        f"Both primary and fallback providers unavailable for role: {role_name}"
                    )
            else:
                raise Exception(
                    f"Provider unavailable and no fallback configured for role: {role_name}"
                )

        # Cache the working provider
        self._provider_cache[role_name] = provider
        return provider

    def _get_active_configuration(
        self, db: Session, role_name: str
    ) -> Optional[LLMConfiguration]:
        """
        Get the active configuration for a role.

        Args:
            db: Database session
            role_name: The role name

        Returns:
            Active LLMConfiguration or None
        """
        return (
            db.query(LLMConfiguration)
            .filter_by(role_name=role_name, is_active=1)
            .first()
        )

    def _get_fallback_configuration(
        self, db: Session, role_name: str
    ) -> Optional[LLMConfiguration]:
        """
        Get a fallback configuration when primary is unavailable.

        Args:
            db: Database session
            role_name: The role name

        Returns:
            Fallback LLMConfiguration or None
        """
        # For now, fallback to any active Gemini configuration
        return (
            db.query(LLMConfiguration)
            .filter_by(provider_name="gemini", is_active=1)
            .first()
        )

    def _create_provider(self, config: LLMConfiguration) -> LLMProvider:
        """
        Create a provider instance based on configuration.

        Args:
            config: LLM configuration

        Returns:
            LLMProvider instance

        Raises:
            Exception: If provider type is unknown
        """
        if config.provider_name == "gemini":
            return GeminiProvider(model_name=config.model_name)
        elif config.provider_name == "ollama":
            return OllamaProvider(model_name=config.model_name)
        else:
            raise Exception(f"Unknown provider type: {config.provider_name}")

    def clear_cache(self):
        """
        Clear the provider cache. Useful for configuration changes.
        """
        self._provider_cache.clear()

    def get_available_providers(self) -> list:
        """
        Get list of all configured providers with their status.

        Returns:
            List of provider status dictionaries
        """
        db = next(get_db())
        configs = db.query(LLMConfiguration).all()

        providers = []
        for config in configs:
            provider = self._create_provider(config)
            status = {
                "role_name": config.role_name,
                "provider_name": config.provider_name,
                "model_name": config.model_name,
                "is_active": bool(config.is_active),
                "connection_status": provider.validate_connection(),
            }
            providers.append(status)

        return providers


# Global router instance
llm_router = LLMRouter()


def get_llm_router():
    """
    Dependency injection function for FastAPI endpoints.
    Provides an LLMRouter instance.

    Returns:
        LLMRouter: The LLM router instance
    """
    return llm_router
