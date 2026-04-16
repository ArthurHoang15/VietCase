from __future__ import annotations

import re
import warnings
from pathlib import Path
from urllib.parse import urlparse

import requests
from urllib3.exceptions import InsecureRequestWarning

from vietcase.core.config import get_settings


class PdfService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save_pdf(
        self,
        pdf_url: str,
        court_name: str,
        document_type: str,
        job_folder: Path,
        document_number: str = '',
    ) -> dict[str, str]:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            response = requests.get(pdf_url, timeout=self.settings.request_timeout, verify=False)
        response.raise_for_status()

        court_dir = self._slug(court_name or 'khac')
        doc_dir = self._slug(document_type or 'tai-lieu')
        target_dir = job_folder / court_dir / doc_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target_name = self._build_file_name(document_number, pdf_url)
        target_path = self._dedupe_path(target_dir / target_name)
        target_path.write_bytes(response.content)
        return {
            'pdf_path': str(target_path),
            'file_name_original': target_path.name,
        }

    def _build_file_name(self, document_number: str, pdf_url: str) -> str:
        if document_number:
            base_name = document_number.strip().replace('/', '-').replace('\\', '-')
        else:
            base_name = Path(urlparse(pdf_url).path).name or 'document.pdf'
            if base_name.lower().endswith('.pdf'):
                base_name = Path(base_name).stem
        base_name = re.sub(r'[<>:"/\\|?*]', '-', base_name)
        base_name = re.sub(r'\s+', ' ', base_name).strip().rstrip('. ')
        if not base_name:
            base_name = 'document'
        return f'{base_name}.pdf'

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
        cleaned = re.sub(r'[^A-Za-z0-9\-_. ]+', '', value.strip())
        cleaned = re.sub(r'\s+', '-', cleaned)
        return cleaned.lower() or 'khac'
