from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from vietcase.core.config import get_settings


class PdfService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save_pdf(self, pdf_url: str, court_name: str, document_type: str, job_folder: Path) -> dict[str, str]:
        response = requests.get(pdf_url, timeout=self.settings.request_timeout, verify=False)
        response.raise_for_status()
        court_dir = self._slug(court_name or "khac")
        doc_dir = self._slug(document_type or "tai-lieu")
        target_dir = job_folder / court_dir / doc_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path(urlparse(pdf_url).path).name or "document.pdf"
        target_path = self._dedupe_path(target_dir / original_name)
        target_path.write_bytes(response.content)
        return {
            "pdf_path": str(target_path),
            "file_name_original": original_name,
        }

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

    def _slug(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9\-_. ]+", "", value.strip())
        cleaned = re.sub(r"\s+", "-", cleaned)
        return cleaned.lower() or "khac"
