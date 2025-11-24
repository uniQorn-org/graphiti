#!/usr/bin/env python3
"""
Translation utility using OpenAI API.
Translates Japanese text to English for better knowledge graph processing.
"""

import os
from openai import OpenAI

def translate_to_english(text: str, model: str = "gpt-4o-mini") -> str:
    """
    Translate text to English using OpenAI API.
    
    Args:
        text: Text to translate (any language)
        model: OpenAI model to use
        
    Returns:
        Translated English text
    """
    if not text or not text.strip():
        return text
    
    # Check if text is already in English (basic heuristic)
    if is_mostly_ascii(text):
        return text
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        response = client.chat.completions.create(
            model=model,
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
            temperature=0.3,
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Warning: Translation failed: {e}")
        return text  # Return original text if translation fails


def is_mostly_ascii(text: str, threshold: float = 0.7) -> bool:
    """
    Check if text is mostly ASCII characters.
    
    Args:
        text: Text to check
        threshold: Minimum ratio of ASCII characters (0.0-1.0)
        
    Returns:
        True if text is mostly ASCII
    """
    if not text:
        return True
    
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    ratio = ascii_chars / len(text)
    return ratio >= threshold


def translate_with_limit(text: str, max_chars: int = 10000, model: str = "gpt-4o-mini") -> str:
    """
    Translate text with character limit.
    If text exceeds limit, translate first part and append truncation notice.
    
    Args:
        text: Text to translate
        max_chars: Maximum characters to translate
        model: OpenAI model to use
        
    Returns:
        Translated English text
    """
    if len(text) <= max_chars:
        return translate_to_english(text, model)
    
    # Truncate text
    truncated = text[:max_chars]
    translated = translate_to_english(truncated, model)
    
    return f"{translated}\n\n[Note: Content truncated due to length. Original text was {len(text)} characters.]"
