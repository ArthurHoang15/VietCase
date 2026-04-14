from __future__ import annotations

from vietcase.schemas.search import SearchPreviewResult
from vietcase.services.source_router import SourceContext, SourceRouter


class SearchService:
    def __init__(self, source_router: SourceRouter) -> None:
        self.source_router = source_router

    def preview(self, filters: dict[str, object], page_index: int = 1, context: SourceContext | None = None) -> SearchPreviewResult:
        ctx = context or SourceContext()
        payload = self.source_router.call("search_preview", ctx, filters, page_index)
        return SearchPreviewResult(
            total_results=int(payload.get("total_results", 0)),
            total_pages=int(payload.get("total_pages", 0)),
            results=list(payload.get("results", [])),
            source_mode=ctx.source_mode,
        )

    def build_job_name(self, filters: dict[str, object]) -> str:
        parts = [
            str(filters.get("case_style") or "Tìm kiếm"),
            str(filters.get("document_type") or "mọi loại"),
        ]
        if filters.get("date_from") or filters.get("date_to"):
            parts.append(f"{filters.get('date_from') or ''}-{filters.get('date_to') or ''}".strip("-"))
        return " | ".join(part for part in parts if part)
