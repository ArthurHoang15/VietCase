from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchFilters:
    keyword: str = ""
    court_level: str = ""
    court: str = ""
    adjudication_level: str = ""
    document_type: str = ""
    case_style: str = ""
    legal_relation: str = ""
    date_from: str = ""
    date_to: str = ""
    precedent_applied: bool = False
    precedent_voted: bool = False


@dataclass(slots=True)
class SearchPreviewResult:
    total_results: int = 0
    total_pages: int = 0
    results: list[dict] = field(default_factory=list)
    source_mode: str = "requests"
    preview_id: str = ""
    current_page: int = 1
