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
from vietcase.core.text_utils import sanitize_windows_name


class PdfService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save_pdf(self, pdf_url: str, job_folder: Path, document_number: str = "") -> dict[str, str]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            response = requests.get(pdf_url, timeout=self.settings.request_timeout, verify=False)
        response.raise_for_status()

        pdf_bytes = response.content
        pdf_text = self._extract_pdf_text(pdf_bytes)
        resolved_document_number = self._extract_document_number_from_pdf_text(pdf_text) or document_number.strip()

        job_folder.mkdir(parents=True, exist_ok=True)
        target_name = self._build_file_name(resolved_document_number, pdf_url)
        target_path = self._dedupe_path(job_folder / target_name)
        target_path.write_bytes(pdf_bytes)
        return {
            "pdf_path": str(target_path),
            "file_name_original": target_path.name,
            "pdf_text": pdf_text,
            "resolved_document_number": resolved_document_number,
        }

    def _build_file_name(self, document_number: str, pdf_url: str) -> str:
        if document_number:
            base_name = sanitize_windows_name(document_number.strip(), fallback="document")
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
        patterns = [
            r"Bản\s+án\s+số\s*[:\-]?\s*([^\n\r]+?)\s+ngày",
            r"Quyết\s+định\s+số\s*[:\-]?\s*([^\n\r]+?)\s+ngày",
            r"\bSố\s*[:\-]?\s*([^\n\r]+?)\s+ngày",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = re.sub(r"\s+", " ", match.group(1)).strip(" :.-")
            if value:
                return value
        return ""

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        if not pdf_bytes:
            return ""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
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
