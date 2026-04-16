from __future__ import annotations

from vietcase.parsers.compatibility import normalize_whitespace
from vietcase.parsers.detail_decision_parser import DetailDecisionParser
from vietcase.parsers.detail_judgment_parser import DetailJudgmentParser


class DetailCommonParser:
    def __init__(self) -> None:
        self.judgment_parser = DetailJudgmentParser()
        self.decision_parser = DetailDecisionParser()

    def parse(self, html: str, source_url: str) -> dict[str, str]:
        lowered = normalize_whitespace(html).lower()
        judgment_markers = (
            "tên bản án",
            "bản án: số",
            "t?n b?n ?n",
            "b?n ?n: s?",
        )
        decision_markers = (
            "tên quyết định",
            "quyết định: số",
            "t?n quy?t ??nh",
            "quy?t ??nh: s?",
        )
        if any(marker in lowered for marker in judgment_markers):
            return self.judgment_parser.parse(html, source_url)
        if any(marker in lowered for marker in decision_markers):
            return self.decision_parser.parse(html, source_url)
        if "quyết định" in lowered and "bản án" not in lowered:
            return self.decision_parser.parse(html, source_url)
        return self.judgment_parser.parse(html, source_url)
