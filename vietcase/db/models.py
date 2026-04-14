from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DocumentRecord:
    source_url: str
    document_type: str = ""
    document_number: str = ""
    issued_date: str = ""
    published_date: str = ""
    court_level: str = ""
    court_name: str = ""
    adjudication_level: str = ""
    case_style: str = ""
    legal_relation: str = ""
    summary_text: str = ""
    pdf_url: str = ""
    pdf_path: str = ""
    file_name_original: str = ""
    download_status: str = "pending"
    download_error: str = ""
    last_job_id: int | None = None
