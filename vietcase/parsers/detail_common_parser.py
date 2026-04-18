from __future__ import annotations

from vietcase.core.text_utils import normalize_for_search
from vietcase.parsers.detail_decision_parser import DetailDecisionParser
from vietcase.parsers.detail_judgment_parser import DetailJudgmentParser


class DetailCommonParser:
    def __init__(self) -> None:
        self.judgment_parser = DetailJudgmentParser()
        self.decision_parser = DetailDecisionParser()

    def parse(self, html: str, source_url: str) -> dict[str, str]:
        lowered = normalize_for_search(html)
        if any(marker in lowered for marker in ("ten quyet dinh", "quyet dinh:", "so quyet dinh")):
            return self.decision_parser.parse(html, source_url)
        if any(marker in lowered for marker in ("ten ban an", "ban an:", "so ban an")):
            return self.judgment_parser.parse(html, source_url)
        if "quyet dinh" in lowered and "ban an" not in lowered:
            return self.decision_parser.parse(html, source_url)
        return self.judgment_parser.parse(html, source_url)
