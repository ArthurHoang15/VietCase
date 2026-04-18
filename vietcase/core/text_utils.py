from __future__ import annotations

import re
import unicodedata


STRONG_DOCUMENT_NUMBER_RE = re.compile(
    r"\b\d+(?:\s*[A-Za-zĐđ]+)?/\d{4}/[0-9A-Za-zÀ-ỹ.-]+(?:/[0-9A-Za-zÀ-ỹ.-]+)*\b"
)


def strip_accents(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_for_search(value: str | None) -> str:
    text = strip_accents(str(value or "")).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_search_text(parts: list[str | None]) -> str:
    return normalize_for_search(" ".join(str(part or "") for part in parts if str(part or "").strip()))


def sanitize_windows_name(value: str, fallback: str = "document") -> str:
    cleaned = str(value or "").replace("/", "-").replace("\\", "-")
    cleaned = re.sub(r'[<>:"/\\|?*]', '-', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().rstrip('. ')
    return cleaned or fallback


def extract_strong_document_number(value: str | None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().rstrip(",.;: ")
    if not text:
        return ""
    match = STRONG_DOCUMENT_NUMBER_RE.search(text)
    return match.group(0).strip().rstrip(",.;: ") if match else ""


def is_reliable_document_number(value: str | None) -> bool:
    return bool(extract_strong_document_number(value))


def infer_document_type(*values: str | None) -> str:
    normalized_values = [normalize_for_search(value) for value in values if str(value or "").strip()]
    for text in normalized_values:
        if "ban an" in text and "quyet dinh" not in text:
            return "Bản án"
        if "quyet dinh" in text and "ban an" not in text:
            return "Quyết định"
    for value in values:
        raw = str(value or "").strip()
        if raw in {"Bản án", "Quyết định"}:
            return raw
    return ""
