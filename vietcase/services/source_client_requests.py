from __future__ import annotations

import logging
import time
import warnings
from copy import deepcopy
from datetime import datetime
from urllib.parse import urljoin, urlparse

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
    "court_level": ["court", "adjudication_level"],
    "case_style": ["legal_relation"],
}
STRICT_FILTER_KEYS = {
    "court_level",
    "court",
    "adjudication_level",
    "document_type",
    "case_style",
    "legal_relation",
    "date_from",
    "date_to",
    "precedent_applied",
    "precedent_voted",
}


class RequestsSourceClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.session = requests.Session()
        self._tls_mode_by_host: dict[str, str] = {}
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
        values = self._normalize_values(fields, dict(working_state.get("values", {})), include_all_fields=True)
        values[parent_field] = self._normalize_form_value(parent_field, parent_value)
        self._reset_dependent_children(values, parent_field)
        self._apply_values_to_payload(payload, fields, values, include_aliases=False)
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
        values = self._prune_invalid_values(values, parsed.get("fields", {}))
        working_state.update(self._build_state(parsed, html, tls_mode, values=values))
        return {
            **parsed,
            "selects": child_selects or parsed.get("selects", {}),
            "state": working_state,
            "tls_mode": tls_mode,
        }

    def search_preview(self, filters: dict[str, object], page_index: int = 1, state: dict[str, object] | None = None) -> dict[str, object]:
        working_state = deepcopy(state) if state else self.load_filters()["state"]
        fields = working_state.get("fields", {})
        if page_index <= 1 or not working_state.get("searched"):
            working_state, submitted_values = self._prepare_search_state_for_submit(filters, working_state)
            fields = working_state.get("fields", {})
            payload = self._base_payload(working_state)
            self._apply_values_to_payload(payload, fields, submitted_values, include_aliases=True)
            search_button_name = working_state.get("search_button_name", "")
            if search_button_name:
                payload[search_button_name] = "Tìm kiếm"
            response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=working_state.get("tls_mode", "secure"))
        else:
            submitted_values = self._normalize_values(fields, dict(working_state.get("values", {})) or filters, include_all_fields=True)
            payload = self._base_payload(working_state)
            self._apply_values_to_payload(payload, fields, submitted_values, include_aliases=True)
            pagination_name = working_state.get("pagination_name", "")
            if not pagination_name:
                raise FallbackRequiredError("Pagination control missing from requests HTML")
            payload["__EVENTTARGET"] = pagination_name
            payload["__EVENTARGUMENT"] = ""
            payload[pagination_name] = str(page_index)
            response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=working_state.get("tls_mode", "secure"))
        html = self._response_text(response)
        if self._is_blocked(html):
            raise FallbackRequiredError("Search results appear blocked")
        result = self.listing_parser.parse(html, page_index=page_index)
        if result["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Search results DOM not present")
        parsed = self.form_parser.parse_form_state(html)
        working_state.update(self._build_state(parsed, html, tls_mode, values=submitted_values, searched=True, current_page=page_index))
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

    def warm_up_tls_cache(self, url: str = SEARCH_URL) -> str | None:
        try:
            response, tls_mode = self._request("GET", url, stream=True)
        except Exception as exc:
            LOGGER.warning("Warm-up request failed for %s: %s", url, exc)
            return None
        if getattr(response, "raw", None) is not None:
            response.close()
        LOGGER.info("Warm-up request completed for %s using %s mode", url, tls_mode)
        return tls_mode

    def _base_payload(self, state: dict[str, object]) -> dict[str, object]:
        payload = dict(state.get("hidden_fields", {}))
        payload.setdefault("__EVENTTARGET", "")
        payload.setdefault("__EVENTARGUMENT", "")
        return payload

    def _apply_values_to_payload(
        self,
        payload: dict[str, object],
        fields: dict[str, dict[str, object]],
        values: dict[str, object],
        *,
        include_aliases: bool,
    ) -> None:
        for logical_key, value in values.items():
            meta = fields.get(logical_key)
            if not meta:
                continue
            names = self._resolve_field_names(meta, include_aliases=include_aliases)
            if not names:
                continue
            if isinstance(value, bool):
                if value:
                    for name in names:
                        payload[name] = "on"
                continue
            normalized_value = self._normalize_form_value(logical_key, value) if value not in (None, "") else ""
            for name in names:
                payload[name] = normalized_value

    def _normalize_values(
        self,
        fields: dict[str, dict[str, object]],
        values: dict[str, object],
        *,
        include_all_fields: bool = False,
    ) -> dict[str, object]:
        normalized: dict[str, object] = {}
        if include_all_fields:
            for logical_key, meta in fields.items():
                normalized[logical_key] = False if meta.get("kind") == "checkbox" else ""
        for logical_key, value in values.items():
            if isinstance(value, bool):
                normalized[logical_key] = value
                continue
            if value in (None, ""):
                normalized[logical_key] = ""
                continue
            normalized[logical_key] = self._normalize_form_value(logical_key, value)
        return normalized

    def _reset_dependent_children(self, values: dict[str, object], parent_field: str) -> None:
        for child_key in DEPENDENT_CHILDREN.get(parent_field, []):
            values.pop(child_key, None)

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

    def _prepare_search_state_for_submit(self, filters: dict[str, object], state: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        working_state = deepcopy(state)
        fields = working_state.get("fields", {})
        values = self._normalize_values(fields, filters, include_all_fields=True)
        for parent_field in ("court_level", "case_style"):
            parent_value = values.get(parent_field, "")
            if not parent_value or parent_field not in fields:
                continue
            working_state = self._postback_field(working_state, parent_field, values)
            fields = working_state.get("fields", {})
            values = self._prune_invalid_values(values, fields)
        return working_state, values

    def _postback_field(self, state: dict[str, object], parent_field: str, values: dict[str, object]) -> dict[str, object]:
        payload = self._base_payload(state)
        fields = state.get("fields", {})
        self._apply_values_to_payload(payload, fields, values, include_aliases=False)
        parent_name = fields.get(parent_field, {}).get("name", "")
        if parent_name:
            payload["__EVENTTARGET"] = parent_name
            payload["__EVENTARGUMENT"] = ""
        response, tls_mode = self._request("POST", SEARCH_URL, data=payload, tls_mode=state.get("tls_mode", "secure"))
        html = self._response_text(response)
        parsed = self.form_parser.parse_form_state(html)
        return self._build_state(parsed, html, tls_mode, values=values)

    def _build_state(self, parsed: dict[str, object], html: str, tls_mode: str, values: dict[str, object] | None = None, searched: bool = False, current_page: int = 1) -> dict[str, object]:
        submitted_values = values or {}
        echoed_values = self._extract_echoed_values(parsed.get("fields", {}))
        strict_filter_valid, invalid_fields = self._validate_echoed_values(submitted_values, echoed_values)
        return {
            "hidden_fields": parsed.get("hidden_fields", {}),
            "fields": parsed.get("fields", {}),
            "pagination_name": parsed.get("pagination_name", ""),
            "search_button_name": parsed.get("search_button_name", ""),
            "values": submitted_values,
            "echoed_values": echoed_values,
            "strict_filter_valid": strict_filter_valid,
            "invalid_fields": invalid_fields,
            "searched": searched,
            "current_page": current_page,
            "tls_mode": tls_mode,
            "current_html": html,
        }

    def _prune_invalid_values(self, values: dict[str, object], fields: dict[str, dict[str, object]]) -> dict[str, object]:
        pruned = dict(values)
        for logical_key, meta in fields.items():
            if meta.get("kind") != "select":
                continue
            current = pruned.get(logical_key, "")
            if current in ("", None):
                continue
            allowed = {str(option.get("value", "")) for option in meta.get("options", [])}
            if str(current) not in allowed:
                pruned[logical_key] = ""
        return pruned

    def _extract_echoed_values(self, fields: dict[str, dict[str, object]]) -> dict[str, object]:
        echoed: dict[str, object] = {}
        for logical_key, meta in fields.items():
            if meta.get("kind") == "checkbox":
                echoed[logical_key] = bool(meta.get("checked", False))
                continue
            echoed[logical_key] = self._normalize_form_value(logical_key, meta.get("current_value", ""))
        return echoed

    def _validate_echoed_values(self, submitted_values: dict[str, object], echoed_values: dict[str, object]) -> tuple[bool, list[str]]:
        invalid_fields: list[str] = []
        for logical_key in STRICT_FILTER_KEYS:
            submitted = submitted_values.get(logical_key)
            if submitted in (None, "", False):
                continue
            echoed = echoed_values.get(logical_key, False if isinstance(submitted, bool) else "")
            if isinstance(submitted, bool):
                if bool(submitted) != bool(echoed):
                    invalid_fields.append(logical_key)
                continue
            normalized_submitted = str(self._normalize_form_value(logical_key, submitted)).strip()
            normalized_echoed = str(self._normalize_form_value(logical_key, echoed)).strip()
            if normalized_submitted != normalized_echoed:
                invalid_fields.append(logical_key)
        return len(invalid_fields) == 0, invalid_fields

    def _resolve_field_names(self, meta: dict[str, object], *, include_aliases: bool) -> list[str]:
        names: list[str] = []
        primary_name = str(meta.get("name", ""))
        if primary_name and primary_name not in names:
            names.append(primary_name)
        if not include_aliases:
            return names
        for alias in meta.get("aliases", []):
            name = str(alias.get("name", ""))
            if name and name not in names:
                names.append(name)
        return names

    def _request(self, method: str, url: str, *, tls_mode: str | None = None, **kwargs) -> tuple[Response, str]:
        host = urlparse(url).netloc
        cached_tls_mode = self._tls_mode_by_host.get(host)
        preferred = tls_mode or cached_tls_mode or ("secure" if self.settings.tls_mode == "auto" else self.settings.tls_mode)
        try:
            if preferred == "compatibility":
                response = self._send(method, url, verify=False, **kwargs)
                if host:
                    self._tls_mode_by_host[host] = "compatibility"
                return response, "compatibility"
            response = self._send(method, url, verify=True, **kwargs)
            if host and preferred != "compatibility":
                self._tls_mode_by_host.pop(host, None)
            return response, "secure"
        except requests.exceptions.SSLError:
            if self.settings.tls_mode == "strict":
                raise
            LOGGER.warning("TLS verification failed for %s; falling back to compatibility mode", url)
            response = self._send(method, url, verify=False, **kwargs)
            if host:
                self._tls_mode_by_host[host] = "compatibility"
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

