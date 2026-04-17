from __future__ import annotations

import re

from bs4 import BeautifulSoup

from vietcase.parsers.compatibility import (
    extract_pdf_url_from_soup,
    extract_regex,
    first_present,
    get_aliases,
    make_document_id,
    normalize_date,
    normalize_label_key,
    normalize_whitespace,
)


class DetailJudgmentParser:
    def parse(self, html: str, source_url: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        heading = normalize_whitespace(first_present([
            soup.select_one(".panel-heading strong").get_text(" ", strip=True) if soup.select_one(".panel-heading strong") else "",
            soup.title.get_text(" ", strip=True) if soup.title else "",
        ]))
        return {
            "source_url": source_url,
            "document_id": make_document_id(source_url),
            "document_type": "B\u1ea3n \u00e1n",
            "title": first_present([self._field(soup, "ten_ban_an"), heading]),
            "document_number": first_present([
                self._field(soup, "so_ban_an"),
                extract_regex(r"s\u1ed1\s+(.+?)\s+ng\u00e0y", heading, flags=re.IGNORECASE),
            ]),
            "issued_date": normalize_date(first_present([
                self._field(soup, "ngay_ban_hanh"),
                extract_regex(r"ng\u00e0y\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})", heading, flags=re.IGNORECASE),
            ])),
            "published_date": normalize_date(first_present([
                self._field(soup, "ngay_cong_bo"),
                extract_regex(r"\((\d{1,2}\.\d{1,2}\.\d{4})\)", heading),
            ])),
            "court_name": first_present([
                self._field(soup, "toa_an"),
                extract_regex(r"c\u1ee7a\s+(.*?)(?:\(\d{2}\.\d{2}\.\d{4}\)|$)", heading, flags=re.IGNORECASE),
            ]),
            "legal_relation": self._field(soup, "quan_he_phap_luat"),
            "adjudication_level": self._field(soup, "cap_xet_xu"),
            "case_style": self._field_by_labels(soup, ["Loai vu/viec"]),
            "summary_text": first_present([
                self._field_by_labels(soup, ["Thong tin ve vu/viec"]),
                normalize_whitespace(text),
            ]),
            "precedent_applied": first_present([
                self._field(soup, "co_ap_dung_an_le"),
                self._field_by_labels(soup, ["Ap dung an le"]),
            ]),
            "correction_count": self._field_by_labels(soup, ["Dinh chinh"]),
            "precedent_vote_count": self._field_by_labels(soup, ["Tong so luot duoc binh chon lam nguon phat trien an le"]),
            "source_card_text": "",
            "source_card_html": "",
            "pdf_url": extract_pdf_url_from_soup(soup),
        }

    def _field(self, soup: BeautifulSoup, label_key: str) -> str:
        aliases = {normalize_label_key(alias) for alias in get_aliases(label_key)}
        for li in soup.select("li.list-group-item"):
            text = normalize_whitespace(li.get_text(" ", strip=True))
            normalized = normalize_label_key(text)
            if any(normalized.startswith(alias) for alias in aliases):
                parts = text.split(":", 1)
                return normalize_whitespace(parts[1] if len(parts) == 2 else "")
        return ""

    def _field_by_labels(self, soup: BeautifulSoup, labels: list[str]) -> str:
        aliases = {normalize_label_key(label) for label in labels}
        for li in soup.select("li.list-group-item"):
            text = normalize_whitespace(li.get_text(" ", strip=True))
            normalized = normalize_label_key(text)
            if any(normalized.startswith(alias) for alias in aliases):
                parts = text.split(":", 1)
                return normalize_whitespace(parts[1] if len(parts) == 2 else "")
        return ""
