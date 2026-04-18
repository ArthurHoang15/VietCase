from __future__ import annotations

import io
import re
import warnings
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader
from urllib3.exceptions import InsecureRequestWarning

from vietcase.core.config import get_settings
from vietcase.core.text_utils import extract_strong_document_number, is_reliable_document_number, sanitize_windows_name


class PdfService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save_pdf(
        self,
        pdf_url: str,
        job_folder: Path,
        document_number: str = "",
        *,
        title: str = "",
        source_card_text: str = "",
    ) -> dict[str, str]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            response = requests.get(pdf_url, timeout=self.settings.request_timeout, verify=False)
        response.raise_for_status()

        pdf_bytes = response.content
        page_texts = self._extract_pdf_page_texts(pdf_bytes)
        pdf_text = self._join_page_texts(page_texts)
        header_number = self._extract_document_number_from_pdf_text(page_texts[0] if page_texts else "")
        resolved_document_number = self._resolve_document_number(header_number, document_number)

        job_folder.mkdir(parents=True, exist_ok=True)
        fallback_title = self._build_metadata_fallback_name(title, source_card_text)
        target_name = self._build_file_name(resolved_document_number, pdf_url, fallback_title=fallback_title)
        target_path = self._dedupe_path(job_folder / target_name)
        target_path.write_bytes(pdf_bytes)
        return {
            "pdf_path": str(target_path),
            "file_name_original": target_path.name,
            "pdf_text": pdf_text,
            "resolved_document_number": resolved_document_number,
        }

    def _build_file_name(self, document_number: str, pdf_url: str, *, fallback_title: str = "") -> str:
        if document_number:
            base_name = sanitize_windows_name(document_number.strip(), fallback="document")
        elif fallback_title:
            base_name = sanitize_windows_name(fallback_title, fallback="document")
        else:
            base_name = Path(urlparse(pdf_url).path).name or "document.pdf"
            if base_name.lower().endswith(".pdf"):
                base_name = Path(base_name).stem
            base_name = sanitize_windows_name(base_name, fallback="document")
        return f"{base_name}.pdf"

    def _extract_document_number_from_pdf_text(self, pdf_text: str) -> str:
        text = str(pdf_text or "")
        if not text.strip():
            return ""
        search_region = self._document_number_search_region(text)
        patterns = [
            r"Bản\s+án\s+số\s*[:\-]?\s*([^\n\r]{0,220})",
            r"Quyết\s+định\s+số\s*[:\-]?\s*([^\n\r]{0,220})",
            r"\bSố\s*[:\-]?\s*([^\n\r]{0,220})",
        ]
        for pattern in patterns:
            match = re.search(pattern, search_region, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._normalize_candidate_number(match.group(1))
            if value:
                return value
        return ""

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        return self._join_page_texts(self._extract_pdf_page_texts(pdf_bytes))

    def _extract_pdf_page_texts(self, pdf_bytes: bytes) -> list[str]:
        if not pdf_bytes:
            return []
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return parts

    def _join_page_texts(self, parts: list[str]) -> str:
        return re.sub(r"\s+", " ", "\n".join(parts)).strip()

    def _dedupe_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        counter = 1
        while True:
            candidate = path.with_name(f"{stem}__{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _resolve_document_number(self, header_number: str, fallback_document_number: str) -> str:
        for candidate in (header_number, fallback_document_number):
            normalized = self._normalize_candidate_number(candidate)
            if self._is_reliable_document_number(normalized):
                return normalized
        return ""

    def _document_number_search_region(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return ""
        head = normalized[:1000]
        first_number_marker = re.search(
            r"(Bản\s+án\s+số|Quyết\s+định\s+số|\bSố\s*[:\-]?)",
            head,
            flags=re.IGNORECASE,
        )
        if not first_number_marker:
            return head[:240]
        start = first_number_marker.start()
        return head[start : start + 280]

    def _normalize_candidate_number(self, candidate: str) -> str:
        strong = extract_strong_document_number(candidate)
        if strong:
            return strong
        cleaned = re.sub(r"\s+", " ", str(candidate or "")).strip().rstrip(",.;: ")
        cleaned = re.split(
            r"\s+(?:ngày|CỘNG HÒA|Độc lập|QUYẾT ĐỊNH|BẢN ÁN|NHÂN DANH)\b",
            cleaned,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip().rstrip(",.;: ")
        return extract_strong_document_number(cleaned)

    def _is_reliable_document_number(self, candidate: str) -> bool:
        return is_reliable_document_number(candidate)

    def _build_metadata_fallback_name(self, title: str, source_card_text: str) -> str:
        candidate = self._clean_metadata_title(title)
        if candidate:
            return candidate
        if source_card_text:
            first_sentence = re.split(r"\s+(?:Quan hệ pháp luật|Cấp xét xử|Loại vụ/việc|Áp dụng án lệ|Thông tin về vụ/việc)\s*:", source_card_text, maxsplit=1)[0]
            candidate = self._clean_metadata_title(first_sentence)
            if candidate:
                return candidate
        return ""

    def _clean_metadata_title(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return ""
        text = re.sub(r"\(\d{2}[./]\d{2}[./]\d{4}\)\s*$", "", text).strip()
        text = text.rstrip(",.;: ")
        text = re.sub(r"\s+", " ", text)
        if len(text) > 120:
            text = text[:120].rsplit(" ", 1)[0].strip() or text[:120].strip()
        return text
