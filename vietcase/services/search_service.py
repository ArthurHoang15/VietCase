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
        fallback_used = False
        if self._is_invalid_search_state(payload) and ctx.source_mode == "requests":
            fallback_ctx = SourceContext(source_mode="playwright")
            fallback_payload = self.source_router.call("search_preview", fallback_ctx, filters, page_index, None)
            if self._is_invalid_search_state(fallback_payload):
                invalid_fields = ", ".join((fallback_payload.get("state") or {}).get("invalid_fields", [])) or "unknown"
                raise RuntimeError(f"Search filter state invalid after Playwright fallback: {invalid_fields}")
            payload = fallback_payload
            ctx = fallback_ctx
            fallback_used = True
        submitted_values = dict((payload.get("state") or {}).get("values", filters))
        preview_id = str(uuid4())
        self._states[preview_id] = {
            "filters": dict(filters),
            "submitted_values": submitted_values,
            "source_state": payload.get("state", {}),
            "source_mode": ctx.source_mode,
            "baseline_total_results": int(payload.get("total_results", 0)),
            "baseline_total_pages": int(payload.get("total_pages", 0)),
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
        self._write_debug_snapshot("preview", preview_id, result, filters, payload.get("state", {}), submitted_values, self._state_baseline(self._states[preview_id]), fallback_used=fallback_used)
        return result

    def page(self, preview_id: str, page_index: int) -> SearchPreviewResult:
        self._cleanup_states()
        state = self._states[preview_id]
        ctx = SourceContext(source_mode=state.get("source_mode", self.settings.search_source_mode))
        submitted_values = dict(state.get("submitted_values") or state["filters"])
        payload = self.source_router.call("search_preview", ctx, submitted_values, page_index, state.get("source_state"))
        fallback_used = False
        if (self._is_invalid_pagination_state(state, payload, page_index) or self._is_invalid_search_state(payload)) and ctx.source_mode == "requests":
            fallback_ctx = SourceContext(source_mode="playwright")
            try:
                fallback_payload = self.source_router.call("search_preview", fallback_ctx, submitted_values, page_index, state.get("source_state"))
            except Exception:
                fallback_payload = None
            if fallback_payload and not self._is_invalid_pagination_state(state, fallback_payload, page_index) and not self._is_invalid_search_state(fallback_payload):
                payload = fallback_payload
                ctx = fallback_ctx
                fallback_used = True
            elif self._is_invalid_search_state(payload):
                invalid_fields = ", ".join((payload.get("state") or {}).get("invalid_fields", [])) or "unknown"
                raise RuntimeError(f"Search filter state invalid during pagination: {invalid_fields}")
        state["source_state"] = payload.get("state", {})
        state["submitted_values"] = dict((payload.get("state") or {}).get("values", submitted_values))
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
        self._write_debug_snapshot("page", preview_id, result, state["filters"], payload.get("state", {}), state["submitted_values"], self._state_baseline(state), fallback_used=fallback_used)
        return result

    def iter_all_results(self, filters: dict[str, object], context: SourceContext | None = None):
        first = self.preview(filters, page_index=1, context=context)
        yield first
        for page_index in range(2, first.total_pages + 1):
            yield self.page(first.preview_id, page_index)

    def build_job_name(self, filters: dict[str, object]) -> str:
        parts = [str(filters.get("case_style") or "Tìm kiếm"), str(filters.get("document_type") or "mọi loại")]
        if filters.get("date_from") or filters.get("date_to"):
            parts.append(f"{filters.get('date_from') or ''}-{filters.get('date_to') or ''}".strip("-"))
        return " | ".join(part for part in parts if part)

    def _cleanup_states(self) -> None:
        now = datetime.utcnow()
        expired = [key for key, value in self._states.items() if value.get("expires_at") and value["expires_at"] < now]
        for key in expired:
            self._states.pop(key, None)

    def _write_debug_snapshot(
        self,
        stage: str,
        preview_id: str,
        result: SearchPreviewResult,
        filters: dict[str, object],
        source_state: dict[str, object],
        submitted_values: dict[str, object],
        baseline: dict[str, int],
        *,
        fallback_used: bool = False,
    ) -> None:
        if not self.settings.debug_search_snapshots:
            return
        self.settings.debug_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": stage,
            "preview_id": preview_id,
            "filters": filters,
            "submitted_values": submitted_values,
            "source_mode": result.source_mode,
            "effective_source_mode": result.source_mode,
            "baseline_total_results": baseline["total_results"],
            "baseline_total_pages": baseline["total_pages"],
            "returned_total_results": result.total_results,
            "returned_total_pages": result.total_pages,
            "current_page": result.current_page,
            "fallback_used": fallback_used,
            "results": result.results[:5],
            "source_state": {
                "searched": bool(source_state.get("searched")),
                "current_page": source_state.get("current_page"),
                "tls_mode": source_state.get("tls_mode"),
                "values": source_state.get("values", {}),
                "echoed_values": source_state.get("echoed_values", {}),
                "strict_filter_valid": bool(source_state.get("strict_filter_valid", True)),
                "invalid_fields": list(source_state.get("invalid_fields", [])),
                "submitted_alias_names": {
                    logical_key: [str(alias.get("name", "")) for alias in meta.get("aliases", []) if alias.get("name")]
                    for logical_key, meta in (source_state.get("fields", {}) or {}).items()
                },
            },
            "captured_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        target = self.settings.debug_dir / f"{preview_id}_{stage}_{result.current_page}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _state_baseline(self, state: dict[str, object]) -> dict[str, int]:
        return {
            "total_results": int(state.get("baseline_total_results", 0) or 0),
            "total_pages": int(state.get("baseline_total_pages", 0) or 0),
        }

    def _is_invalid_pagination_state(self, state: dict[str, object], payload: dict[str, object], page_index: int) -> bool:
        if page_index <= 1:
            return False
        baseline = self._state_baseline(state)
        returned_total_results = int(payload.get("total_results", 0) or 0)
        returned_total_pages = int(payload.get("total_pages", 0) or 0)
        if baseline["total_results"] and returned_total_results != baseline["total_results"]:
            return True
        if baseline["total_pages"] and returned_total_pages != baseline["total_pages"]:
            return True
        return False

    def _is_invalid_search_state(self, payload: dict[str, object]) -> bool:
        state = payload.get("state") or {}
        return not bool(state.get("strict_filter_valid", True))
