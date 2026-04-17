from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from vietcase.core.config import get_settings


LOGGER = logging.getLogger(__name__)
SEARCH_ACTIONS = {"load_filters", "load_dependent_options", "search_preview"}


class FallbackRequiredError(RuntimeError):
    pass


@dataclass(slots=True)
class SourceContext:
    source_mode: str = "requests"
    job_id: int | None = None


class SourceRouter:
    def __init__(self, requests_client: Any, playwright_client: Any) -> None:
        self.requests_client = requests_client
        self.playwright_client = playwright_client
        self.settings = get_settings()
        self._search_playwright_disabled = False

    def call(self, action: str, context: SourceContext, *args: Any, **kwargs: Any) -> Any:
        if action in SEARCH_ACTIONS:
            preferred_mode = context.source_mode or self.settings.search_source_mode
            if preferred_mode == "playwright" and not self._search_playwright_disabled:
                try:
                    context.source_mode = "playwright"
                    return self._invoke(self.playwright_client, action, *args, **kwargs)
                except Exception as exc:
                    message = str(exc)
                    if "Sync API inside the asyncio loop" in message:
                        self._search_playwright_disabled = True
                    LOGGER.warning(
                        "Search action %s is falling back to requests because Playwright failed: %s",
                        action,
                        exc,
                    )
            context.source_mode = "requests"
            return self._invoke(self.requests_client, action, *args, **kwargs)

        if context.source_mode == "playwright":
            try:
                return self._invoke(self.playwright_client, action, *args, **kwargs)
            except FallbackRequiredError as exc:
                LOGGER.warning(
                    "Playwright mode failed for action %s on job %s; retrying requests: %s",
                    action,
                    context.job_id,
                    exc,
                )
                context.source_mode = "requests"
                return self._invoke(self.requests_client, action, *args, **kwargs)

        try:
            return self._invoke(self.requests_client, action, *args, **kwargs)
        except FallbackRequiredError as exc:
            LOGGER.warning(
                "Requests mode failed for action %s on job %s; trying Playwright: %s",
                action,
                context.job_id,
                exc,
            )
            try:
                result = self._invoke(self.playwright_client, action, *args, **kwargs)
            except Exception as playwright_exc:
                LOGGER.warning(
                    "Playwright fallback also failed for action %s on job %s; keeping requests mode: %s",
                    action,
                    context.job_id,
                    playwright_exc,
                )
                context.source_mode = "requests"
                raise exc
            context.source_mode = "playwright"
            LOGGER.warning("Switching job %s to Playwright because requests failed: %s", context.job_id, exc)
            return result

    def _invoke(self, client: Any, action: str, *args: Any, **kwargs: Any) -> Any:
        method: Callable[..., Any] = getattr(client, action)
        return method(*args, **kwargs)
