from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from vietcase.core.config import get_settings
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from vietcase.services.source_router import FallbackRequiredError


LOGGER = logging.getLogger(__name__)
BASE_URL = "https://congbobanan.toaan.gov.vn"
SEARCH_URL = f"{BASE_URL}/0tat1cvn/ban-an-quyet-dinh"
SEARCH_BUTTON_ID = "#ctl00_Content_home_Public_ctl00_cmd_search_banner"
PROFESSION_MODAL_ID = "#popModal"
PROFESSION_RADIO_ID = "#ctl00_Feedback_Home_Radio_STYLE_9"
PROFESSION_SAVE_ID = "#ctl00_Feedback_Home_cmdSave_Regis"
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


class PlaywrightSourceClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.form_parser = FormParser()
        self.listing_parser = ListingParser()

    def load_filters(self) -> dict[str, object]:
        html = self._fetch_page_html(SEARCH_URL)
        self._ensure_not_blocked(html, 'Playwright bootstrap blocked')
        parsed = self.form_parser.parse_form_state(html)
        if not parsed.get('fields') or not any(parsed.get('selects', {}).values()):
            raise FallbackRequiredError('Playwright bootstrap missing form controls')
        return {**parsed, "state": self._build_state(parsed, html)}

    def load_dependent_options(self, parent_field: str, parent_value: str, state: dict[str, object] | None = None) -> dict[str, object]:
        values = self._normalize_values(dict((state or {}).get("values", {})), include_all_fields=True)
        values[parent_field] = self._normalize_form_value(parent_field, parent_value)
        self._reset_dependent_children(values, parent_field)
        html = self._run_search(values, submit=False)
        self._ensure_not_blocked(html, f'Playwright dependent dropdown blocked for {parent_field}')
        parsed = self.form_parser.parse_form_state(html)
        child_selects = {key: parsed["selects"].get(key, []) for key in DEPENDENT_CHILDREN.get(parent_field, [])}
        values = self._prune_invalid_values(values, parsed.get("fields", {}))
        return {
            **parsed,
            "selects": child_selects or parsed.get("selects", {}),
            "state": self._build_state(parsed, html, values=values),
        }

    def search_preview(
        self,
        filters: dict[str, object],
        page_index: int = 1,
        state: dict[str, object] | None = None,
        *,
        throttle_ms: int | None = None,
    ) -> dict[str, object]:
        submitted_values = self._normalize_values(
            dict((state or {}).get("values", {})) or dict(filters),
            include_all_fields=True,
        ) if page_index > 1 and state else self._normalize_values(dict(filters), include_all_fields=True)
        html = self._run_search(submitted_values, page_index=page_index, submit=True)
        self._ensure_not_blocked(html, 'Playwright search preview blocked')
        parsed = self.listing_parser.parse(html, page_index=page_index)
        if parsed["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Playwright could not load search results")
        form_state = self.form_parser.parse_form_state(html)
        return {**parsed, "state": self._build_state(form_state, html, values=submitted_values, searched=True, current_page=page_index)}

    def load_detail(self, source_url: str) -> dict[str, object]:
        html = self._fetch_page_html(source_url)
        self._ensure_not_blocked(html, 'Playwright detail blocked')
        return {"html": html, "source_url": source_url}

    def _fetch_page_html(self, url: str) -> str:
        with sync_playwright() as playwright:
            browser = getattr(playwright, self.settings.playwright_browser).launch(headless=True)
            page = browser.new_page(ignore_https_errors=True)
            page.goto(url, wait_until="networkidle", timeout=self.settings.request_timeout * 1000)
            self._dismiss_profession_modal(page)
            html = page.content()
            browser.close()
            return html

    def _run_search(self, filters: dict[str, object], page_index: int = 1, submit: bool = True) -> str:
        with sync_playwright() as playwright:
            browser = getattr(playwright, self.settings.playwright_browser).launch(headless=True)
            page = browser.new_page(ignore_https_errors=True)
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=self.settings.request_timeout * 1000)
            self._dismiss_profession_modal(page)
            parsed = self.form_parser.parse_form_state(page.content())
            self._apply_filters(page, parsed.get("fields", {}), filters)
            if submit:
                page.locator(SEARCH_BUTTON_ID).click()
                page.wait_for_load_state("networkidle")
                self._go_to_page(page, page_index)
            else:
                page.wait_for_load_state("networkidle")
            html = page.content()
            browser.close()
            return html

    def _dismiss_profession_modal(self, page: Any) -> None:
        with suppress(PlaywrightTimeoutError):
            page.wait_for_selector(PROFESSION_MODAL_ID, timeout=1500)
            if page.locator(PROFESSION_RADIO_ID).count():
                page.check(PROFESSION_RADIO_ID)
            if page.locator(PROFESSION_SAVE_ID).count():
                page.click(PROFESSION_SAVE_ID)
                page.wait_for_load_state("networkidle")

    def _apply_filters(self, page: Any, fields: dict[str, dict[str, object]], filters: dict[str, object]) -> None:
        normalized_filters = self._normalize_values(dict(filters), include_all_fields=True)
        ordered_keys = [
            "keyword",
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
        ]
        for key in ordered_keys:
            value = normalized_filters.get(key, "")
            meta = fields.get(key)
            if not meta or value in (None, "", False):
                continue
            locator = page.locator(meta.get("selector", ""))
            if not locator.count():
                continue
            kind = meta.get("kind")
            if kind == "select":
                locator.select_option(str(value))
                page.wait_for_load_state("networkidle")
            elif kind == "checkbox" and value:
                locator.check()
            else:
                locator.fill(str(value))

    def _normalize_values(self, values: dict[str, object], *, include_all_fields: bool = False) -> dict[str, object]:
        normalized: dict[str, object] = {}
        if include_all_fields:
            normalized = {
                "keyword": "",
                "court_level": "",
                "court": "",
                "adjudication_level": "",
                "document_type": "",
                "case_style": "",
                "legal_relation": "",
                "date_from": "",
                "date_to": "",
                "precedent_applied": False,
                "precedent_voted": False,
            }
        for key, value in values.items():
            if isinstance(value, bool):
                normalized[key] = value
                continue
            if value in (None, ""):
                normalized[key] = ""
                continue
            normalized[key] = self._normalize_form_value(key, value)
        return normalized

    def _reset_dependent_children(self, values: dict[str, object], parent_field: str) -> None:
        for child_key in DEPENDENT_CHILDREN.get(parent_field, []):
            values.pop(child_key, None)

    def _normalize_form_value(self, logical_key: str, value: object) -> object:
        if logical_key not in {"date_from", "date_to"}:
            return value
        text = str(value).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return text

    def _go_to_page(self, page: Any, page_index: int) -> None:
        if page_index <= 1:
            return
        drop = page.locator("#ctl00_Content_home_Public_ctl00_DropPages")
        if drop.count():
            drop.select_option(str(page_index))
            page.wait_for_load_state("networkidle")
            return
        next_button = page.locator("#ctl00_Content_home_Public_ctl00_cmdnext")
        current_page = 1
        while current_page < page_index and next_button.count():
            next_button.click()
            page.wait_for_load_state("networkidle")
            current_page += 1


    def _ensure_not_blocked(self, html: str, message: str) -> None:
        lowered = html.lower()
        blocked_markers = [
            'web page blocked',
            'the url you requested has been blocked',
            'access denied',
            'captcha',
            'cloudflare',
        ]
        if any(marker in lowered for marker in blocked_markers):
            raise FallbackRequiredError(message)

    def _build_state(self, parsed: dict[str, object], html: str, values: dict[str, object] | None = None, searched: bool = False, current_page: int = 1) -> dict[str, object]:
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
            "tls_mode": "browser",
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
