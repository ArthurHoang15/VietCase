from __future__ import annotations

import time
from urllib.parse import urljoin

import requests

from vietcase.core.config import get_settings
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from vietcase.services.source_router import FallbackRequiredError


BASE_URL = "https://congbobanan.toaan.gov.vn"
SEARCH_URL = f"{BASE_URL}/0tat1cvn/ban-an-quyet-dinh"


class RequestsSourceClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.verify = False
        self.form_parser = FormParser()
        self.listing_parser = ListingParser()

    def load_filters(self) -> dict[str, object]:
        response = self.session.get(SEARCH_URL, timeout=self.settings.request_timeout)
        html = response.text
        if self._is_blocked(html):
            raise FallbackRequiredError("Search form appears blocked")
        hidden_fields = self.form_parser.parse_hidden_fields(html)
        selects = self.form_parser.parse_select_options(html)
        if not selects:
            raise FallbackRequiredError("Search form options missing from HTML")
        return {"hidden_fields": hidden_fields, "selects": selects}

    def load_dependent_options(self, parent_field: str, parent_value: str) -> dict[str, object]:
        bootstrap = self.load_filters()
        return {"parent_field": parent_field, "parent_value": parent_value, "selects": bootstrap["selects"]}

    def search_preview(self, filters: dict[str, object], page_index: int = 1) -> dict[str, object]:
        bootstrap = self.load_filters()
        payload = dict(bootstrap["hidden_fields"])
        payload.update(self._map_filters(filters))
        payload["ctl00$Content$home$Public$ctl00$cmd_search_banner"] = "Tìm kiếm"
        response = self.session.post(SEARCH_URL, data=payload, timeout=self.settings.request_timeout)
        html = response.text
        if self._is_blocked(html):
            raise FallbackRequiredError("Search results appear blocked")
        result = self.listing_parser.parse(html, page_index=page_index)
        if result["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Search results DOM not present")
        time.sleep(self.settings.rate_limit_ms / 1000)
        return result

    def load_detail(self, source_url: str) -> dict[str, object]:
        response = self.session.get(source_url, timeout=self.settings.request_timeout)
        html = response.text
        if self._is_blocked(html):
            raise FallbackRequiredError("Detail page appears blocked")
        if ".pdf" not in html.lower() and "xuatfile" not in html.lower():
            raise FallbackRequiredError("Detail page missing PDF link in requests mode")
        return {"html": html, "source_url": source_url}

    def download_pdf(self, pdf_url: str) -> bytes:
        response = self.session.get(urljoin(BASE_URL, pdf_url), timeout=self.settings.request_timeout)
        response.raise_for_status()
        return response.content

    def _map_filters(self, filters: dict[str, object]) -> dict[str, object]:
        mapping = {
            "keyword": "ctl00$Content$home$Public$ctl00$txt_key",
            "court_level": "ctl00$Content$home$Public$ctl00$drp_court_level",
            "court": "ctl00$Content$home$Public$ctl00$drp_court",
            "adjudication_level": "ctl00$Content$home$Public$ctl00$drp_adjudication_level",
            "document_type": "ctl00$Content$home$Public$ctl00$drp_document_type",
            "case_style": "ctl00$Content$home$Public$ctl00$drp_case_style",
            "legal_relation": "ctl00$Content$home$Public$ctl00$drp_legal_relation",
            "date_from": "ctl00$Content$home$Public$ctl00$txt_from_date",
            "date_to": "ctl00$Content$home$Public$ctl00$txt_to_date",
            "precedent_applied": "ctl00$Content$home$Public$ctl00$chk_precedent_applied",
            "precedent_voted": "ctl00$Content$home$Public$ctl00$chk_precedent_voted",
        }
        payload: dict[str, object] = {}
        for key, value in filters.items():
            if key not in mapping:
                continue
            if isinstance(value, bool):
                if value:
                    payload[mapping[key]] = "on"
            elif value not in (None, ""):
                payload[mapping[key]] = value
        return payload

    def _is_blocked(self, html: str) -> bool:
        lowered = html.lower()
        markers = ["request blocked", "access denied", "the url you requested has been blocked", "captcha"]
        return any(marker in lowered for marker in markers)
