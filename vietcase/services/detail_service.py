from __future__ import annotations

from vietcase.parsers.detail_common_parser import DetailCommonParser
from vietcase.services.source_router import SourceContext, SourceRouter


class DetailService:
    def __init__(self, source_router: SourceRouter) -> None:
        self.source_router = source_router
        self.parser = DetailCommonParser()

    def fetch(self, source_url: str, context: SourceContext | None = None) -> dict[str, object]:
        ctx = context or SourceContext()
        payload = self.source_router.call("load_detail", ctx, source_url)
        parsed = self.parser.parse(payload["html"], source_url)
        parsed["source_mode"] = ctx.source_mode
        return parsed
