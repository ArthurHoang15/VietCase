from __future__ import annotations

import re
import unicodedata


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
