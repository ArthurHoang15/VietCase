from __future__ import annotations

import logging
from contextlib import suppress
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


class PlaywrightSourceClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.form_parser = FormParser()
        self.listing_parser = ListingParser()

    def load_filters(self) -> dict[str, object]:
        html = self._fetch_page_html(SEARCH_URL)
        return {
            "hidden_fields": self.form_parser.parse_hidden_fields(html),
            "selects": self.form_parser.parse_select_options(html),
        }

    def load_dependent_options(self, parent_field: str, parent_value: str) -> dict[str, object]:
        return self.load_filters()

    def search_preview(self, filters: dict[str, object], page_index: int = 1) -> dict[str, object]:
        html = self._run_search(filters)
        parsed = self.listing_parser.parse(html, page_index=page_index)
        if parsed["total_results"] == 0 and "List_group_pub" not in html:
            raise FallbackRequiredError("Playwright could not load search results")
        return parsed

    def load_detail(self, source_url: str) -> dict[str, object]:
        html = self._fetch_page_html(source_url)
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

    def _run_search(self, filters: dict[str, object]) -> str:
        with sync_playwright() as playwright:
            browser = getattr(playwright, self.settings.playwright_browser).launch(headless=True)
            page = browser.new_page(ignore_https_errors=True)
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=self.settings.request_timeout * 1000)
            self._dismiss_profession_modal(page)
            self._apply_filters(page, filters)
            page.click(SEARCH_BUTTON_ID)
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

    def _apply_filters(self, page: Any, filters: dict[str, object]) -> None:
        mapping = {
            "keyword": ("fill", "#ctl00_Content_home_Public_ctl00_txt_key"),
            "court_level": ("select", "#ctl00_Content_home_Public_ctl00_drp_court_level"),
            "court": ("select", "#ctl00_Content_home_Public_ctl00_drp_court"),
            "adjudication_level": ("select", "#ctl00_Content_home_Public_ctl00_drp_adjudication_level"),
            "document_type": ("select", "#ctl00_Content_home_Public_ctl00_drp_document_type"),
            "case_style": ("select", "#ctl00_Content_home_Public_ctl00_drp_case_style"),
            "legal_relation": ("select", "#ctl00_Content_home_Public_ctl00_drp_legal_relation"),
            "date_from": ("fill", "#ctl00_Content_home_Public_ctl00_txt_from_date"),
            "date_to": ("fill", "#ctl00_Content_home_Public_ctl00_txt_to_date"),
            "precedent_applied": ("check", "#ctl00_Content_home_Public_ctl00_chk_precedent_applied"),
            "precedent_voted": ("check", "#ctl00_Content_home_Public_ctl00_chk_precedent_voted"),
        }
        for key, value in filters.items():
            if key not in mapping or value in (None, "", False):
                continue
            action, selector = mapping[key]
            locator = page.locator(selector)
            if not locator.count():
                continue
            if action == "fill":
                locator.fill(str(value))
            elif action == "select":
                locator.select_option(str(value))
            elif action == "check" and value:
                locator.check()
