from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)


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

    def call(self, action: str, context: SourceContext, *args: Any, **kwargs: Any) -> Any:
        if context.source_mode == "playwright":
            client = self.playwright_client
            return self._invoke(client, action, *args, **kwargs)
        try:
            return self._invoke(self.requests_client, action, *args, **kwargs)
        except FallbackRequiredError as exc:
            context.source_mode = "playwright"
            LOGGER.warning("Switching job %s to Playwright because requests failed: %s", context.job_id, exc)
            return self._invoke(self.playwright_client, action, *args, **kwargs)

    def _invoke(self, client: Any, action: str, *args: Any, **kwargs: Any) -> Any:
        method: Callable[..., Any] = getattr(client, action)
        return method(*args, **kwargs)
