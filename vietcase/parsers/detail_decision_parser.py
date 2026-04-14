from __future__ import annotations

from bs4 import BeautifulSoup

from vietcase.parsers.compatibility import extract_pdf_url_from_soup, extract_regex, first_present, get_aliases, make_document_id, normalize_date, normalize_label_text, normalize_whitespace


class DetailDecisionParser:
    def parse(self, html: str, source_url: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        return {
            "source_url": source_url,
            "document_id": make_document_id(source_url),
            "document_type": "Quyết định",
            "title": first_present([self._field(soup, "ten_quyet_dinh"), extract_regex(r"Tên quyết định:\s*([^\n]+)", text)]),
            "document_number": first_present([self._field(soup, "so_quyet_dinh"), extract_regex(r"Số quyết định:\s*([^\n]+)", text)]),
            "issued_date": normalize_date(first_present([self._field(soup, "ngay_ban_hanh"), extract_regex(r"Ngày ban hành:\s*([^\n]+)", text)])),
            "published_date": normalize_date(first_present([self._field(soup, "ngay_cong_bo"), extract_regex(r"Ngày công bố:\s*([^\n]+)", text)])),
            "court_name": first_present([self._field(soup, "toa_an"), extract_regex(r"Tòa án:\s*([^\n]+)", text)]),
            "legal_relation": first_present([self._field(soup, "quan_he_phap_luat"), extract_regex(r"Quan hệ pháp luật:\s*([^\n]+)", text)]),
            "adjudication_level": first_present([self._field(soup, "cap_xet_xu"), extract_regex(r"Cấp giải quyết/xét xử:\s*([^\n]+)", text)]),
            "summary_text": normalize_whitespace(text),
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
