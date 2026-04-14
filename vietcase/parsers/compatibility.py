from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

BASE_URL = "https://congbobanan.toaan.gov.vn"


LABEL_ALIASES = {
    "ten_ban_an": ["Tên bản án", "TÃªn báº£n Ã¡n"],
    "ten_quyet_dinh": ["Tên quyết định", "TÃªn quyáº¿t Ä‘á»‹nh"],
    "so_ban_an": ["Số bản án", "Sá»‘ báº£n Ã¡n"],
    "so_quyet_dinh": ["Số quyết định", "Sá»‘ quyáº¿t Ä‘á»‹nh"],
    "toa_an": ["Tòa án", "TÃ²a Ã¡n"],
    "ngay_ban_hanh": ["Ngày ban hành", "NgÃ y ban hÃ nh"],
    "ngay_cong_bo": ["Ngày công bố", "NgÃ y cÃ´ng bá»‘"],
    "quan_he_phap_luat": ["Quan hệ pháp luật", "Quan há»‡ phÃ¡p luáº­t"],
    "cap_xet_xu": ["Cấp giải quyết/xét xử", "Cáº¥p giáº£i quyáº¿t/xÃ©t xá»­"],
    "co_ap_dung_an_le": ["Có áp dụng án lệ", "CÃ³ Ã¡p dá»¥ng Ã¡n lá»‡"],
    "duoc_binh_chon": ["Được bình chọn làm nguồn phát triển án lệ", "ÄÆ°á»£c bÃ¬nh chá»n lÃ m nguá»“n phÃ¡t triá»ƒn Ã¡n lá»‡"],
}


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
    return normalize_whitespace(match.group(group)) if match else ""


def make_document_id(source_url: str) -> str:
    path = urlparse(source_url).path.strip("/")
    return path.split("/")[0] if path else "unknown"


def normalize_label_text(text: str) -> str:
    return normalize_whitespace(text).rstrip(":")


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
    return ""
