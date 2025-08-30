"""
Unit tests for the LLM Router service and provider implementations.
Tests configuration-driven routing, provider selection, and fallback mechanisms.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from src.core.llm_router import LLMRouter, get_llm_router
from src.core.llm_client import GeminiProvider, OllamaProvider


class TestLLMRouterInitialization:
    """Test cases for LLMRouter initialization."""

    def test_router_initialization(self):
        """Test router initializes correctly."""
        router = LLMRouter()
        assert router._provider_cache == {}
        assert hasattr(router, "get_provider_for_role")
        assert hasattr(router, "clear_cache")


class TestProviderSelection:
    """Test cases for provider selection logic."""

    def test_get_provider_for_role_gemini(self):
        """Test getting Gemini provider for a role."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            # Mock configuration
            mock_config = MagicMock()
            mock_config.provider_name = "gemini"
            mock_config.model_name = "gemini-1.5-pro"
            mock_db.query.return_value.filter_by.return_value.first.return_value = (
                mock_config
            )

            # Mock provider
            with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                mock_provider = MagicMock()
                mock_provider.validate_connection.return_value = True
                mock_gemini.return_value = mock_provider

                result = router.get_provider_for_role("rag_generator")

                assert result == mock_provider
                mock_gemini.assert_called_once_with(model_name="gemini-1.5-pro")

    def test_get_provider_for_role_ollama(self):
        """Test getting Ollama provider for a role."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            # Mock configuration
            mock_config = MagicMock()
            mock_config.provider_name = "ollama"
            mock_config.model_name = "llama2"
            mock_db.query.return_value.filter_by.return_value.first.return_value = (
                mock_config
            )

            # Mock provider
            with patch("src.core.llm_router.OllamaProvider") as mock_ollama:
                mock_provider = MagicMock()
                mock_provider.validate_connection.return_value = True
                mock_ollama.return_value = mock_provider

                result = router.get_provider_for_role("rag_generator")

                assert result == mock_provider
                mock_ollama.assert_called_once_with(model_name="llama2")

    def test_get_provider_for_role_no_config(self):
        """Test error when no configuration exists for role."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            mock_db.query.return_value.filter_by.return_value.first.return_value = None

            with pytest.raises(
                Exception, match="No active configuration found for role"
            ):
                router.get_provider_for_role("nonexistent_role")

    def test_get_provider_for_role_connection_failure_with_fallback(self):
        """Test fallback when primary provider fails."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            # Mock primary config (fails)
            mock_primary_config = MagicMock()
            mock_primary_config.provider_name = "ollama"
            mock_primary_config.model_name = "llama2"

            # Mock fallback config (succeeds)
            mock_fallback_config = MagicMock()
            mock_fallback_config.provider_name = "gemini"
            mock_fallback_config.model_name = "gemini-1.5-pro"

            mock_db.query.return_value.filter_by.return_value.first.side_effect = [
                mock_primary_config,  # First call for primary
                mock_fallback_config,  # Second call for fallback
            ]

            with patch("src.core.llm_router.OllamaProvider") as mock_ollama:
                with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                    # Primary provider fails
                    mock_primary_provider = MagicMock()
                    mock_primary_provider.validate_connection.return_value = False
                    mock_ollama.return_value = mock_primary_provider

                    # Fallback provider succeeds
                    mock_fallback_provider = MagicMock()
                    mock_fallback_provider.validate_connection.return_value = True
                    mock_gemini.return_value = mock_fallback_provider

                    result = router.get_provider_for_role("rag_generator")

                    assert result == mock_fallback_provider
                    mock_ollama.assert_called_once_with(model_name="llama2")
                    mock_gemini.assert_called_once_with(model_name="gemini-1.5-pro")

    def test_get_provider_for_role_both_fail(self):
        """Test error when both primary and fallback providers fail."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            # Mock configs
            mock_primary_config = MagicMock()
            mock_primary_config.provider_name = "ollama"
            mock_primary_config.model_name = "llama2"

            mock_fallback_config = MagicMock()
            mock_fallback_config.provider_name = "gemini"
            mock_fallback_config.model_name = "gemini-1.5-pro"

            mock_db.query.return_value.filter_by.return_value.first.side_effect = [
                mock_primary_config,
                mock_fallback_config,
            ]

            with patch("src.core.llm_router.OllamaProvider") as mock_ollama:
                with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                    # Both providers fail
                    mock_primary_provider = MagicMock()
                    mock_primary_provider.validate_connection.return_value = False
                    mock_ollama.return_value = mock_primary_provider

                    mock_fallback_provider = MagicMock()
                    mock_fallback_provider.validate_connection.return_value = False
                    mock_gemini.return_value = mock_fallback_provider

                    with pytest.raises(
                        Exception,
                        match="Both primary and fallback providers unavailable",
                    ):
                        router.get_provider_for_role("rag_generator")


class TestProviderCaching:
    """Test cases for provider caching."""

    def test_provider_caching(self):
        """Test that providers are cached correctly."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            mock_config = MagicMock()
            mock_config.provider_name = "gemini"
            mock_config.model_name = "gemini-1.5-pro"
            mock_db.query.return_value.filter_by.return_value.first.return_value = (
                mock_config
            )

            with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                mock_provider = MagicMock()
                mock_provider.validate_connection.return_value = True
                mock_gemini.return_value = mock_provider

                # First call
                result1 = router.get_provider_for_role("rag_generator")
                # Second call should use cache
                result2 = router.get_provider_for_role("rag_generator")

                assert result1 == result2
                assert result1 == mock_provider
                # Should only instantiate once
                mock_gemini.assert_called_once()

    def test_cache_invalidation_on_failure(self):
        """Test cache invalidation when provider fails."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            mock_config = MagicMock()
            mock_config.provider_name = "gemini"
            mock_config.model_name = "gemini-1.5-pro"
            mock_db.query.return_value.filter_by.return_value.first.return_value = (
                mock_config
            )

            with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                # First provider fails
                mock_provider1 = MagicMock()
                mock_provider1.validate_connection.return_value = False
                # Second provider succeeds
                mock_provider2 = MagicMock()
                mock_provider2.validate_connection.return_value = True

                mock_gemini.side_effect = [mock_provider1, mock_provider2]

                # First call fails and creates new provider
                result = router.get_provider_for_role("rag_generator")

                assert result == mock_provider2
                # Should have created two providers (first failed, second succeeded)
                assert mock_gemini.call_count == 2


class TestAvailableProviders:
    """Test cases for getting available providers."""

    def test_get_available_providers(self):
        """Test getting list of all configured providers."""
        router = LLMRouter()

        with patch("src.core.llm_router.next") as mock_next:
            mock_db = MagicMock(spec=Session)
            mock_next.return_value = mock_db

            # Mock configurations
            mock_configs = [
                MagicMock(
                    role_name="rag_generator",
                    provider_name="gemini",
                    model_name="gemini-1.5-pro",
                    is_active=1,
                ),
                MagicMock(
                    role_name="parser",
                    provider_name="ollama",
                    model_name="llama2",
                    is_active=0,
                ),
            ]
            mock_db.query.return_value.all.return_value = mock_configs

            with patch("src.core.llm_router.GeminiProvider") as mock_gemini:
                with patch("src.core.llm_router.OllamaProvider") as mock_ollama:
                    mock_gemini_provider = MagicMock()
                    mock_gemini_provider.validate_connection.return_value = True
                    mock_gemini.return_value = mock_gemini_provider

                    mock_ollama_provider = MagicMock()
                    mock_ollama_provider.validate_connection.return_value = False
                    mock_ollama.return_value = mock_ollama_provider

                    result = router.get_available_providers()

                    assert len(result) == 2
                    assert result[0]["role_name"] == "rag_generator"
                    assert result[0]["connection_status"]
                    assert result[1]["role_name"] == "parser"
                    assert not result[1]["connection_status"]


class TestGeminiProvider:
    """Test cases for GeminiProvider implementation."""

    def test_gemini_provider_initialization(self):
        """Test Gemini provider initialization."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel"):
                    provider = GeminiProvider()
                    assert provider.api_key == "test_key"
                    assert provider.model_name == "gemini-1.5-pro"

    def test_gemini_generate_structured_json(self):
        """Test Gemini provider structured JSON generation."""
        provider = GeminiProvider()
        provider.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"result": "test"}'
        provider.client.generate_content.return_value = mock_response

        result = provider.generate_structured_json("test prompt")

        assert result == {"result": "test"}
        provider.client.generate_content.assert_called_once()

    def test_gemini_generate_grounded_answer(self):
        """Test Gemini provider grounded answer generation."""
        provider = GeminiProvider()
        provider.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = (
            '{"answer_summary": "test", "claims": [], "confidence_score": 0.8}'
        )
        provider.client.generate_content.return_value = mock_response

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            result = provider.generate_grounded_answer("query", "context")

            assert result == mock_instance

    def test_gemini_validate_connection(self):
        """Test Gemini provider connection validation."""
        provider = GeminiProvider()
        provider.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = "working"
        provider.client.generate_content.return_value = mock_response

        result = provider.validate_connection()
        assert result


class TestOllamaProvider:
    """Test cases for OllamaProvider implementation."""

    def test_ollama_provider_initialization(self):
        """Test Ollama provider initialization."""
        with patch("requests.Session") as mock_session:
            provider = OllamaProvider()
            assert provider.model_name == "llama2"
            assert provider.base_url == "http://localhost:11434"
            mock_session.assert_called_once()

    def test_ollama_generate_structured_json(self):
        """Test Ollama provider structured JSON generation."""
        with patch("requests.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_response = MagicMock()
            mock_response.json.return_value = {"response": '{"result": "test"}'}
            mock_session.post.return_value = mock_response

            provider = OllamaProvider()
            result = provider.generate_structured_json("test prompt")

            assert result == {"result": "test"}
            mock_session.post.assert_called_once()

    def test_ollama_generate_grounded_answer(self):
        """Test Ollama provider grounded answer generation."""
        with patch("requests.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": '{"answer_summary": "test", "claims": [], "confidence_score": 0.8}'
            }
            mock_session.post.return_value = mock_response

            provider = OllamaProvider()

            with patch("src.core.schemas.Answer") as mock_answer:
                mock_instance = MagicMock()
                mock_answer.return_value = mock_instance

                result = provider.generate_grounded_answer("query", "context")

                assert result == mock_instance

    def test_ollama_validate_connection(self):
        """Test Ollama provider connection validation."""
        with patch("requests.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_session.post.return_value = mock_response

            provider = OllamaProvider()
            result = provider.validate_connection()

            assert result


class TestGlobalRouter:
    """Test cases for global router instance."""

    def test_get_llm_router_returns_instance(self):
        """Test that get_llm_router returns an instance."""
        instance = get_llm_router()
        assert instance is not None
        assert isinstance(instance, LLMRouter)
