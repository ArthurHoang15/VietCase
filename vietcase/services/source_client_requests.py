from __future__ import annotations

import logging
import time
import warnings
from copy import deepcopy
from datetime import datetime
from urllib.parse import urljoin

import requests
from requests import Response
from urllib3.exceptions import InsecureRequestWarning

from vietcase.core.config import get_settings
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from vietcase.services.source_router import FallbackRequiredError


LOGGER = logging.getLogger(__name__)
BASE_URL = "https://congbobanan.toaan.gov.vn"
SEARCH_URL = f"{BASE_URL}/0tat1cvn/ban-an-quyet-dinh"
DEPENDENT_CHILDREN = {
    "court_level": ["court"],
    "case_style": ["legal_relation"],
}


class RequestsSourceClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                )
            }
        )
        self.form_parser = FormParser()
        self.listing_parser = ListingParser()

    def load_filters(self) -> dict[str, object]:
        response, tls_mode = self._request("GET", SEARCH_URL)
        html = self._response_text(response)
        if self._is_blocked(html):
            raise FallbackRequiredError("Search form appears blocked")
        parsed = self.form_parser.parse_form_state(html)
        if not parsed.get("fields"):
            raise FallbackRequiredError("Search form controls missing from HTML")
        return {
            **parsed,
            "state": self._build_state(parsed, html, tls_mode),
            "tls_mode": tls_mode,
        }

    def load_dependent_options(self, parent_field: str, parent_value: str, state: dict[str, object] | None = None) -> dict[str, object]:
        working_state = deepcopy(state) if state else self.load_filters()["state"]
        fields = working_state.get("fields", {})
        if parent_field not in fields:
            return self.load_filters()
        payload = self._base_payload(working_state)
        values = dict(working_state.get("values", {}))
        values[parent_field] = parent_value
        self._apply_values_to_payload(payload, fields, values)
        parent_name = fields[parent_field].get("name", "")
        if parent_name:
            payload["__EVENTTARGET"] = parent_name
            payload["__EVENTARGUMENT"] = ""
        response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=working_state.get("tls_mode", "secure"))
        html = self._response_text(response)
        if self._is_blocked(html):
            raise FallbackRequiredError(f"Dependent options for {parent_field} appear blocked")
        parsed = self.form_parser.parse_form_state(html)
        child_selects = {key: parsed["selects"].get(key, []) for key in DEPENDENT_CHILDREN.get(parent_field, [])}
        working_state.update(self._build_state(parsed, html, tls_mode, values=values))
        return {
            **parsed,
            "selects": child_selects or parsed.get("selects", {}),
            "state": working_state,
            "tls_mode": tls_mode,
        }

    def search_preview(self, filters: dict[str, object], page_index: int = 1, state: dict[str, object] | None = None) -> dict[str, object]:
        working_state = deepcopy(state) if state else self.load_filters()["state"]
        if page_index <= 1 or not working_state.get("searched"):
            payload = self._base_payload(working_state)
            self._apply_values_to_payload(payload, working_state.get("fields", {}), filters)
            search_button_name = working_state.get("search_button_name", "")
            if search_button_name:
                payload[search_button_name] = "Tìm kiếm"
            response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=working_state.get("tls_mode", "secure"))
        else:
            payload = self._base_payload(working_state)
            pagination_name = working_state.get("pagination_name", "")
            if not pagination_name:
                raise FallbackRequiredError("Pagination control missing from requests HTML")
            payload[pagination_name] = str(page_index)
            response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=working_state.get("tls_mode", "secure"))
        html = self._response_text(response)
        if self._is_blocked(html):
            raise FallbackRequiredError("Search results appear blocked")
        result = self.listing_parser.parse(html, page_index=page_index)
        if result["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Search results DOM not present")
        parsed = self.form_parser.parse_form_state(html)
        working_state.update(self._build_state(parsed, html, tls_mode, values=dict(filters), searched=True, current_page=page_index))
        time.sleep(self.settings.rate_limit_ms / 1000)
        return {
            **result,
            "state": working_state,
            "tls_mode": tls_mode,
        }

    def load_detail(self, source_url: str) -> dict[str, object]:
        response, tls_mode = self._request("GET", source_url)
        html = self._response_text(response)
        lowered = html.lower()
        has_detail_markers = any(marker in lowered for marker in ("iframe_pub", ".pdf", "sample.pdf", "title_detai_tab_pub", "list-group-item"))
        if self._is_blocked(html) and not has_detail_markers:
            raise FallbackRequiredError("Detail page appears blocked")
        return {"html": html, "source_url": source_url, "tls_mode": tls_mode}

    def download_pdf(self, pdf_url: str) -> bytes:
        response, _tls_mode = self._request("GET", urljoin(BASE_URL, pdf_url))
        return response.content

    def _base_payload(self, state: dict[str, object]) -> dict[str, object]:
        payload = dict(state.get("hidden_fields", {}))
        payload.setdefault("__EVENTTARGET", "")
        payload.setdefault("__EVENTARGUMENT", "")
        return payload

    def _apply_values_to_payload(self, payload: dict[str, object], fields: dict[str, dict[str, object]], values: dict[str, object]) -> None:
        for logical_key, value in values.items():
            meta = fields.get(logical_key)
            if not meta:
                continue
            name = meta.get("name", "")
            if not name:
                continue
            if isinstance(value, bool):
                if value:
                    payload[name] = "on"
            elif value not in (None, ""):
                payload[name] = self._normalize_form_value(logical_key, value)

    def _normalize_form_value(self, logical_key: str, value: object) -> object:
        if logical_key not in {'date_from', 'date_to'}:
            return value
        text = str(value).strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
            try:
                return datetime.strptime(text, fmt).strftime('%d/%m/%Y')
            except ValueError:
                continue
        return text

    def _build_state(self, parsed: dict[str, object], html: str, tls_mode: str, values: dict[str, object] | None = None, searched: bool = False, current_page: int = 1) -> dict[str, object]:
        return {
            "hidden_fields": parsed.get("hidden_fields", {}),
            "fields": parsed.get("fields", {}),
            "pagination_name": parsed.get("pagination_name", ""),
            "search_button_name": parsed.get("search_button_name", ""),
            "values": values or {},
            "searched": searched,
            "current_page": current_page,
            "tls_mode": tls_mode,
            "current_html": html,
        }

    def _request(self, method: str, url: str, *, tls_mode: str | None = None, **kwargs) -> tuple[Response, str]:
        preferred = tls_mode or ("secure" if self.settings.tls_mode == "auto" else self.settings.tls_mode)
        try:
            if preferred == "compatibility":
                response = self._send(method, url, verify=False, **kwargs)
                return response, "compatibility"
            response = self._send(method, url, verify=True, **kwargs)
            return response, "secure"
        except requests.exceptions.SSLError:
            if self.settings.tls_mode == "strict":
                raise
            LOGGER.warning("TLS verification failed for %s; falling back to compatibility mode", url)
            response = self._send(method, url, verify=False, **kwargs)
            return response, "compatibility"

    def _send(self, method: str, url: str, *, verify: bool, **kwargs) -> Response:
        last_error: Exception | None = None
        for attempt in range(max(1, self.settings.max_retries)):
            try:
                with warnings.catch_warnings():
                    if not verify:
                        warnings.simplefilter("ignore", InsecureRequestWarning)
                    response = self.session.request(method, url, timeout=self.settings.request_timeout, verify=verify, **kwargs)
                response.raise_for_status()
                return response
            except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                if attempt + 1 >= max(1, self.settings.max_retries):
                    raise
                time.sleep(min(1.0 * (attempt + 1), 3.0))
        assert last_error is not None
        raise last_error

    def _response_text(self, response: Response) -> str:
        if response.encoding and response.encoding.lower() not in {"iso-8859-1", "latin-1"}:
            return response.text
        for encoding in ("utf-8", response.apparent_encoding, response.encoding):
            if not encoding:
                continue
            try:
                return response.content.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return response.text

    def _is_blocked(self, html: str) -> bool:
        lowered = html.lower()
        markers = [
            "request blocked",
            "access denied",
            "the url you requested has been blocked",
            "captcha",
            "cloudflare",
        ]
        return any(marker in lowered for marker in markers)

