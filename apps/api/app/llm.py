from __future__ import annotations

import json
import logging
import re
from typing import Any

from .config import settings
from .schemas import SourceRef

log = logging.getLogger("legalo.llm")

INDIC_LANGS = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "sa": "Sanskrit",
    "ks": "Kashmiri",
    "sd": "Sindhi",
    "ne": "Nepali",
    "kok": "Konkani",
    "mai": "Maithili",
    "doi": "Dogri",
    "mni": "Manipuri",
    "sat": "Santali",
    "brx": "Bodo",
}


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    if re.search(r"[\u0980-\u09FF]", text):
        return "bn"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te"
    if re.search(r"[\u0A80-\u0AFF]", text):
        return "gu"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml"
    if re.search(r"[\u0A00-\u0A7F]", text):
        return "pa"
    if re.search(r"[\u0B00-\u0B7F]", text):
        return "or"
    if re.search(r"[\u0600-\u06FF]", text):
        return "ur"
    return "en"


def _client():
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=settings.gemini_api_key)
    except Exception as exc:  # pragma: no cover
        log.warning("Gemini client unavailable: %s", exc)
        return None


def generate_json(system: str, user: str) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    prompt = f"{system}\n\nUSER:\n{user}\n\nRespond with a single JSON object only."
    try:
        resp = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        text = (resp.text or "").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.I | re.M).strip()
        return json.loads(text)
    except Exception as exc:
        log.warning("LLM JSON failed: %s", exc)
        return None


def rewrite_in_language(text: str, language: str, sources: list[SourceRef]) -> str:
    if language in ("en", "") or not text:
        return text
    lang_name = INDIC_LANGS.get(language, language)
    cited = "; ".join(f"{s.title} s.{s.section} ({s.published_on})" for s in sources[:4])
    client = _client()
    if not client:
        return text
    prompt = (
        f"Translate the following civic-rights explanation into {lang_name}. "
        "Keep legal citations, Act names, dates, URLs and ₹ amounts unchanged. "
        "Do not add new legal claims.\n\n"
        f"Citations that must remain: {cited}\n\n{text}"
    )
    try:
        resp = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        return (resp.text or text).strip()
    except Exception:
        return text
