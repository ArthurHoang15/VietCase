from __future__ import annotations

import logging
from contextlib import suppress
from copy import deepcopy
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
    "court_level": ["court"],
    "case_style": ["legal_relation"],
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
        values = dict((state or {}).get("values", {}))
        values[parent_field] = parent_value
        html = self._run_search(values, submit=False)
        self._ensure_not_blocked(html, f'Playwright dependent dropdown blocked for {parent_field}')
        parsed = self.form_parser.parse_form_state(html)
        child_selects = {key: parsed["selects"].get(key, []) for key in DEPENDENT_CHILDREN.get(parent_field, [])}
        return {
            **parsed,
            "selects": child_selects or parsed.get("selects", {}),
            "state": self._build_state(parsed, html, values=values),
        }

    def search_preview(self, filters: dict[str, object], page_index: int = 1, state: dict[str, object] | None = None) -> dict[str, object]:
        html = self._run_search(filters, page_index=page_index, submit=True)
        self._ensure_not_blocked(html, 'Playwright search preview blocked')
        parsed = self.listing_parser.parse(html, page_index=page_index)
        if parsed["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Playwright could not load search results")
        form_state = self.form_parser.parse_form_state(html)
        return {**parsed, "state": self._build_state(form_state, html, values=dict(filters), searched=True, current_page=page_index)}

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
        for key, value in filters.items():
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
        return {
            "hidden_fields": parsed.get("hidden_fields", {}),
            "fields": parsed.get("fields", {}),
            "pagination_name": parsed.get("pagination_name", ""),
            "search_button_name": parsed.get("search_button_name", ""),
            "values": values or {},
            "searched": searched,
            "current_page": current_page,
            "tls_mode": "browser",
            "current_html": html,
        }
