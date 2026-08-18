from __future__ import annotations

from pathlib import Path


def extract_text(data: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "") for p in reader.pages]
            text = "\n".join(pages).strip()
            if text:
                return text
        except Exception:
            pass
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
        try:
            import io
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            return pytesseract.image_to_string(img, lang="eng+hin") or ""
        except Exception:
            return ""
    return ""
