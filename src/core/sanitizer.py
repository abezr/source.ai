"""
Security sanitizer module for HBI system.
Provides comprehensive text sanitization to mitigate prompt injection attacks before LLM processing.
"""

import logging
import re
from typing import Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SanitizationResult:
    """Result of text sanitization operation."""

    original_text: str
    sanitized_text: str
    changes_made: Dict[str, int]
    is_modified: bool


class TextSanitizer:
    """
    Comprehensive text sanitizer for LLM inputs to prevent prompt injection attacks.

    This sanitizer implements multiple layers of protection:
    1. Markdown and formatting removal
    2. Code block and script removal
    3. Instructional phrase removal
    4. System prompt override attempts
    5. Malicious pattern removal
    """

    def __init__(self):
        """Initialize the sanitizer with comprehensive regex patterns."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile all regex patterns for efficient reuse."""

        # Markdown headings and formatting (process in order of specificity)
        self.markdown_patterns = [
            (re.compile(r"^#{1,6}\s+.*$", re.MULTILINE), "markdown_heading"),
            (
                re.compile(r"#+\s+.*?(?=\n|$)"),
                "markdown_heading_inline",
            ),  # More flexible heading match
            (re.compile(r"\*\*.*?\*\*"), "bold_text"),
            (re.compile(r"\*.*?\*"), "italic_text"),
            (re.compile(r"^\s*[-*+]\s+.*$", re.MULTILINE), "list_item"),
            (re.compile(r"^\s*\d+\.\s+.*$", re.MULTILINE), "numbered_list"),
        ]

        # Code blocks (multi-line) - process before inline code
        self.code_block_patterns = [
            (re.compile(r"```[\s\S]*?```"), "code_block"),
            (re.compile(r"~~~[\s\S]*?~~~"), "code_block_alt"),
            (re.compile(r"<code>[\s\S]*?</code>", re.IGNORECASE), "html_code"),
            (re.compile(r"<pre>[\s\S]*?</pre>", re.IGNORECASE), "html_pre"),
        ]

        # Inline code (process after code blocks)
        self.inline_code_patterns = [
            (re.compile(r"`.*?`"), "inline_code"),
        ]

        # Instructional phrases and system overrides
        self.instruction_patterns = [
            # System prompt overrides
            (re.compile(r"(?i)system\s*:.*?(?=\n\n|\n[A-Z]|\Z)"), "system_override"),
            (
                re.compile(r"(?i)assistant\s*:.*?(?=\n\n|\n[A-Z]|\Z)"),
                "assistant_override",
            ),
            (re.compile(r"(?i)user\s*:.*?(?=\n\n|\n[A-Z]|\Z)"), "user_override"),
            # Direct instructions
            (
                re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"),
                "ignore_instructions",
            ),
            (
                re.compile(r"(?i)forget\s+(all\s+)?previous\s+(instructions|rules)"),
                "forget_instructions",
            ),
            (
                re.compile(r"(?i)override\s+(all\s+)?previous\s+(instructions|rules)"),
                "override_instructions",
            ),
            (
                re.compile(r"(?i)disregard\s+(all\s+)?previous\s+(instructions|rules)"),
                "disregard_instructions",
            ),
            # Role changes
            (re.compile(r"(?i)you\s+are\s+(now|a)\s+.*?(?=\.|\n|$)"), "role_change"),
            (re.compile(r"(?i)act\s+as\s+.*?(?=\.|\n|$)"), "act_as"),
            (
                re.compile(r"(?i)pretend\s+(to\s+be|you\s+are)\s+.*?(?=\.|\n|$)"),
                "pretend_role",
            ),
            # Output format instructions
            (
                re.compile(
                    r"(?i)output\s+(only|just|exclusively)\s+(json|xml|html|markdown)"
                ),
                "output_format",
            ),
            (
                re.compile(
                    r"(?i)return\s+(only|just|exclusively)\s+(json|xml|html|markdown)"
                ),
                "return_format",
            ),
            (
                re.compile(
                    r"(?i)respond\s+(only|just|exclusively)\s+(in|with)\s+(json|xml|html|markdown)"
                ),
                "respond_format",
            ),
            # Dangerous commands
            (
                re.compile(
                    r"(?i)(run|execute|eval|system|shell|cmd|powershell)\s+.*?(?=\n|$)"
                ),
                "dangerous_command",
            ),
            (
                re.compile(r"(?i)(import|require|load)\s+(os|sys|subprocess|shutil)"),
                "dangerous_import",
            ),
            # Additional injection patterns
            (re.compile(r"(?i)break\s+character"), "break_character"),
            (re.compile(r"(?i)jailbreak"), "jailbreak"),
            (re.compile(r"(?i)dont\s+follow\s+rules"), "dont_follow_rules"),
            (re.compile(r"(?i)override.*safety"), "override_safety"),
            (re.compile(r"(?i)act\s+as.*uncensored"), "uncensored_role"),
            (re.compile(r"(?i)forget.*system\s+prompt"), "forget_system"),
        ]

        # Malicious patterns
        self.malicious_patterns = [
            # SQL injection attempts
            (
                re.compile(
                    r"(?i)(select|insert|update|delete|drop|create|alter)\s+.*?(from|into|table|database)"
                ),
                "sql_injection",
            ),
            # XSS attempts
            (
                re.compile(r"<script[^>]*>[\s\S]*?</script>", re.IGNORECASE),
                "script_tag",
            ),
            (re.compile(r"javascript\s*:", re.IGNORECASE), "javascript_url"),
            (re.compile(r"on\w+\s*=", re.IGNORECASE), "event_handler"),
            # Path traversal
            (re.compile(r"\.\./|\.\.\\"), "path_traversal"),
            (
                re.compile(r"/etc/passwd|/etc/shadow|/etc/hosts", re.IGNORECASE),
                "sensitive_file",
            ),
            # Base64 encoded content (potential obfuscation)
            (re.compile(r"(?i)base64\s*[:-]\s*[A-Za-z0-9+/=]{20,}"), "base64_content"),
            # URL patterns that might contain malicious content
            (
                re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
                "suspicious_url",
            ),
        ]

        # Structural patterns that might confuse LLM
        self.structural_patterns = [
            # Excessive whitespace
            (re.compile(r"\n{3,}"), "excessive_newlines"),
            (re.compile(r"\s{4,}"), "excessive_spaces"),
            # Control characters
            (
                re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]"),
                "control_characters",
            ),
            # Unicode confusables
            (
                re.compile(r"[\u200B\u200C\u200D\u200E\u200F\u202A-\u202E\uFEFF]"),
                "zero_width_chars",
            ),
        ]

    def sanitize_text_for_llm(
        self, text: str, context: str = "general"
    ) -> SanitizationResult:
        """
        Sanitize text for safe LLM processing.

        Args:
            text: Raw text to sanitize
            context: Context of sanitization (e.g., 'toc', 'index', 'general')

        Returns:
            SanitizationResult with original text, sanitized text, and change summary
        """
        if not text or not isinstance(text, str):
            return SanitizationResult(
                original_text=text or "",
                sanitized_text=text or "",
                changes_made={},
                is_modified=False,
            )

        original_text = text
        changes_made = {}
        is_modified = False

        # Apply sanitization layers in correct order
        text = self._sanitize_code_blocks(
            text, changes_made
        )  # Process code blocks first
        text = self._sanitize_markdown(text, changes_made)  # Then markdown formatting
        text = self._sanitize_inline_code(text, changes_made)  # Then inline code
        text = self._sanitize_instructions(text, changes_made)  # Then instructions
        text = self._sanitize_malicious_patterns(
            text, changes_made
        )  # Then malicious patterns
        text = self._sanitize_structural_issues(
            text, changes_made
        )  # Finally structural issues

        # Context-specific sanitization
        if context == "toc":
            text = self._sanitize_toc_specific(text, changes_made)
        elif context == "index":
            text = self._sanitize_index_specific(text, changes_made)

        # Final cleanup
        text = self._final_cleanup(text, changes_made)

        is_modified = text != original_text

        # Log sanitization results
        if is_modified:
            logger.info(
                f"Text sanitized for context '{context}': "
                f"original_length={len(original_text)}, "
                f"sanitized_length={len(text)}, "
                f"changes={changes_made}"
            )

        return SanitizationResult(
            original_text=original_text,
            sanitized_text=text,
            changes_made=changes_made,
            is_modified=is_modified,
        )

    def _sanitize_markdown(self, text: str, changes: Dict[str, int]) -> str:
        """Remove markdown formatting that could confuse LLM."""
        for pattern, pattern_name in self.markdown_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)
                text = pattern.sub("", text)

        return text

    def _sanitize_inline_code(self, text: str, changes: Dict[str, int]) -> str:
        """Remove inline code formatting."""
        for pattern, pattern_name in self.inline_code_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)
                text = pattern.sub("", text)

        return text

    def _sanitize_code_blocks(self, text: str, changes: Dict[str, int]) -> str:
        """Remove code blocks and script content."""
        for pattern, pattern_name in self.code_block_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)
                text = pattern.sub("[CODE_BLOCK_REMOVED]", text)

        return text

    def _sanitize_instructions(self, text: str, changes: Dict[str, int]) -> str:
        """Remove instructional phrases that could override system prompts."""
        for pattern, pattern_name in self.instruction_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)
                text = pattern.sub("[INSTRUCTION_REMOVED]", text)

        return text

    def _sanitize_malicious_patterns(self, text: str, changes: Dict[str, int]) -> str:
        """Remove potentially malicious patterns."""
        for pattern, pattern_name in self.malicious_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)
                if pattern_name in ["script_tag", "sql_injection", "dangerous_command"]:
                    text = pattern.sub("[MALICIOUS_CONTENT_REMOVED]", text)
                else:
                    text = pattern.sub("", text)

        return text

    def _sanitize_structural_issues(self, text: str, changes: Dict[str, int]) -> str:
        """Fix structural issues that could confuse LLM parsing."""
        for pattern, pattern_name in self.structural_patterns:
            matches = pattern.findall(text)
            if matches:
                changes[pattern_name] = changes.get(pattern_name, 0) + len(matches)

                if pattern_name == "excessive_newlines":
                    text = pattern.sub("\n\n", text)
                elif pattern_name == "excessive_spaces":
                    text = pattern.sub(" ", text)
                elif pattern_name in ["control_characters", "zero_width_chars"]:
                    text = pattern.sub("", text)

        return text

    def _sanitize_toc_specific(self, text: str, changes: Dict[str, int]) -> str:
        """TOC-specific sanitization rules."""
        # Remove page number patterns that might be confused with instructions
        page_pattern = re.compile(r"(?i)page\s+\d+", re.MULTILINE)
        matches = page_pattern.findall(text)
        if matches:
            changes["toc_page_references"] = len(matches)
            text = page_pattern.sub("", text)

        return text

    def _sanitize_index_specific(self, text: str, changes: Dict[str, int]) -> str:
        """Index-specific sanitization rules."""
        # Remove alphabetical section headers that might be confused
        alpha_pattern = re.compile(r"^[A-Z]\s*$", re.MULTILINE)
        matches = alpha_pattern.findall(text)
        if matches:
            changes["index_alpha_headers"] = len(matches)
            text = alpha_pattern.sub("", text)

        return text

    def _final_cleanup(self, text: str, changes: Dict[str, int]) -> str:
        """Final cleanup and normalization."""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        # Ensure minimum content length
        if len(text) < 10:
            changes["insufficient_content"] = 1
            text = "[CONTENT_TOO_SHORT]"

        return text


# Global sanitizer instance
_sanitizer = TextSanitizer()


def sanitize_text_for_llm(text: str, context: str = "general") -> str:
    """
    Sanitize text for safe LLM processing.

    Args:
        text: Raw text to sanitize
        context: Context of sanitization ('toc', 'index', 'general')

    Returns:
        Sanitized text safe for LLM processing
    """
    result = _sanitizer.sanitize_text_for_llm(text, context)
    return result.sanitized_text


def sanitize_text_with_audit(text: str, context: str = "general") -> SanitizationResult:
    """
    Sanitize text and return detailed audit information.

    Args:
        text: Raw text to sanitize
        context: Context of sanitization ('toc', 'index', 'general')

    Returns:
        SanitizationResult with full audit trail
    """
    return _sanitizer.sanitize_text_for_llm(text, context)
