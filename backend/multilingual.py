"""
BONUS 3 — Multilingual Ticket Handling
Detect language → translate to English → classify → translate response back.
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

from llm import analyze_ticket

# Language detection
try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# Translation
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False


LANGUAGE_NAMES = {
    "en": "English",   "fr": "French",    "de": "German",
    "es": "Spanish",   "it": "Italian",   "pt": "Portuguese",
    "ja": "Japanese",  "zh-cn": "Chinese","ko": "Korean",
    "ar": "Arabic",    "hi": "Hindi",     "ru": "Russian",
    "nl": "Dutch",     "pl": "Polish",    "tr": "Turkish",
}


def detect_language(text: str) -> str:
    """Detect language of text. Returns ISO 639-1 code."""
    if not LANGDETECT_AVAILABLE:
        return "en"
    try:
        return detect(text)
    except Exception:
        return "en"


def translate_text(text: str, source: str, target: str = "en") -> str:
    """Translate text from source language to target language."""
    if not TRANSLATOR_AVAILABLE:
        return text
    if source == target:
        return text
    try:
        # deep-translator uses 'zh-CN' format
        src = source.replace("-", "_") if "-" in source else source
        translated = GoogleTranslator(source=src, target=target).translate(text)
        return translated or text
    except Exception:
        return text


def handle_multilingual_ticket(issue_description: str) -> dict:
    """
    Full multilingual pipeline:
    1. Detect language
    2. Translate to English
    3. Classify with LLM
    4. Translate response back to original language
    """
    # Step 1: Detect language
    detected_lang = detect_language(issue_description)
    lang_name     = LANGUAGE_NAMES.get(detected_lang, detected_lang.upper())
    is_english    = detected_lang in ("en", "en-us", "en-gb")

    # Step 2: Translate to English if needed
    if not is_english and TRANSLATOR_AVAILABLE:
        english_text = translate_text(issue_description, source=detected_lang, target="en")
    else:
        english_text = issue_description

    # Step 3: LLM classification on English text
    result = analyze_ticket(english_text)

    # Step 4: Translate suggested response back to original language
    original_response = result.get("suggested_response", "")
    if not is_english and TRANSLATOR_AVAILABLE and original_response:
        translated_response = translate_text(
            original_response, source="en", target=detected_lang
        )
        result["suggested_response_translated"] = translated_response
        result["suggested_response_english"]    = original_response
    else:
        result["suggested_response_translated"] = original_response
        result["suggested_response_english"]    = original_response

    # Add language metadata
    result["detected_language"]      = detected_lang
    result["detected_language_name"] = lang_name
    result["original_text"]          = issue_description
    result["english_text"]           = english_text
    result["translation_applied"]    = not is_english and TRANSLATOR_AVAILABLE

    return result


def get_language_distribution(db) -> list:
    """Get ticket distribution by language from DB."""
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT language, COUNT(*) as count
        FROM tickets_raw
        WHERE language IS NOT NULL AND language != ''
        GROUP BY language
        ORDER BY count DESC
    """)).fetchall()
    return [{"language": r[0], "count": r[1]} for r in rows]
