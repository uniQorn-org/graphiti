#!/usr/bin/env python3
"""
Translation utility using OpenAI API.
Translates Japanese text to English for better knowledge graph processing.
"""

import os
from openai import OpenAI
from shared.utils.proxy_config import create_httpx_client
from shared.constants import TRANSLATION_TEMPERATURE, TRANSLATION_MODEL, ASCII_DETECTION_THRESHOLD, MAX_CHARS_DEFAULT
from shared.exceptions import TranslationError

def translate_to_english(text: str, model: str | None = None) -> str:
    """
    Translate text to English using OpenAI API.

    Args:
        text: Text to translate (any language)
        model: OpenAI model to use (defaults to TRANSLATION_MODEL from constants)

    Returns:
        Translated English text

    Raises:
        TranslationError: If translation fails and fallback is not possible
    """
    if not text or not text.strip():
        return text

    # Check if text is already in English (basic heuristic)
    if is_mostly_ascii(text):
        return text

    # Use configured model or default
    effective_model = model or TRANSLATION_MODEL

    # Create httpx client with proxy configuration
    http_client = create_httpx_client()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client)

    try:
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate the given text to English. Preserve technical terms, code blocks, URLs, and markdown formatting. Only translate natural language text. If the text is already in English, return it as-is."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=TRANSLATION_TEMPERATURE,
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Translation failed: {e}")
        return text  # Return original text if translation fails


def is_mostly_ascii(text: str, threshold: float | None = None) -> bool:
    """
    Check if text is mostly ASCII characters.

    Args:
        text: Text to check
        threshold: Minimum ratio of ASCII characters (0.0-1.0). Defaults to ASCII_DETECTION_THRESHOLD from constants.

    Returns:
        True if text is mostly ASCII
    """
    if not text:
        return True

    effective_threshold = threshold if threshold is not None else ASCII_DETECTION_THRESHOLD
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    ratio = ascii_chars / len(text)
    return ratio >= effective_threshold


def translate_with_limit(text: str, max_chars: int | None = None, model: str | None = None) -> str:
    """
    Translate text with character limit.
    If text exceeds limit, translate first part and append truncation notice.

    Args:
        text: Text to translate
        max_chars: Maximum characters to translate (defaults to MAX_CHARS_DEFAULT from constants)
        model: OpenAI model to use (defaults to TRANSLATION_MODEL from constants)

    Returns:
        Translated English text
    """
    effective_max_chars = max_chars if max_chars is not None else MAX_CHARS_DEFAULT

    if len(text) <= effective_max_chars:
        return translate_to_english(text, model)

    # Truncate text
    truncated = text[:effective_max_chars]
    translated = translate_to_english(truncated, model)

    return f"{translated}\n\n[Note: Content truncated due to length. Original text was {len(text)} characters.]"
