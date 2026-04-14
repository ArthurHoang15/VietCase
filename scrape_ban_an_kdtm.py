from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
from pypdf import PdfReader


warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://congbobanan.toaan.gov.vn"
SEARCH_URL = f"{BASE_URL}/0tat1cvn/ban-an-quyet-dinh"

LIST_GROUP_ID = "#List_group_pub"
DROP_PAGES_ID = "#ctl00_Content_home_Public_ctl00_DropPages"
SEARCH_BUTTON_ID = "#ctl00_Content_home_Public_ctl00_cmd_search_banner"
NEXT_BUTTON_ID = "#ctl00_Content_home_Public_ctl00_cmdnext"
PROFESSION_MODAL_ID = "#popModal"
PROFESSION_RADIO_ID = "#ctl00_Feedback_Home_Radio_STYLE_9"
PROFESSION_SAVE_ID = "#ctl00_Feedback_Home_cmdSave_Regis"


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_date(value: str | None) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def extract_regex(pattern: str, text: str, group: int = 1, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    if not match:
        return ""
    return normalize_whitespace(match.group(group))


def make_document_id(source_url: str) -> str:
    path = urlparse(source_url).path.strip("/")
    if not path:
        return "unknown"
    return path.split("/")[0]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_jsonl_map(path: Path, key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in load_jsonl_records(path):
        value = record.get(key)
        if value:
            result[value] = record
    return result


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value not in ("", None, [], {}):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


@dataclass
class CrawlConfig:
    date_from: str = "2021-03-29"
    date_to: str = "2026-03-29"
    case_style: str = "2"
    include_document_types: str = "all"
    headless: bool = True
    rate_limit_ms: int = 1500
    max_retries: int = 3
    output_dir: Path = Path("output")
    resume: bool = False
    max_pages: int | None = None
    max_details: int | None = None

    @property
    def date_from_display(self) -> str:
        return datetime.fromisoformat(self.date_from).strftime("%d/%m/%Y")

    @property
    def date_to_display(self) -> str:
        return datetime.fromisoformat(self.date_to).strftime("%d/%m/%Y")


@dataclass
class ListingParseResult:
    total_results: int
    total_pages: int
    records: list[dict[str, Any]]


class OutputLayout:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.raw_search_dir = base_dir / "raw" / "search"
        self.raw_detail_dir = base_dir / "raw" / "detail"
        self.raw_pdf_dir = base_dir / "raw" / "pdf"
        self.normalized_dir = base_dir / "normalized"
        self.checkpoint_path = base_dir / "checkpoint.json"
        self.search_results_path = self.normalized_dir / "search_results.jsonl"
        self.documents_path = self.normalized_dir / "documents.jsonl"
        self.failures_path = self.normalized_dir / "failures.jsonl"
        self.config_path = self.normalized_dir / "run_config.json"

    def ensure(self) -> None:
        for path in (
            self.raw_search_dir,
            self.raw_detail_dir,
            self.raw_pdf_dir,
            self.normalized_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


class CheckpointStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "search": {
                    "last_completed_page": 0,
                    "total_pages": None,
                    "total_results": None,
                    "completed": False,
                },
                "detail": {
                    "completed": False,
                    "last_completed_url": None,
                    "completed_count": 0,
                },
                "updated_at": None,
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.data["updated_at"] = utc_now()
        write_json(self.path, self.data)


class CourtParsers:
    @staticmethod
    def parse_listing_page(html: str, page_index: int, crawl_time: str) -> ListingParseResult:
        soup = BeautifulSoup(html, "html.parser")
        total_results = CourtParsers._extract_int_by_id(
            soup, "ctl00_Content_home_Public_ctl00_lbl_count_record"
        )
        total_pages = CourtParsers._extract_int_by_id(
            soup, "ctl00_Content_home_Public_ctl00_LbShowtotal"
        )
        records: list[dict[str, Any]] = []
        for result_index, item in enumerate(soup.select(f"{LIST_GROUP_ID} > .list-group-item"), start=1):
            anchor = item.select_one("a.echo_id_pub[href*='chi-tiet-ban-an']")
            if not anchor:
                continue
            header = normalize_whitespace(anchor.get_text(" ", strip=True))
            source_url = urljoin(BASE_URL, anchor.get("href", ""))
            document_type = CourtParsers._extract_labeled_text(anchor.select_one("h4 > label"))
            summary_text = CourtParsers._extract_field_from_container(item, "Thông tin về vụ/việc:")
            legal_relation = CourtParsers._extract_field_from_container(item, "Quan hệ pháp luật:")
            level = CourtParsers._extract_field_from_container(item, "Cấp xét xử:")
            case_style = CourtParsers._extract_field_from_container(item, "Loại vụ/việc:")
            precedent_applied = CourtParsers._extract_field_from_container(item, "Áp dụng án lệ:")
            correction_count = CourtParsers._extract_field_from_container(item, "Đính chính:")
            court = extract_regex(r"của\s+(.*?)(?:\(\d{2}\.\d{2}\.\d{4}\)|$)", header, flags=re.IGNORECASE)
            document_number = extract_regex(r"số\s+(.+?)\s+ngày", header, flags=re.IGNORECASE)
            issued_date = normalize_date(
                extract_regex(r"ngày\s+(\d{1,2}[/-]\d{1,2}[/-]\d{4})", header, flags=re.IGNORECASE)
            )
            published_date = normalize_date(
                extract_regex(r"\((\d{1,2}\.\d{1,2}\.\d{4})\)", header, flags=re.IGNORECASE)
            )
            records.append(
                {
                    "source_url": source_url,
                    "document_id": make_document_id(source_url),
                    "document_type": document_type,
                    "case_style": case_style or "Kinh doanh thương mại",
                    "document_number": document_number,
                    "issued_date": issued_date,
                    "court": court,
                    "published_date": published_date,
                    "title": summary_text or header,
                    "summary_text": summary_text,
                    "full_text": "",
                    "crawl_time": crawl_time,
                    "page_index": page_index,
                    "result_index": result_index,
                    "header_text": header,
                    "legal_relation": legal_relation,
                    "level": level,
                    "precedent_applied": precedent_applied,
                    "correction_count": correction_count,
                }
            )
        return ListingParseResult(total_results=total_results, total_pages=total_pages, records=records)

    @staticmethod
    def parse_detail_page(html: str, source_url: str, crawl_time: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        field_map: dict[str, str] = {}
        for item in soup.select("li.list-group-item"):
            text = normalize_whitespace(item.get_text(" ", strip=True))
            if ":" not in text:
                continue
            key, value = text.split(":", 1)
            field_map[normalize_whitespace(key)] = normalize_whitespace(value)

        title_key = "Tên bản án" if "Tên bản án" in field_map else "Tên quyết định"
        title = field_map.get(title_key, "")
        title = re.sub(r"\(\d{2}\.\d{2}\.\d{4}\)\s*$", "", title).strip()
        detail_date = CourtParsers._extract_detail_tab_value(soup, "Ngày tuyên án")
        pdf_url = CourtParsers._extract_pdf_url(soup, source_url)
        pdf_viewer_url = CourtParsers._extract_pdf_viewer_url(soup, source_url)
        published_date = normalize_date(
            extract_regex(r"\((\d{1,2}\.\d{1,2}\.\d{4})\)", field_map.get(title_key, ""))
        )

        return {
            "source_url": source_url,
            "document_id": make_document_id(source_url),
            "document_type": "Bản án" if "Tên bản án" in field_map else "Quyết định",
            "case_style": field_map.get("Loại vụ/việc", ""),
            "document_number": extract_regex(
                r"số\s+(.+?)\s+ngày",
                soup.title.get_text(" ", strip=True) if soup.title else "",
                flags=re.IGNORECASE,
            ),
            "issued_date": normalize_date(detail_date),
            "court": field_map.get("Tòa án xét xử", ""),
            "published_date": published_date,
            "title": normalize_whitespace(title),
            "summary_text": field_map.get("Thông tin về vụ/việc", ""),
            "full_text": "",
            "crawl_time": crawl_time,
            "page_index": None,
            "result_index": None,
            "legal_relation": field_map.get("Quan hệ pháp luật", ""),
            "level": field_map.get("Cấp xét xử", ""),
            "precedent_applied": field_map.get("Áp dụng án lệ", ""),
            "correction_count": field_map.get("Đính chính", ""),
            "pdf_url": pdf_url,
            "pdf_viewer_url": pdf_viewer_url,
            "detail_fields": field_map,
        }

    @staticmethod
    def _extract_int_by_id(soup: BeautifulSoup, element_id: str) -> int:
        node = soup.find(id=element_id)
        if not node:
            return 0
        text = normalize_whitespace(node.get_text(" ", strip=True))
        match = re.search(r"(\d[\d.]*)", text)
        if not match:
            return 0
        return int(match.group(1).replace(".", ""))

    @staticmethod
    def _extract_field_from_container(container: BeautifulSoup, label_text: str) -> str:
        for label in container.find_all("label"):
            text = normalize_whitespace(label.get_text(" ", strip=True))
            if text != label_text:
                continue
            sibling = label.find_next_sibling("span")
            if sibling:
                return normalize_whitespace(sibling.get_text(" ", strip=True))
            parent = label.parent
            if parent:
                span = parent.find("span")
                if span:
                    return normalize_whitespace(span.get_text(" ", strip=True))
        return ""

    @staticmethod
    def _extract_labeled_text(node: BeautifulSoup | None) -> str:
        if not node:
            return ""
        return normalize_whitespace(node.get_text(" ", strip=True)).rstrip(":")

    @staticmethod
    def _extract_detail_tab_value(soup: BeautifulSoup, label_prefix: str) -> str:
        for node in soup.select(".title_detai_tab_pub, .title_item_tab_pub"):
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if text.startswith(label_prefix):
                _, _, remainder = text.partition(":")
                return normalize_whitespace(remainder)
        return ""

    @staticmethod
    def _extract_pdf_url(soup: BeautifulSoup, source_url: str) -> str:
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.lower().endswith(".pdf"):
                return urljoin(source_url, href)
        iframe_url = CourtParsers._extract_pdf_viewer_url(soup, source_url)
        if not iframe_url:
            return ""
        parsed = urlparse(iframe_url)
        file_value = parse_qs(parsed.query).get("file", [""])[0]
        if not file_value:
            return ""
        return urljoin(BASE_URL, file_value.lstrip("/"))

    @staticmethod
    def _extract_pdf_viewer_url(soup: BeautifulSoup, source_url: str) -> str:
        iframe = soup.find("iframe", src=True)
        if not iframe:
            return ""
        return urljoin(source_url, iframe["src"])


class CourtCrawler:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.outputs = OutputLayout(config.output_dir)
        self.outputs.ensure()
        self.checkpoint = CheckpointStore(self.outputs.checkpoint_path)
        self._search_index = load_jsonl_map(self.outputs.search_results_path, "source_url")
        self._document_index = load_jsonl_map(self.outputs.documents_path, "source_url")
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
        write_json(self.outputs.config_path, asdict(config))

    def run_search(self) -> None:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.config.headless)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
                self._open_search(page)

                last_completed_page = 0
                if self.config.resume:
                    last_completed_page = int(self.checkpoint.data["search"].get("last_completed_page") or 0)

                listing_html = page.content()
                if last_completed_page == 0:
                    self._capture_search_page(1, listing_html)
                    parsed = CourtParsers.parse_listing_page(listing_html, 1, utc_now())
                    self._persist_search_records(parsed.records)
                    self._update_search_checkpoint(1, parsed.total_pages, parsed.total_results)
                    last_completed_page = 1
                else:
                    parsed = CourtParsers.parse_listing_page(listing_html, last_completed_page, utc_now())
                    if parsed.total_pages:
                        self._update_search_checkpoint(
                            last_completed_page,
                            parsed.total_pages,
                            parsed.total_results,
                        )

                total_pages = self._resolve_total_pages(parsed.total_pages)
                for page_index in range(last_completed_page + 1, total_pages + 1):
                    self._go_to_page(page, page_index)
                    html = page.content()
                    self._capture_search_page(page_index, html)
                    parsed = CourtParsers.parse_listing_page(html, page_index, utc_now())
                    self._persist_search_records(parsed.records)
                    self._update_search_checkpoint(page_index, parsed.total_pages or total_pages, parsed.total_results)
                    self._sleep()

                self.checkpoint.data["search"]["completed"] = True
                self.checkpoint.save()
                context.close()
                browser.close()
                return
        except Exception as exc:  # noqa: BLE001
            print(f"[search] playwright unavailable, falling back to requests: {exc}")

        self._run_search_via_requests()

    def run_detail(self) -> None:
        search_records = list(load_jsonl_map(self.outputs.search_results_path, "source_url").values())
        completed = load_jsonl_map(self.outputs.documents_path, "source_url")
        pending = [record for record in search_records if record["source_url"] not in completed]
        if self.config.max_details is not None:
            pending = pending[: self.config.max_details]

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.config.headless)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
                for index, listing_record in enumerate(pending, start=1):
                    source_url = listing_record["source_url"]
                    try:
                        html = self._with_retry(
                            lambda: self._fetch_detail_page(page, source_url),
                            f"detail {source_url}",
                        )
                        self._handle_detail_success(index, pending, listing_record, html)
                    except Exception as exc:  # noqa: BLE001
                        if "blocked" in str(exc).lower():
                            raise
                        self._record_failure("detail", source_url, str(exc))
                        print(f"[detail] failed {source_url}: {exc}", file=sys.stderr)
                    self._sleep()

                self.checkpoint.data["detail"]["completed"] = True
                self.checkpoint.save()
                context.close()
                browser.close()
                return
        except Exception as exc:  # noqa: BLE001
            print(f"[detail] playwright unavailable, falling back to requests: {exc}")

        for index, listing_record in enumerate(pending, start=1):
            source_url = listing_record["source_url"]
            try:
                html = self._with_retry(
                    lambda: self._fetch_detail_via_requests(source_url),
                    f"detail {source_url}",
                )
                self._handle_detail_success(index, pending, listing_record, html)
            except Exception as exc:  # noqa: BLE001
                self._record_failure("detail", source_url, str(exc))
                print(f"[detail] failed {source_url}: {exc}", file=sys.stderr)
            self._sleep()
        self.checkpoint.data["detail"]["completed"] = True
        self.checkpoint.save()

    def run_resume(self) -> None:
        if not self.checkpoint.data["search"].get("completed"):
            self.config.resume = True
            self.run_search()
        self.run_detail()

    def _run_search_via_requests(self) -> None:
        response = self._with_retry(
            lambda: self.session.get(SEARCH_URL, timeout=120, verify=False),
            "search page bootstrap",
        )
        response.raise_for_status()
        fields = self._extract_form_fields(response.text)
        fields["ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top"] = self.config.case_style
        fields["ctl00$Content_home_Public$ctl00$Rad_DATE_FROM_top"] = self.config.date_from_display
        fields["ctl00$Content_home_Public$ctl00$Rad_DATE_TO_top"] = self.config.date_to_display
        fields["ctl00$Content_home_Public$ctl00$cmd_search_banner"] = "Tìm kiếm"

        search_response = self._with_retry(
            lambda: self.session.post(SEARCH_URL, data=fields, timeout=120, verify=False),
            "search page submit",
        )
        search_response.raise_for_status()
        html = search_response.text

        last_completed_page = 0
        if self.config.resume:
            last_completed_page = int(self.checkpoint.data["search"].get("last_completed_page") or 0)

        parsed = CourtParsers.parse_listing_page(html, 1, utc_now())
        total_pages = self._resolve_total_pages(parsed.total_pages)
        if last_completed_page == 0:
            self._capture_search_page(1, html)
            self._persist_search_records(parsed.records)
            self._update_search_checkpoint(1, parsed.total_pages, parsed.total_results)
            last_completed_page = 1

        current_html = html
        for page_index in range(last_completed_page + 1, total_pages + 1):
            fields = self._extract_form_fields(current_html)
            fields["ctl00$Content_home_Public$ctl00$DropPages"] = str(page_index)
            page_response = self._with_retry(
                lambda: self.session.post(SEARCH_URL, data=fields, timeout=120, verify=False),
                f"search page {page_index}",
            )
            page_response.raise_for_status()
            current_html = page_response.text
            self._capture_search_page(page_index, current_html)
            parsed = CourtParsers.parse_listing_page(current_html, page_index, utc_now())
            self._persist_search_records(parsed.records)
            self._update_search_checkpoint(page_index, parsed.total_pages or total_pages, parsed.total_results)
            self._sleep()

        self.checkpoint.data["search"]["completed"] = True
        self.checkpoint.save()

    def _extract_form_fields(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        fields: dict[str, str] = {}
        for tag in soup.select("input, select, textarea"):
            name = tag.get("name")
            if not name:
                continue
            if tag.name == "select":
                selected = tag.find("option", selected=True)
                fields[name] = selected.get("value", "") if selected else ""
                continue

            input_type = (tag.get("type") or "").lower()
            if input_type in {"checkbox", "radio"}:
                if tag.has_attr("checked"):
                    fields[name] = tag.get("value", "on")
                continue
            fields[name] = tag.get("value", "")
        return fields

    def _handle_detail_success(
        self,
        index: int,
        pending: list[dict[str, Any]],
        listing_record: dict[str, Any],
        html: str,
    ) -> None:
        source_url = listing_record["source_url"]
        detail_record = CourtParsers.parse_detail_page(html, source_url, utc_now())
        self._capture_detail_html(detail_record["document_id"], html)
        full_text, pdf_path = self._extract_full_text(detail_record)
        detail_record["full_text"] = full_text
        detail_record["pdf_path"] = str(pdf_path) if pdf_path else ""
        self._persist_detail_record(deep_merge(listing_record, detail_record))
        self.checkpoint.data["detail"]["last_completed_url"] = source_url
        self.checkpoint.data["detail"]["completed_count"] = len(
            load_jsonl_map(self.outputs.documents_path, "source_url")
        )
        self.checkpoint.save()
        print(f"[detail] {index}/{len(pending)} {source_url}")

    def _open_search(self, page: Page) -> None:
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=120_000)
        if "blocked" in page.title().lower():
            raise RuntimeError("Playwright browser is blocked by the target site")
        page.wait_for_selector(SEARCH_BUTTON_ID, timeout=120_000)
        self._dismiss_profession_modal(page)
        page.select_option("#ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH_top", self.config.case_style)
        page.fill("#ctl00_Content_home_Public_ctl00_Rad_DATE_FROM_top", self.config.date_from_display)
        page.fill("#ctl00_Content_home_Public_ctl00_Rad_DATE_TO_top", self.config.date_to_display)
        with page.expect_navigation(wait_until="domcontentloaded", timeout=120_000):
            page.click(SEARCH_BUTTON_ID)
        page.wait_for_selector(f"{LIST_GROUP_ID} > .list-group-item", timeout=120_000)

    def _dismiss_profession_modal(self, page: Page) -> None:
        try:
            modal = page.locator(PROFESSION_MODAL_ID)
            if not modal.is_visible(timeout=5_000):
                return
        except PlaywrightTimeoutError:
            return
        page.check(PROFESSION_RADIO_ID)
        with page.expect_navigation(wait_until="domcontentloaded", timeout=120_000):
            page.click(PROFESSION_SAVE_ID)
        page.wait_for_selector(SEARCH_BUTTON_ID, timeout=120_000)

    def _resolve_total_pages(self, parsed_total_pages: int) -> int:
        total_pages = parsed_total_pages or int(self.checkpoint.data["search"].get("total_pages") or 1)
        if self.config.max_pages is not None:
            total_pages = min(total_pages, self.config.max_pages)
        return max(total_pages, 1)

    def _go_to_page(self, page: Page, target_page_index: int) -> None:
        selector = page.locator(DROP_PAGES_ID)
        selector.wait_for(timeout=120_000)
        current_value = selector.input_value()
        if current_value == str(target_page_index):
            return
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=120_000):
                selector.select_option(str(target_page_index))
            page.wait_for_selector(f"{LIST_GROUP_ID} > .list-group-item", timeout=120_000)
            return
        except PlaywrightTimeoutError:
            pass
        current_page = int(current_value or 1)
        while current_page < target_page_index:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=120_000):
                page.click(NEXT_BUTTON_ID)
            page.wait_for_selector(f"{LIST_GROUP_ID} > .list-group-item", timeout=120_000)
            current_page += 1

    def _fetch_detail_page(self, page: Page, source_url: str) -> str:
        page.goto(source_url, wait_until="domcontentloaded", timeout=120_000)
        if "blocked" in page.title().lower():
            raise RuntimeError("Playwright browser is blocked by the target site")
        page.wait_for_selector("li.list-group-item", timeout=120_000)
        return page.content()

    def _fetch_detail_via_requests(self, source_url: str) -> str:
        response = self.session.get(source_url, timeout=120, verify=False)
        response.raise_for_status()
        return response.text

    def _extract_full_text(self, detail_record: dict[str, Any]) -> tuple[str, Path | None]:
        pdf_url = detail_record.get("pdf_url", "")
        if pdf_url:
            pdf_path = self.outputs.raw_pdf_dir / f"{detail_record['document_id']}.pdf"
            self._download_pdf(pdf_url, pdf_path)
            return self._extract_pdf_text(pdf_path), pdf_path

        html_path = self.outputs.raw_detail_dir / f"{detail_record['document_id']}.html"
        if html_path.exists():
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
            return normalize_whitespace(soup.get_text("\n", strip=True)), None
        return "", None

    def _download_pdf(self, pdf_url: str, path: Path) -> None:
        if path.exists():
            return
        response = self._with_retry(
            lambda: self.session.get(pdf_url, timeout=120, verify=False),
            f"pdf {pdf_url}",
        )
        response.raise_for_status()
        ensure_parent(path)
        path.write_bytes(response.content)

    def _extract_pdf_text(self, path: Path) -> str:
        reader = PdfReader(io.BytesIO(path.read_bytes()))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return normalize_whitespace("\n".join(parts))

    def _capture_search_page(self, page_index: int, html: str) -> None:
        write_text(self.outputs.raw_search_dir / f"page_{page_index:05d}.html", html)

    def _capture_detail_html(self, document_id: str, html: str) -> None:
        write_text(self.outputs.raw_detail_dir / f"{document_id}.html", html)

    def _persist_search_records(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            if record["source_url"] in self._search_index:
                continue
            append_jsonl(self.outputs.search_results_path, record)
            self._search_index[record["source_url"]] = record

    def _persist_detail_record(self, record: dict[str, Any]) -> None:
        if record["source_url"] in self._document_index:
            return
        append_jsonl(self.outputs.documents_path, record)
        self._document_index[record["source_url"]] = record

    def _update_search_checkpoint(self, page_index: int, total_pages: int, total_results: int) -> None:
        self.checkpoint.data["search"]["last_completed_page"] = page_index
        self.checkpoint.data["search"]["total_pages"] = total_pages
        self.checkpoint.data["search"]["total_results"] = total_results
        self.checkpoint.save()
        print(f"[search] page={page_index} total_pages={total_pages} total_results={total_results}")

    def _record_failure(self, phase: str, target: str, error: str) -> None:
        append_jsonl(
            self.outputs.failures_path,
            {"phase": phase, "target": target, "error": error, "crawl_time": utc_now()},
        )

    def _with_retry(self, func: Callable[[], Any], label: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return func()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self.config.max_retries:
                    break
                print(f"[retry] {label} attempt={attempt} error={exc}")
                time.sleep(attempt * max(self.config.rate_limit_ms, 1000) / 1000)
        if last_error is None:
            raise RuntimeError(f"Retry wrapper failed without an exception for {label}")
        raise last_error

    def _sleep(self) -> None:
        time.sleep(max(self.config.rate_limit_ms, 0) / 1000)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawler ban an KDTM bang Playwright.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_flags(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--date-from", default="2021-03-29")
        subparser.add_argument("--date-to", default="2026-03-29")
        subparser.add_argument("--case-style", default="2")
        subparser.add_argument("--include-document-types", default="all")
        subparser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
        subparser.add_argument("--rate-limit-ms", type=int, default=1500)
        subparser.add_argument("--max-retries", type=int, default=3)
        subparser.add_argument("--output-dir", default="output")
        subparser.add_argument("--resume", action="store_true")
        subparser.add_argument("--max-pages", type=int, default=None)
        subparser.add_argument("--max-details", type=int, default=None)

    add_common_flags(subparsers.add_parser("search", help="Run search and save listing pages"))
    add_common_flags(subparsers.add_parser("detail", help="Fetch detail pages from prior search results"))
    add_common_flags(subparsers.add_parser("resume", help="Resume interrupted crawl"))
    return parser


def config_from_args(args: argparse.Namespace) -> CrawlConfig:
    return CrawlConfig(
        date_from=args.date_from,
        date_to=args.date_to,
        case_style=args.case_style,
        include_document_types=args.include_document_types,
        headless=args.headless,
        rate_limit_ms=args.rate_limit_ms,
        max_retries=args.max_retries,
        output_dir=Path(args.output_dir).resolve(),
        resume=args.resume or args.command == "resume",
        max_pages=args.max_pages,
        max_details=args.max_details,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    crawler = CourtCrawler(config_from_args(args))
    if args.command == "search":
        crawler.run_search()
    elif args.command == "detail":
        crawler.run_detail()
    elif args.command == "resume":
        crawler.run_resume()
    else:
        parser.error(f"Unsupported command: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
