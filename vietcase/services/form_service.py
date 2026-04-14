from __future__ import annotations

from datetime import datetime

from vietcase.db.sqlite import connect, execute, execute_fetchone
from vietcase.schemas.filters import FilterOptions
from vietcase.services.source_router import SourceContext, SourceRouter


class FormService:
    def __init__(self, source_router: SourceRouter) -> None:
        self.source_router = source_router

    def get_bootstrap_filters(self, context: SourceContext | None = None) -> FilterOptions:
        ctx = context or SourceContext()
        payload = self.source_router.call("load_filters", ctx)
        hidden_fields = payload.get("hidden_fields", {})
        selects = payload.get("selects", {})
        self._cache_options(selects)
        return FilterOptions(hidden_fields=hidden_fields, selects=selects, source_mode=ctx.source_mode)

    def get_dependent_options(self, parent_field: str, parent_value: str, context: SourceContext | None = None) -> dict[str, object]:
        ctx = context or SourceContext()
        payload = self.source_router.call("load_dependent_options", ctx, parent_field, parent_value)
        selects = payload.get("selects", {})
        self._cache_options(selects, parent_field=parent_field, parent_value=parent_value)
        return {"selects": selects, "source_mode": ctx.source_mode}

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
