from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from vietcase.core.text_utils import normalize_for_search

BASE_URL = "https://congbobanan.toaan.gov.vn"

LABEL_ALIASES = {
    "ten_ban_an": ["T\u00ean b\u1ea3n \u00e1n"],
    "ten_quyet_dinh": ["T\u00ean quy\u1ebft \u0111\u1ecbnh"],
    "so_ban_an": ["S\u1ed1 b\u1ea3n \u00e1n"],
    "so_quyet_dinh": ["S\u1ed1 quy\u1ebft \u0111\u1ecbnh"],
    "toa_an": ["T\u00f2a \u00e1n"],
    "ngay_ban_hanh": ["Ng\u00e0y ban h\u00e0nh", "Ng\u00e0y tuy\u00ean \u00e1n"],
    "ngay_cong_bo": ["Ng\u00e0y c\u00f4ng b\u1ed1"],
    "quan_he_phap_luat": ["Quan h\u1ec7 ph\u00e1p lu\u1eadt"],
    "cap_xet_xu": ["C\u1ea5p gi\u1ea3i quy\u1ebft/x\u00e9t x\u1eed", "C\u1ea5p x\u00e9t x\u1eed"],
    "co_ap_dung_an_le": ["C\u00f3 \u00e1p d\u1ee5ng \u00e1n l\u1ec7", "\u00c1p d\u1ee5ng \u00e1n l\u1ec7"],
    "duoc_binh_chon": ["\u0110\u01b0\u1ee3c b\u00ecnh ch\u1ecdn l\u00e0m ngu\u1ed3n ph\u00e1t tri\u1ec3n \u00e1n l\u1ec7"],
}

MOJIBAKE_MARKERS = ("\u00c3", "\u00c4", "\u00c6", "\u00e1\u00bb", "\u00e1\u00ba", "\u00e2", "\u00f0", "\u00c2")


def _repair_mojibake(value: str) -> str:
    if not value:
        return ""
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if repaired:
            return repaired
    return value


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    repaired = _repair_mojibake(str(value))
    return re.sub(r"\s+", " ", repaired).strip()


def normalize_date(value: str | None) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def extract_regex(pattern: str, text: str, group: int = 1, flags: int = 0) -> str:
    match = re.search(pattern, normalize_whitespace(text), flags)
    return normalize_whitespace(match.group(group)) if match else ""


def make_document_id(source_url: str) -> str:
    path = urlparse(source_url).path.strip("/")
    return path.split("/")[0] if path else "unknown"


def normalize_label_text(text: str) -> str:
    return normalize_whitespace(text).rstrip(":")


def normalize_label_key(text: str) -> str:
    return normalize_for_search(normalize_label_text(text))


def first_present(values: Iterable[str]) -> str:
    for value in values:
        value = normalize_whitespace(value)
        if value:
            return value
    return ""


def get_aliases(label_key: str) -> list[str]:
    return LABEL_ALIASES.get(label_key, [label_key])


def extract_pdf_url_from_soup(soup: BeautifulSoup) -> str:
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if ".pdf" in href.lower() or "xuatfile" in href.lower():
            return urljoin(BASE_URL, href)
    iframe = soup.select_one("iframe[src]")
    if iframe:
        src = iframe.get("src", "")
        viewer_url = urljoin(BASE_URL, src)
        file_value = parse_qs(urlparse(viewer_url).query).get("file", [""])[0]
        if file_value:
            return urljoin(BASE_URL, file_value.lstrip("/"))
    return ""
