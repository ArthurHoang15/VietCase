from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

BASE_URL = "https://congbobanan.toaan.gov.vn"


LABEL_ALIASES = {
    "ten_ban_an": ["T?n b?n ?n", "T??n b???n ??n"],
    "ten_quyet_dinh": ["T?n quy?t ??nh", "T??n quy???t ?????nh"],
    "so_ban_an": ["S? b?n ?n", "S??? b???n ??n"],
    "so_quyet_dinh": ["S? quy?t ??nh", "S??? quy???t ?????nh"],
    "toa_an": ["T?a ?n", "T??a ??n"],
    "ngay_ban_hanh": ["Ng?y ban h?nh", "Ng? y ban h? nh"],
    "ngay_cong_bo": ["Ng?y c?ng b?", "Ng? y c??ng b???"],
    "quan_he_phap_luat": ["Quan h? ph?p lu?t", "Quan h??? ph??p lu???t"],
    "cap_xet_xu": ["C?p gi?i quy?t/x?t x?", "C???p gi???i quy???t/x??t x???"],
    "co_ap_dung_an_le": ["C? ?p d?ng ?n l?", "C?? ??p d???ng ??n l???"],
    "duoc_binh_chon": ["???c b?nh ch?n l?m ngu?n ph?t tri?n ?n l?", "???????c b??nh ch???n l? m ngu???n ph??t tri???n ??n l???"],
}


MOJIBAKE_MARKERS = ("Ã", "Ä", "Æ", "á»", "áº", "â", "ð", "Â")


def _repair_mojibake(value: str) -> str:
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    repaired = _repair_mojibake(value)
    return re.sub(r"\s+", " ", repaired).strip()


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
    iframe = soup.select_one("iframe[src]")
    if iframe:
        src = iframe.get("src", "")
        viewer_url = urljoin(BASE_URL, src)
        file_value = parse_qs(urlparse(viewer_url).query).get("file", [""])[0]
        if file_value:
            return urljoin(BASE_URL, file_value.lstrip("/"))
    return ""
