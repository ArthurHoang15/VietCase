from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from vietcase.parsers.compatibility import BASE_URL, extract_regex, first_present, get_aliases, make_document_id, normalize_date, normalize_label_text, normalize_whitespace


class ListingParser:
    def parse(self, html: str, page_index: int = 1) -> dict[str, object]:
        soup = BeautifulSoup(html, "html.parser")
        total_results_text = soup.select_one("#ctl00_Content_home_Public_ctl00_lbl_count_record")
        total_pages_text = soup.select_one("#ctl00_Content_home_Public_ctl00_LbShowtotal")
        total_results = int(extract_regex(r"(\d[\d\.]*)", total_results_text.get_text(" ", strip=True) if total_results_text else "").replace(".", "") or 0)
        total_pages = int(extract_regex(r"(\d+)", total_pages_text.get_text(" ", strip=True) if total_pages_text else "") or 0)

        results: list[dict[str, object]] = []
        for result_index, item in enumerate(soup.select("#List_group_pub > .list-group-item"), start=1):
            link = item.select_one("a[href]")
            source_url = urljoin(BASE_URL, link.get("href", "")) if link else ""
            title = normalize_whitespace(link.get_text(" ", strip=True)) if link else ""
            container_text = item.get_text("\n", strip=True)
            record = {
                "source_url": source_url,
                "document_id": make_document_id(source_url),
                "title": title,
                "document_type": self._extract_field_from_container(item, "ten_ban_an") or self._extract_field_from_container(item, "ten_quyet_dinh") or ("Bản án" if "bản án" in title.lower() else "Quyết định" if "quyết định" in title.lower() else ""),
                "document_number": first_present([
                    self._extract_field_from_container(item, "so_ban_an"),
                    self._extract_field_from_container(item, "so_quyet_dinh"),
                    extract_regex(r"Số[^:\n]*:\s*([^\n]+)", container_text),
                ]),
                "issued_date": normalize_date(self._extract_field_from_container(item, "ngay_ban_hanh") or extract_regex(r"Ngày ban hành:\s*([^\n]+)", container_text)),
                "published_date": normalize_date(self._extract_field_from_container(item, "ngay_cong_bo") or extract_regex(r"Ngày công bố:\s*([^\n]+)", container_text)),
                "court_name": first_present([
                    self._extract_field_from_container(item, "toa_an"),
                    extract_regex(r"Tòa án:\s*([^\n]+)", container_text),
                ]),
                "case_style": extract_regex(r"Loại vụ việc:\s*([^\n]+)", container_text),
                "legal_relation": first_present([
                    self._extract_field_from_container(item, "quan_he_phap_luat"),
                    extract_regex(r"Quan hệ pháp luật:\s*([^\n]+)", container_text),
                ]),
                "adjudication_level": first_present([
                    self._extract_field_from_container(item, "cap_xet_xu"),
                    extract_regex(r"Cấp giải quyết/xét xử:\s*([^\n]+)", container_text),
                ]),
                "summary_text": normalize_whitespace(container_text),
                "precedent_applied": self._extract_checkbox_like(container_text, get_aliases("co_ap_dung_an_le")),
                "precedent_voted": self._extract_checkbox_like(container_text, get_aliases("duoc_binh_chon")),
                "page_index": page_index,
                "result_index": result_index,
            }
            results.append(record)
        return {
            "total_results": total_results,
            "total_pages": total_pages,
            "results": results,
        }

    def _extract_field_from_container(self, item: BeautifulSoup, label_key: str) -> str:
        aliases = [normalize_label_text(alias) for alias in get_aliases(label_key)]
        for li in item.select("li.list-group-item"):
            text = normalize_whitespace(li.get_text(" ", strip=True))
            normalized = normalize_label_text(text)
            for alias in aliases:
                if normalized.startswith(alias):
                    return normalize_whitespace(normalized[len(alias):].lstrip(":"))
        return ""

    def _extract_checkbox_like(self, text: str, aliases: list[str]) -> bool:
        lowered = text.lower()
        return any(alias.lower() in lowered for alias in aliases)
