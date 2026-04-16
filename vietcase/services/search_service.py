from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

from vietcase.core.config import get_settings
from vietcase.schemas.search import SearchPreviewResult
from vietcase.services.source_router import SourceContext, SourceRouter


class SearchService:
    def __init__(self, source_router: SourceRouter) -> None:
        self.source_router = source_router
        self.settings = get_settings()
        self._states: dict[str, dict[str, object]] = {}

    def preview(self, filters: dict[str, object], page_index: int = 1, context: SourceContext | None = None) -> SearchPreviewResult:
        self._cleanup_states()
        ctx = context or SourceContext(source_mode=self.settings.search_source_mode)
        payload = self.source_router.call("search_preview", ctx, filters, page_index, None)
        preview_id = str(uuid4())
        self._states[preview_id] = {
            "filters": dict(filters),
            "source_state": payload.get("state", {}),
            "source_mode": ctx.source_mode,
            "expires_at": datetime.utcnow() + timedelta(seconds=self.settings.preview_state_ttl_seconds),
        }
        result = SearchPreviewResult(
            total_results=int(payload.get("total_results", 0)),
            total_pages=int(payload.get("total_pages", 0)),
            results=list(payload.get("results", [])),
            source_mode=ctx.source_mode,
            preview_id=preview_id,
            current_page=page_index,
        )
        self._write_debug_snapshot("preview", preview_id, result, filters, payload.get("state", {}))
        return result

    def page(self, preview_id: str, page_index: int) -> SearchPreviewResult:
        self._cleanup_states()
        state = self._states[preview_id]
        ctx = SourceContext(source_mode=state.get("source_mode", self.settings.search_source_mode))
        payload = self.source_router.call("search_preview", ctx, state["filters"], page_index, state.get("source_state"))
        state["source_state"] = payload.get("state", {})
        state["source_mode"] = ctx.source_mode
        state["expires_at"] = datetime.utcnow() + timedelta(seconds=self.settings.preview_state_ttl_seconds)
        result = SearchPreviewResult(
            total_results=int(payload.get("total_results", 0)),
            total_pages=int(payload.get("total_pages", 0)),
            results=list(payload.get("results", [])),
            source_mode=ctx.source_mode,
            preview_id=preview_id,
            current_page=page_index,
        )
        self._write_debug_snapshot("page", preview_id, result, state["filters"], payload.get("state", {}))
        return result

    def iter_all_results(self, filters: dict[str, object], context: SourceContext | None = None):
        first = self.preview(filters, page_index=1, context=context)
        yield first
        for page_index in range(2, first.total_pages + 1):
            yield self.page(first.preview_id, page_index)

    def build_job_name(self, filters: dict[str, object]) -> str:
        parts = [
            str(filters.get("case_style") or "T?m ki?m"),
            str(filters.get("document_type") or "m?i lo?i"),
        ]
        if filters.get("date_from") or filters.get("date_to"):
            parts.append(f"{filters.get('date_from') or ''}-{filters.get('date_to') or ''}".strip("-"))
        return " | ".join(part for part in parts if part)

    def _cleanup_states(self) -> None:
        now = datetime.utcnow()
        expired = [key for key, value in self._states.items() if value.get("expires_at") and value["expires_at"] < now]
        for key in expired:
            self._states.pop(key, None)

    def _write_debug_snapshot(self, stage: str, preview_id: str, result: SearchPreviewResult, filters: dict[str, object], source_state: dict[str, object]) -> None:
        if not self.settings.debug_search_snapshots:
            return
        self.settings.debug_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": stage,
            "preview_id": preview_id,
            "filters": filters,
            "source_mode": result.source_mode,
            "total_results": result.total_results,
            "total_pages": result.total_pages,
            "current_page": result.current_page,
            "results": result.results[:5],
            "source_state": {
                "searched": bool(source_state.get("searched")),
                "current_page": source_state.get("current_page"),
                "tls_mode": source_state.get("tls_mode"),
                "values": source_state.get("values", {}),
            },
            "captured_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        target = self.settings.debug_dir / f"{preview_id}_{stage}_{result.current_page}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
