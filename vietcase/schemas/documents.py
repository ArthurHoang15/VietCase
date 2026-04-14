from dataclasses import dataclass


@dataclass(slots=True)
class DocumentView:
    id: int
    source_url: str
    document_type: str
    document_number: str
    court_name: str
    pdf_path: str
    download_status: str
