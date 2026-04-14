from __future__ import annotations

from vietcase.parsers.detail_decision_parser import DetailDecisionParser
from vietcase.parsers.detail_judgment_parser import DetailJudgmentParser


class DetailCommonParser:
    def __init__(self) -> None:
        self.judgment_parser = DetailJudgmentParser()
        self.decision_parser = DetailDecisionParser()

    def parse(self, html: str, source_url: str) -> dict[str, str]:
        lowered = html.lower()
        if "tên quyết định" in lowered or "tãªn quyáº¿t Ä‘á»‹nh" in lowered or "quyết định" in lowered:
            return self.decision_parser.parse(html, source_url)
        return self.judgment_parser.parse(html, source_url)
