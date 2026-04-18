from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from vietcase.core.text_utils import extract_strong_document_number, normalize_for_search
from vietcase.parsers.compatibility import (
    BASE_URL,
    extract_regex,
    first_present,
    make_document_id,
    normalize_date,
    normalize_label_key,
    normalize_whitespace,
)


class ListingParser:
    def parse(self, html: str, page_index: int = 1) -> dict[str, object]:
        soup = BeautifulSoup(html, "html.parser")
        total_results_text = soup.select_one("#ctl00_Content_home_Public_ctl00_lbl_count_record")
        total_pages_text = soup.select_one("#ctl00_Content_home_Public_ctl00_LbShowtotal")
        total_results = int(extract_regex(r"(\d[\d\.]*)", total_results_text.get_text(" ", strip=True) if total_results_text else "").replace(".", "") or 0)
        total_pages = int(extract_regex(r"(\d+)", total_pages_text.get_text(" ", strip=True) if total_pages_text else "") or 0)

        records: list[dict[str, object]] = []
        anchors = soup.select('#List_group_pub a.echo_id_pub[href*="chi-tiet-ban-an"]')
        for result_index, anchor in enumerate(anchors, start=1):
            item = self._extract_item(anchor)
            if not item:
                continue
            item["page_index"] = page_index
            item["result_index"] = result_index
            records.append(item)
        return {"total_results": total_results, "total_pages": total_pages, "results": records}

    def _extract_item(self, anchor: Tag) -> dict[str, object] | None:
        href = anchor.get("href", "")
        if not href:
            return None

        title_text = normalize_whitespace(anchor.get_text(" ", strip=True))
        heading_label = anchor.select_one("h4.list-group-item-heading label")
        heading_label_text = normalize_whitespace(heading_label.get_text(" ", strip=True)).rstrip(":") if heading_label else ""
        title_block = anchor.select_one("h4.list-group-item-heading span")
        title = normalize_whitespace(title_block.get_text(" ", strip=True)) if title_block else title_text
        scope = self._collect_item_scope(anchor)
        source_card_html = "".join(str(child) for child in (scope.contents or [])) or str(scope)
        source_card_text = normalize_whitespace(scope.get_text(" ", strip=True))

        source_url = urljoin(BASE_URL, href)
        published_date = normalize_date(extract_regex(r"\((\d{2}[\./]\d{2}[\./]\d{4})\)", title_text))
        issued_date = normalize_date(first_present([
            extract_regex(r"ng\u00e0y\s+(\d{1,2}[\./]\d{1,2}[\./]\d{4})", title, flags=re.IGNORECASE),
            extract_regex(r"(\d{1,2}[\./]\d{1,2}[\./]\d{4})", title_text),
        ]))
        document_type = heading_label_text or self._document_type_from_title(title_text)
        document_number = self._extract_document_number(title, title_text)
        court_name = first_present([
            extract_regex(r"c\u1ee7a\s+(.+?)(?:\(|$)", title, flags=re.IGNORECASE),
            extract_regex(r"cua\s+(.+?)(?:\(|$)", title, flags=re.IGNORECASE),
            self._court_name_from_title(title, issued_date),
        ])

        legal_relation = self._extract_labeled_value(scope, ["Quan h\u1ec7 ph\u00e1p lu\u1eadt"])
        adjudication_level = self._extract_labeled_value(scope, ["C\u1ea5p x\u00e9t x\u1eed", "C\u1ea5p gi\u1ea3i quy\u1ebft/x\u00e9t x\u1eed"])
        case_style = self._extract_labeled_value(scope, ["Lo\u1ea1i v\u1ee5/vi\u1ec7c"])
        summary_text = first_present([
            self._extract_labeled_value(scope, ["Th\u00f4ng tin v\u1ec1 v\u1ee5/vi\u1ec7c"]),
            self._extract_description(scope),
        ])
        precedent_applied = self._extract_labeled_value(scope, ["\u00c1p d\u1ee5ng \u00e1n l\u1ec7", "C\u00f3 \u00e1p d\u1ee5ng \u00e1n l\u1ec7"])
        correction_count = self._extract_labeled_value(scope, ["\u0110\u00ednh ch\u00ednh"])
        precedent_vote_count = self._extract_labeled_value(scope, ["T\u1ed5ng s\u1ed1 l\u01b0\u1ee3t \u0111\u01b0\u1ee3c b\u00ecnh ch\u1ecdn l\u00e0m ngu\u1ed3n ph\u00e1t tri\u1ec3n \u00e1n l\u1ec7"])

        return {
            "source_url": source_url,
            "document_id": make_document_id(source_url),
            "title": title,
            "document_type": document_type,
            "document_number": document_number,
            "issued_date": issued_date,
            "published_date": published_date,
            "court_name": court_name,
            "case_style": case_style,
            "legal_relation": legal_relation,
            "adjudication_level": adjudication_level,
            "summary_text": summary_text,
            "precedent_applied": precedent_applied,
            "correction_count": correction_count,
            "precedent_vote_count": precedent_vote_count,
            "source_card_text": source_card_text,
            "source_card_html": source_card_html,
        }

    def _collect_item_scope(self, anchor: Tag) -> Tag:
        parts = [str(anchor)]
        sibling = anchor.next_sibling
        while sibling is not None:
            if isinstance(sibling, Tag) and sibling.name == "a" and "echo_id_pub" in (sibling.get("class") or []):
                break
            if isinstance(sibling, Tag):
                parts.append(str(sibling))
            sibling = sibling.next_sibling
        scope_html = "<div>" + "".join(parts) + "</div>"
        scope_soup = BeautifulSoup(scope_html, "html.parser")
        return scope_soup.div or anchor

    def _extract_labeled_value(self, scope: Tag, labels: list[str]) -> str:
        normalized_labels = {normalize_label_key(label) for label in labels}
        for label in scope.select("label"):
            text = normalize_label_key(label.get_text(" ", strip=True))
            if text not in normalized_labels:
                continue
            parent = label.parent if isinstance(label.parent, Tag) else None
            sibling = label.next_sibling
            while sibling is not None:
                if isinstance(sibling, Tag):
                    value = normalize_whitespace(sibling.get_text(" ", strip=True))
                else:
                    value = normalize_whitespace(str(sibling))
                if value:
                    return value.lstrip(":").strip()
                sibling = sibling.next_sibling
            if parent:
                parent_text = normalize_whitespace(parent.get_text(" ", strip=True))
                raw_label = normalize_whitespace(label.get_text(" ", strip=True)).rstrip(":")
                if parent_text.startswith(raw_label):
                    stripped = normalize_whitespace(parent_text[len(raw_label):].lstrip(":"))
                    if stripped:
                        return stripped
        return ""

    def _extract_description(self, scope: Tag) -> str:
        description = scope.select_one(".Description_pub span") or scope.select_one(".Description_pub")
        if not description:
            return ""
        text = normalize_whitespace(description.get_text(" ", strip=True))
        for prefix in ("Th\u00f4ng tin v\u1ec1 v\u1ee5/vi\u1ec7c:", "Th\u00f4ng tin v\u1ec1 v\u1ee5 \u00e1n:"):
            if text.startswith(prefix):
                return text.replace(prefix, "", 1).strip()
        return text

    def _court_name_from_title(self, title: str, issued_date: str) -> str:
        source = title or ""
        if issued_date:
            parts = issued_date.split("-")
            if len(parts) == 3:
                vn_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                index = source.find(vn_date)
                if index >= 0:
                    source = source[index + len(vn_date):]
        source = source.split("(", 1)[0]
        match = re.search(r"c\u1ee7a\s+(.+)$", source, flags=re.IGNORECASE)
        if match:
            return normalize_whitespace(match.group(1))
        match = re.search(r"cua\s+(.+)$", source, flags=re.IGNORECASE)
        if match:
            return normalize_whitespace(match.group(1))
        return ""

    def _document_type_from_title(self, title: str) -> str:
        normalized = normalize_for_search(title)
        if "quyet dinh" in normalized:
            return "Quy\u1ebft \u0111\u1ecbnh"
        if "ban an" in normalized:
            return "B\u1ea3n \u00e1n"
        return ""

    def _extract_document_number(self, *candidates: str) -> str:
        for candidate in candidates:
            extracted = extract_strong_document_number(candidate)
            if extracted:
                return extracted
        return ""
