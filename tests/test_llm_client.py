"""
Comprehensive unit tests for the LLM client module.
Tests Gemini API interactions, prompt building, and error handling.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from src.core.llm_client import LLMClient, get_llm_client


class TestLLMClientInitialization:
    """Test cases for LLMClient initialization."""

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            with patch("google.generativeai.configure") as mock_configure:
                with patch("google.generativeai.GenerativeModel") as mock_model:
                    client = LLMClient()
                    assert client.api_key == "test_key"
                    assert client.model_name == "gemini-1.5-pro"
                    assert client.client is not None
                    mock_configure.assert_called_once_with(api_key="test_key")
                    mock_model.assert_called_once_with("gemini-1.5-pro")

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient()
            assert client.api_key is None
            assert client.client is None

    def test_init_with_custom_model(self):
        """Test initialization with custom model name."""
        with patch.dict("os.environ", {
            "GEMINI_API_KEY": "test_key",
            "GEMINI_MODEL": "gemini-pro"
        }):
            with patch("google.generativeai.configure"):
                with patch("google.generativeai.GenerativeModel") as mock_model:
                    client = LLMClient()
                    assert client.model_name == "gemini-pro"
                    mock_model.assert_called_once_with("gemini-pro")


class TestPromptBuilding:
    """Test cases for prompt building functions."""

    def test_build_toc_parsing_prompt(self):
        """Test ToC parsing prompt building."""
        client = LLMClient()
        toc_text = "Chapter 1: Introduction........5\nChapter 2: Methods........12"

        prompt = client._build_toc_parsing_prompt(toc_text)

        assert "Table of Contents" in prompt
        assert toc_text in prompt
        assert "JSON array" in prompt
        assert "TOCNode" in prompt
        assert "page_number" in prompt
        assert "children" in prompt

    def test_build_index_parsing_prompt(self):
        """Test index parsing prompt building."""
        client = LLMClient()
        index_text = "Apple, 5, 12, 45\nBanana, 8, 23"

        prompt = client._build_index_parsing_prompt(index_text)

        assert "Alphabetical Index" in prompt
        assert index_text in prompt
        assert "IndexEntry" in prompt
        assert "page_numbers" in prompt
        assert "term" in prompt

    def test_build_grounded_generation_prompt(self):
        """Test grounded generation prompt building."""
        client = LLMClient()
        query = "What is machine learning?"
        context = "[Chunk 1 - ID: 123, Page: 5]\nMachine learning is..."

        prompt = client._build_grounded_generation_prompt(query, context)

        assert query in prompt
        assert context in prompt
        assert "answer_summary" in prompt
        assert "claims" in prompt
        assert "confidence_score" in prompt
        assert "source_chunk_id" in prompt


class TestJSONExtraction:
    """Test cases for JSON extraction from responses."""

    def test_extract_json_from_plain_response(self):
        """Test extracting JSON from plain response."""
        client = LLMClient()
        response_text = '{"key": "value"}'

        result = client._extract_json_from_response(response_text)
        assert result == '{"key": "value"}'

    def test_extract_json_from_markdown_response(self):
        """Test extracting JSON from markdown code block."""
        client = LLMClient()
        response_text = '```json\n{"key": "value"}\n```'

        result = client._extract_json_from_response(response_text)
        assert result == '{"key": "value"}'

    def test_extract_json_from_generic_markdown(self):
        """Test extracting JSON from generic markdown block."""
        client = LLMClient()
        response_text = '```\n{"key": "value"}\n```'

        result = client._extract_json_from_response(response_text)
        assert result == '{"key": "value"}'

    def test_extract_json_with_whitespace(self):
        """Test extracting JSON with surrounding whitespace."""
        client = LLMClient()
        response_text = '\n  \n```json\n{"key": "value"}\n```\n  \n'

        result = client._extract_json_from_response(response_text)
        assert result == '{"key": "value"}'


class TestAnswerValidation:
    """Test cases for answer response validation."""

    def test_validate_answer_response_complete(self):
        """Test validation of complete answer response."""
        client = LLMClient()
        answer_data = {
            "answer_summary": "This is a test answer",
            "claims": [
                {
                    "text": "Test claim",
                    "source_chunk_id": 123,
                    "page_number": 5
                }
            ],
            "confidence_score": 0.85
        }

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            result = client._validate_answer_response(answer_data)

            assert result == mock_instance
            mock_answer.assert_called_once_with(**answer_data)

    def test_validate_answer_response_missing_fields(self):
        """Test validation with missing fields."""
        client = LLMClient()
        answer_data = {}  # Empty data

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            client._validate_answer_response(answer_data)

            # Should have added default values
            call_args = mock_answer.call_args[1]
            assert call_args["answer_summary"] == "No summary provided"
            assert call_args["claims"] == []
            assert call_args["confidence_score"] == 0.0

    def test_validate_answer_response_invalid_confidence(self):
        """Test validation with invalid confidence score."""
        client = LLMClient()
        answer_data = {
            "answer_summary": "Test",
            "claims": [],
            "confidence_score": 1.5  # Invalid: > 1.0
        }

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            client._validate_answer_response(answer_data)

            # Should have corrected confidence score
            call_args = mock_answer.call_args[1]
            assert call_args["confidence_score"] == 0.0

    def test_validate_answer_response_invalid_claims(self):
        """Test validation with invalid claims structure."""
        client = LLMClient()
        answer_data = {
            "answer_summary": "Test",
            "claims": [
                {"text": "Valid claim", "source_chunk_id": 123, "page_number": 5},
                {"invalid": "claim"},  # Missing required fields
                {"text": "Another", "source_chunk_id": "invalid", "page_number": 10}  # Wrong types
            ],
            "confidence_score": 0.8
        }

        # The method should handle the ValueError internally and filter out invalid claims
        # Only the valid claim should remain
        result = client._validate_answer_response(answer_data)

        # Should have filtered out invalid claims and kept only the valid one
        assert len(result.claims) == 1
        assert result.claims[0].text == "Valid claim"
        assert result.claims[0].source_chunk_id == 123
        assert result.claims[0].page_number == 5


class TestFallbackAnswer:
    """Test cases for fallback answer creation."""

    def test_create_fallback_answer(self):
        """Test creating fallback answer."""
        client = LLMClient()
        message = "Test fallback message"

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            result = client._create_fallback_answer(message)

            assert result == mock_instance
            mock_answer.assert_called_once_with(
                answer_summary=message,
                claims=[],
                confidence_score=0.0
            )


class TestConnectionValidation:
    """Test cases for connection validation."""

    def test_validate_connection_success(self):
        """Test successful connection validation."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = "Hello, I'm working!"
        client.client.generate_content.return_value = mock_response

        result = client.validate_connection()
        assert result is True

    def test_validate_connection_no_client(self):
        """Test connection validation without client."""
        client = LLMClient()
        client.client = None

        result = client.validate_connection()
        assert result is False

    def test_validate_connection_api_error(self):
        """Test connection validation with API error."""
        client = LLMClient()
        client.client = MagicMock()
        client.client.generate_content.side_effect = Exception("API Error")

        result = client.validate_connection()
        assert result is False


class TestStructuredTOC:
    """Test cases for structured ToC parsing."""

    def test_get_structured_toc_no_client(self):
        """Test ToC parsing without initialized client."""
        client = LLMClient()
        client.client = None

        with pytest.raises(Exception, match="LLM client not initialized"):
            client.get_structured_toc("test toc text")

    def test_get_structured_toc_success(self):
        """Test successful ToC parsing."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"parsed": "toc"}'
        client.client.generate_content.return_value = mock_response

        with patch("json.loads") as mock_json_loads:
            mock_json_loads.return_value = {"parsed": "toc"}

            result = client.get_structured_toc("test toc text")

            assert result == {"parsed": "toc"}
            client.client.generate_content.assert_called_once()

    def test_get_structured_toc_json_error(self):
        """Test ToC parsing with JSON parsing error."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = 'invalid json'
        client.client.generate_content.return_value = mock_response

        with patch("json.loads", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            with pytest.raises(Exception, match="Failed to parse LLM response as JSON"):
                client.get_structured_toc("test toc text")

    def test_get_structured_toc_api_error(self):
        """Test ToC parsing with API error."""
        client = LLMClient()
        client.client = MagicMock()
        client.client.generate_content.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="LLM API call failed"):
            client.get_structured_toc("test toc text")


class TestStructuredIndex:
    """Test cases for structured index parsing."""

    def test_get_structured_index_no_client(self):
        """Test index parsing without initialized client."""
        client = LLMClient()
        client.client = None

        with pytest.raises(Exception, match="LLM client not initialized"):
            client.get_structured_index("test index text")

    def test_get_structured_index_success(self):
        """Test successful index parsing."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"parsed": "index"}'
        client.client.generate_content.return_value = mock_response

        with patch("json.loads") as mock_json_loads:
            mock_json_loads.return_value = {"parsed": "index"}

            result = client.get_structured_index("test index text")

            assert result == {"parsed": "index"}
            client.client.generate_content.assert_called_once()


class TestGroundedAnswerGeneration:
    """Test cases for grounded answer generation."""

    def test_generate_grounded_answer_no_client(self):
        """Test answer generation without client (should return fallback)."""
        client = LLMClient()
        client.client = None

        result = client.generate_grounded_answer("test query", "test context")

        assert result.answer_summary == "I apologize, but the LLM service is currently unavailable. Please try again later."
        assert result.confidence_score == 0.0
        assert result.claims == []

    def test_generate_grounded_answer_success(self):
        """Test successful answer generation."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"answer_summary": "Test answer", "claims": [], "confidence_score": 0.8}'
        client.client.generate_content.return_value = mock_response

        with patch("src.core.schemas.Answer") as mock_answer:
            mock_instance = MagicMock()
            mock_answer.return_value = mock_instance

            result = client.generate_grounded_answer("test query", "test context")

            assert result == mock_instance

    def test_generate_grounded_answer_json_error(self):
        """Test answer generation with JSON parsing error."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = 'invalid json'
        client.client.generate_content.return_value = mock_response

        result = client.generate_grounded_answer("test query", "test context")

        # Should return fallback answer
        assert "apologize" in result.answer_summary
        assert result.confidence_score == 0.0

    def test_generate_grounded_answer_validation_error(self):
        """Test answer generation with validation error."""
        client = LLMClient()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.text = '{"invalid": "data"}'
        client.client.generate_content.return_value = mock_response

        with patch("src.core.llm_client.LLMClient._validate_answer_response", side_effect=Exception("Validation failed")):
            result = client.generate_grounded_answer("test query", "test context")

            # Should return fallback answer
            assert "apologize" in result.answer_summary
            assert result.confidence_score == 0.0

    def test_generate_grounded_answer_api_error(self):
        """Test answer generation with API error."""
        client = LLMClient()
        client.client = MagicMock()
        client.client.generate_content.side_effect = Exception("API Error")

        result = client.generate_grounded_answer("test query", "test context")

        # Should return fallback answer
        assert "apologize" in result.answer_summary
        assert result.confidence_score == 0.0


class TestGlobalClient:
    """Test cases for global client instance management."""

    def test_get_llm_client_returns_instance(self):
        """Test that get_llm_client returns an instance."""
        # Test that the function returns something (basic smoke test)
        instance = get_llm_client()
        assert instance is not None
        # The instance should be an LLMClient or have the expected interface
        assert hasattr(instance, 'validate_connection')