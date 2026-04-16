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
    normalize_label_text,
    normalize_whitespace,
)


class DetailJudgmentParser:
    def parse(self, html: str, source_url: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        heading = normalize_whitespace(
            first_present([
                soup.select_one('.panel-heading strong').get_text(' ', strip=True) if soup.select_one('.panel-heading strong') else '',
                soup.title.get_text(' ', strip=True) if soup.title else '',
            ])
        )
        return {
            "source_url": source_url,
            "document_id": make_document_id(source_url),
            "document_type": "Bản án",
            "title": first_present([
                self._field(soup, "ten_ban_an"),
                heading,
                extract_regex(r"Tên bản án:\s*([^\n]+)", text),
                extract_regex(r"T?n b?n ?n:\s*([^\n]+)", text),
            ]),
            "document_number": first_present([
                self._field(soup, "so_ban_an"),
                extract_regex(r"số\s+(.+?)\s+ngày", heading, flags=re.IGNORECASE),
                extract_regex(r"s?\s+(.+?)\s+ng?y", heading, flags=re.IGNORECASE),
            ]),
            "issued_date": normalize_date(first_present([
                extract_regex(r"Ngày tuyên án:\s*([^\n]+)", text),
                extract_regex(r"Ng?y tuy?n ?n:\s*([^\n]+)", text),
                self._field(soup, "ngay_ban_hanh"),
                extract_regex(r"ngày\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})", heading, flags=re.IGNORECASE),
            ])),
            "published_date": normalize_date(first_present([
                self._field(soup, "ngay_cong_bo"),
                extract_regex(r"\((\d{1,2}\.\d{1,2}\.\d{4})\)", heading),
            ])),
            "court_name": first_present([
                self._field(soup, "toa_an"),
                extract_regex(r"Tòa án xét xử:\s*([^\n]+)", text),
                extract_regex(r"T?a ?n x?t x?:\s*([^\n]+)", text),
                extract_regex(r"của\s+(.*?)(?:\(\d{2}\.\d{2}\.\d{4}\)|$)", heading, flags=re.IGNORECASE),
                extract_regex(r"c?a\s+(.*?)(?:\(\d{2}\.\d{2}\.\d{4}\)|$)", heading, flags=re.IGNORECASE),
            ]),
            "legal_relation": first_present([
                self._field(soup, "quan_he_phap_luat"),
                extract_regex(r"Quan hệ pháp luật:\s*([^\n]+)", text),
                extract_regex(r"Quan h? ph?p lu?t:\s*([^\n]+)", text),
            ]),
            "adjudication_level": first_present([
                extract_regex(r"Cấp xét xử:\s*([^\n]+)", text),
                extract_regex(r"Cấp giải quyết/xét xử:\s*([^\n]+)", text),
                extract_regex(r"C?p x?t x?:\s*([^\n]+)", text),
                extract_regex(r"C?p gi?i quy?t/x?t x?:\s*([^\n]+)", text),
                self._field(soup, "cap_xet_xu"),
            ]),
            "case_style": first_present([
                extract_regex(r"Loại vụ/việc:\s*([^\n]+)", text),
                extract_regex(r"Lo?i v?/vi?c:\s*([^\n]+)", text),
            ]),
            "summary_text": first_present([
                extract_regex(r"Thông tin về vụ/việc:\s*([^\n]+)", text),
                extract_regex(r"Th?ng tin v? v?/vi?c:\s*([^\n]+)", text),
                normalize_whitespace(text),
            ]),
            "pdf_url": extract_pdf_url_from_soup(soup),
        }

    def _field(self, soup: BeautifulSoup, label_key: str) -> str:
        aliases = [normalize_label_text(alias) for alias in get_aliases(label_key)]
        for li in soup.select("li.list-group-item"):
            text = normalize_label_text(li.get_text(" ", strip=True))
            for alias in aliases:
                if text.startswith(alias):
                    return normalize_whitespace(text[len(alias):].lstrip(":"))
        return ""
