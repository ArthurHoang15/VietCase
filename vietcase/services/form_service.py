from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from vietcase.core.config import get_settings
from vietcase.db.sqlite import connect, execute_fetchone
from vietcase.schemas.filters import FilterOptions
from vietcase.services.source_router import SourceContext, SourceRouter


DEPENDENT_CHILDREN = {
    "court_level": ["court"],
    "case_style": ["legal_relation"],
}


class FormService:
    def __init__(self, source_router: SourceRouter) -> None:
        self.source_router = source_router
        self.settings = get_settings()
        self._states: dict[str, dict[str, object]] = {}

    def get_bootstrap_filters(self, context: SourceContext | None = None) -> FilterOptions:
        self._cleanup_states()
        ctx = context or SourceContext(source_mode=self.settings.search_source_mode)
        payload = self.source_router.call("load_filters", ctx)
        hidden_fields = payload.get("hidden_fields", {})
        fields = payload.get("fields", {})
        selects = payload.get("selects", {})
        self._cache_options(selects)
        form_state_id = self._save_state({
            "source_state": payload.get("state", {}),
            "source_mode": ctx.source_mode,
            "values": {},
        })
        return FilterOptions(hidden_fields=hidden_fields, fields=fields, selects=selects, source_mode=ctx.source_mode, form_state_id=form_state_id)

    def get_dependent_options(self, parent_field: str, parent_value: str, form_state_id: str, context: SourceContext | None = None) -> dict[str, object]:
        self._cleanup_states()
        state = self._states.get(form_state_id)
        ctx = context or SourceContext(source_mode=(state or {}).get("source_mode", self.settings.search_source_mode))
        source_state = (state or {}).get("source_state")
        payload = self.source_router.call("load_dependent_options", ctx, parent_field, parent_value, source_state)
        selects = payload.get("selects", {})
        fields = payload.get("fields", {})
        values = dict((payload.get("state") or {}).get("values") or (state or {}).get("values", {}))
        values[parent_field] = parent_value
        for child_key in DEPENDENT_CHILDREN.get(parent_field, []):
            values.pop(child_key, None)
        next_source_state = dict(payload.get("state", {}))
        if next_source_state is not None:
            next_source_state["values"] = values
        self._states[form_state_id] = {
            "source_state": next_source_state,
            "source_mode": ctx.source_mode,
            "values": values,
            "expires_at": datetime.utcnow() + timedelta(seconds=self.settings.preview_state_ttl_seconds),
        }
        self._cache_options(selects, parent_field=parent_field, parent_value=parent_value)
        return {"selects": selects, "fields": fields, "source_mode": ctx.source_mode, "form_state_id": form_state_id}

    def get_state(self, form_state_id: str) -> dict[str, object] | None:
        self._cleanup_states()
        return self._states.get(form_state_id)

    def _save_state(self, state: dict[str, object]) -> str:
        state_id = str(uuid4())
        self._states[state_id] = {
            **state,
            "expires_at": datetime.utcnow() + timedelta(seconds=self.settings.preview_state_ttl_seconds),
        }
        return state_id

    def _cleanup_states(self) -> None:
        now = datetime.utcnow()
        expired = [key for key, value in self._states.items() if value.get("expires_at") and value["expires_at"] < now]
        for key in expired:
            self._states.pop(key, None)

    def _cache_options(self, selects: dict[str, list[dict[str, str]]], parent_field: str | None = None, parent_value: str | None = None) -> None:
        fetched_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with connect() as conn:
            for group_key, options in selects.items():
                conn.execute(
                    "DELETE FROM filter_option_cache WHERE group_key = ? AND COALESCE(parent_key,'') = ? AND COALESCE(parent_value,'') = ?",
                    (group_key, parent_field or "", parent_value or ""),
                )
                for idx, option in enumerate(options):
                    conn.execute(
                        "INSERT INTO filter_option_cache (group_key, parent_key, parent_value, option_value, option_label, sort_order, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (group_key, parent_field, parent_value, option.get("value", ""), option.get("label", ""), idx, fetched_at),
                    )
            conn.commit()

    def get_cached_options(self) -> dict[str, list[dict[str, str]]]:
        rows = execute_fetchone("SELECT COUNT(*) AS count FROM filter_option_cache")
        if not rows or int(rows["count"]) == 0:
            return {}
        grouped: dict[str, list[dict[str, str]]] = {}
        with connect() as conn:
            cursor = conn.execute("SELECT group_key, option_value, option_label FROM filter_option_cache ORDER BY group_key, sort_order")
            for row in cursor.fetchall():
                grouped.setdefault(row["group_key"], []).append({"value": row["option_value"], "label": row["option_label"]})
        return grouped
