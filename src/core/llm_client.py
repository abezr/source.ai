"""
LLM client module for HBI system.
Provides abstracted interface for interacting with Gemini API.
"""

import os
import json
import logging
from typing import Dict, Any, TYPE_CHECKING
from pydantic import ValidationError
import google.generativeai as genai
from google.generativeai.types import RequestOptions

if TYPE_CHECKING:
    from . import schemas


class LLMClient:
    """
    Abstracted client for interacting with Google's Gemini API.
    """

    def __init__(self):
        """Initialize the Gemini client with API key from environment."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.client = None

        if not self.api_key:
            # For testing/development, allow initialization without API key
            # The client will be None and methods will handle this gracefully
            return

        # Configure the API
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model_name)

    def get_structured_toc(self, toc_text: str) -> Dict[str, Any]:
        """
        Parse table of contents text into structured JSON format using Gemini.

        Args:
            toc_text: Raw table of contents text extracted from PDF

        Returns:
            Dict containing structured ToC data

        Raises:
            Exception: If LLM API call fails or returns invalid JSON
        """
        if not self.client:
            raise Exception("LLM client not initialized - missing API key")

        prompt = self._build_toc_parsing_prompt(toc_text)

        try:
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent parsing
                    top_p=0.8,
                    top_k=10,
                    max_output_tokens=2048,
                ),
                request_options=RequestOptions(
                    timeout=30.0  # 30 second timeout
                ),
            )

            # Extract the JSON from the response
            json_text = self._extract_json_from_response(response.text)
            return json.loads(json_text)

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"LLM API call failed: {str(e)}")

    def get_structured_index(self, index_text: str) -> Dict[str, Any]:
        """
        Parse alphabetical index text into structured JSON format using Gemini.

        Args:
            index_text: Raw alphabetical index text extracted from book

        Returns:
            Dict containing structured index data

        Raises:
            Exception: If LLM API call fails or returns invalid JSON
        """
        if not self.client:
            raise Exception("LLM client not initialized - missing API key")

        prompt = self._build_index_parsing_prompt(index_text)

        try:
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent parsing
                    top_p=0.8,
                    top_k=10,
                    max_output_tokens=4096,  # Larger output for index parsing
                ),
                request_options=RequestOptions(
                    timeout=60.0  # 60 second timeout for complex index parsing
                ),
            )

            # Extract the JSON from the response
            json_text = self._extract_json_from_response(response.text)
            return json.loads(json_text)

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"LLM API call failed: {str(e)}")

    def _build_toc_parsing_prompt(self, toc_text: str) -> str:
        """
        Build the prompt for ToC parsing.

        Args:
            toc_text: Raw table of contents text

        Returns:
            Complete prompt string
        """
        return f"""
You are a specialized AI assistant for parsing book Table of Contents (ToC) into structured JSON format.

Your task is to analyze the following table of contents text and convert it into a hierarchical JSON structure.

**Input ToC Text:**
{toc_text}

**Instructions:**
1. Parse the text to identify chapters, sections, and subsections
2. Extract titles and page numbers for each entry
3. Maintain the hierarchical structure (chapters contain sections, sections contain subsections)
4. Handle various formatting styles (dots, dashes, Roman numerals, etc.)
5. Return ONLY valid JSON - no additional text or explanations

**Output Format:**
Return a JSON array of TOCNode objects with this exact structure:
[
  {{
    "title": "Chapter Title",
    "page_number": 5,
    "children": [
      {{
        "title": "Section Title",
        "page_number": 7,
        "children": [
          {{
            "title": "Subsection Title",
            "page_number": 9,
            "children": []
          }}
        ]
      }}
    ]
  }}
]

**Important Rules:**
- page_number must be an integer
- children is always an array (empty [] if no children)
- Maintain the exact hierarchy from the original text
- If page numbers are missing or unclear, use 0
- Return only the JSON array, no markdown formatting or explanations

Parse the provided text and return the structured JSON:
"""

    def _build_index_parsing_prompt(self, index_text: str) -> str:
        """
        Build the prompt for alphabetical index parsing.

        Args:
            index_text: Raw alphabetical index text

        Returns:
            Complete prompt string
        """
        return f"""
You are a specialized AI assistant for parsing book Alphabetical Index into structured JSON format.

Your task is to analyze the following index text and convert it into a structured JSON array of index entries.

**Input Index Text:**
{index_text}

**Instructions:**
1. Parse the text to identify index terms and their page references
2. Extract terms and all associated page numbers
3. Handle various formatting styles (commas, hyphens, ranges, etc.)
4. Normalize term names (remove extra spaces, standardize capitalization)
5. Return ONLY valid JSON - no additional text or explanations

**Output Format:**
Return a JSON array of IndexEntry objects with this exact structure:
[
  {{
    "term": "Index Term",
    "page_numbers": [5, 12, 45]
  }},
  {{
    "term": "Another Term",
    "page_numbers": [8, 23]
  }}
]

**Important Rules:**
- term: The index term as a string (normalized)
- page_numbers: Array of integers representing page references
- Handle page ranges like "5-7" as separate entries [5, 6, 7]
- Handle comma-separated pages like "5, 12, 45" as [5, 12, 45]
- Handle hyphenated ranges like "5-12" as [5, 6, 7, 8, 9, 10, 11, 12]
- Ignore non-numeric page references
- Return only the JSON array, no markdown formatting or explanations
- If no valid index entries are found, return an empty array []

**Examples of formats to handle:**
- "Term, 5, 12, 45"
- "Term 5-7, 12"
- "Term........5, 12-15"
- "term: 5, 12, 45"

Parse the provided text and return the structured JSON:
"""

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling potential markdown formatting.

        Args:
            response_text: Raw response from LLM

        Returns:
            Clean JSON string
        """
        # Remove markdown code blocks if present
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def validate_connection(self) -> bool:
        """
        Validate that the LLM client can connect to the API.

        Returns:
            True if connection is successful
        """
        if not self.client:
            return False

        try:
            # Simple test query
            response = self.client.generate_content(
                "Hello, can you confirm you're working?",
                generation_config=genai.types.GenerationConfig(max_output_tokens=10),
            )
            return bool(response.text)
        except Exception:
            return False

    def generate_grounded_answer(self, query: str, context: str) -> "schemas.Answer":
        """
        Generate a grounded answer using retrieved context with mandatory citations.

        Args:
            query: User's question
            context: Retrieved context passages formatted with chunk IDs and page numbers

        Returns:
            Answer object with claims, confidence score, and summary

        Raises:
            Exception: If generation fails or validation fails
        """
        if not self.client:
            # Return fallback answer when API is not available
            return self._create_fallback_answer(
                "I apologize, but the LLM service is currently unavailable. Please try again later."
            )

        try:
            prompt = self._build_grounded_generation_prompt(query, context)

            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent, factual responses
                    top_p=0.8,
                    top_k=10,
                    max_output_tokens=2048,
                    response_mime_type="application/json",  # Force JSON response
                ),
                request_options=RequestOptions(
                    timeout=60.0  # 60 second timeout for complex generation
                ),
            )

            # Extract and validate JSON response
            json_text = self._extract_json_from_response(response.text)
            answer_data = json.loads(json_text)

            # Validate and create Answer object
            validated_answer = self._validate_answer_response(answer_data)

            return validated_answer

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM JSON response: {str(e)}")
            return self._create_fallback_answer(
                "I apologize, but I encountered an error processing your request. Please try again."
            )
        except ValidationError as e:
            logging.error(f"LLM response validation failed: {str(e)}")
            return self._create_fallback_answer(
                "I apologize, but I couldn't generate a properly validated response. Please try rephrasing your question."
            )
        except Exception as e:
            logging.error(f"Grounded answer generation failed: {str(e)}")
            return self._create_fallback_answer(
                "I apologize, but I'm currently unable to process your request. Please try again later."
            )

    def _build_grounded_generation_prompt(self, query: str, context: str) -> str:
        """
        Build the master prompt for grounded answer generation.

        Args:
            query: User's question
            context: Formatted context with chunk IDs and page numbers

        Returns:
            Complete prompt string
        """
        return f"""You are a precise, truth-seeking AI assistant that provides factual answers based solely on the provided context.

**CRITICAL INSTRUCTIONS:**
1. **Answer ONLY using information from the provided context passages.** Do not use any external knowledge, assumptions, or prior training data.
2. **If the answer is not in the context, state that you cannot answer the question.**
3. **Every claim you make MUST be supported by a specific context passage.**
4. **Cite the exact source_chunk_id and page_number for each claim.**
5. **Provide a confidence_score between 0.0 and 1.0** indicating how well your answer is supported by the context.

**User Query:** {query}

**Context Passages:**
{context}

**Output Format:**
Return a JSON object with this exact structure:
{{
  "answer_summary": "A concise summary of your answer (2-3 sentences max)",
  "claims": [
    {{
      "text": "Specific claim or fact from the answer",
      "source_chunk_id": 123,
      "page_number": 45
    }}
  ],
  "confidence_score": 0.85
}}

**Rules:**
- answer_summary: Brief, direct answer to the query
- claims: Array of specific claims, each with source citation
- confidence_score: 0.0 (cannot answer) to 1.0 (fully confident)
- If confidence < 0.3: Set answer_summary to indicate you cannot answer confidently
- Every claim must have a valid source_chunk_id from the context
- Do not make claims without citing sources
- Return ONLY valid JSON, no additional text or formatting

Generate your response:"""

    def _validate_answer_response(self, answer_data: dict) -> "schemas.Answer":
        """
        Validate and convert raw LLM response to Answer schema.

        Args:
            answer_data: Raw dictionary from LLM response

        Returns:
            Validated Answer object

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Import here to avoid circular imports
            from . import schemas

            # Ensure required fields exist
            if "answer_summary" not in answer_data:
                answer_data["answer_summary"] = "No summary provided"
            if "claims" not in answer_data:
                answer_data["claims"] = []
            if "confidence_score" not in answer_data:
                answer_data["confidence_score"] = 0.0

            # Validate confidence score range
            confidence = answer_data.get("confidence_score", 0.0)
            if not isinstance(confidence, (int, float)) or not (
                0.0 <= confidence <= 1.0
            ):
                answer_data["confidence_score"] = 0.0

            # Validate claims structure
            claims = answer_data.get("claims", [])
            if not isinstance(claims, list):
                claims = []

            # Filter out invalid claims
            valid_claims = []
            for claim in claims:
                if (
                    isinstance(claim, dict)
                    and "text" in claim
                    and "source_chunk_id" in claim
                    and "page_number" in claim
                ):
                    valid_claims.append(
                        {
                            "text": str(claim["text"]),
                            "source_chunk_id": int(claim["source_chunk_id"]),
                            "page_number": int(claim["page_number"]),
                        }
                    )

            answer_data["claims"] = valid_claims

            # Create and validate Answer object
            answer = schemas.Answer(**answer_data)
            return answer

        except Exception as e:
            raise ValidationError(f"Answer validation failed: {str(e)}")

    def _create_fallback_answer(self, message: str) -> "schemas.Answer":
        """
        Create a fallback Answer object for error cases.

        Args:
            message: Fallback message

        Returns:
            Answer object with zero confidence
        """
        from . import schemas

        return schemas.Answer(answer_summary=message, claims=[], confidence_score=0.0)


# Global client instance
llm_client = LLMClient()


def get_llm_client():
    """
    Dependency injection function for FastAPI endpoints.
    Provides an LLMClient instance.

    Returns:
        LLMClient: The LLM client instance
    """
    return llm_client
