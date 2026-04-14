from __future__ import annotations

from vietcase.parsers.detail_common_parser import DetailCommonParser
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from vietcase.services.source_router import FallbackRequiredError, SourceContext, SourceRouter


FILTER_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="abc123" />
  <select name="court_level">
    <option value="">-----chọn-----</option>
    <option value="1">TAND tối cao</option>
  </select>
</form>
"""

LISTING_HTML = """
<div id="ctl00_Content_home_Public_ctl00_lbl_count_record">36.519</div>
<div id="ctl00_Content_home_Public_ctl00_LbShowtotal">1826</div>
<div id="List_group_pub">
  <div class="list-group-item">
    <a href="/2ta100/chi-tiet-ban-an">Bản án 10/2026/KDTM-ST</a>
    <ul>
      <li class="list-group-item">Số bản án: 10/2026/KDTM-ST</li>
      <li class="list-group-item">Ngày ban hành: 29/03/2026</li>
      <li class="list-group-item">Tòa án: TAND Quận 1</li>
      <li class="list-group-item">Ngày công bố: 30/03/2026</li>
      <li class="list-group-item">Quan hệ pháp luật: Tranh chấp hợp đồng</li>
      <li class="list-group-item">Cấp giải quyết/xét xử: Sơ thẩm</li>
    </ul>
  </div>
</div>
"""

DETAIL_JUDGMENT_HTML = """
<ul>
  <li class="list-group-item">Tên bản án: Bản án kinh doanh thương mại sơ thẩm</li>
  <li class="list-group-item">Số bản án: 10/2026/KDTM-ST</li>
  <li class="list-group-item">Ngày ban hành: 29/03/2026</li>
  <li class="list-group-item">Ngày công bố: 30/03/2026</li>
  <li class="list-group-item">Tòa án: TAND Quận 1</li>
  <li class="list-group-item">Quan hệ pháp luật: Tranh chấp hợp đồng</li>
  <li class="list-group-item">Cấp giải quyết/xét xử: Sơ thẩm</li>
</ul>
<a href="/xuatfile/banan.pdf">PDF</a>
"""

DETAIL_DECISION_HTML = """
<ul>
  <li class="list-group-item">Tên quyết định: Quyết định công nhận hòa giải thành</li>
  <li class="list-group-item">Số quyết định: 15/2026/QĐ-KDTM</li>
  <li class="list-group-item">Ngày ban hành: 29/03/2026</li>
  <li class="list-group-item">Ngày công bố: 30/03/2026</li>
  <li class="list-group-item">Tòa án: TAND Quận 3</li>
  <li class="list-group-item">Quan hệ pháp luật: Tranh chấp cổ phần</li>
  <li class="list-group-item">Cấp giải quyết/xét xử: Phúc thẩm</li>
</ul>
<a href="/xuatfile/quyetdinh.pdf">PDF</a>
"""


def test_form_parser_extracts_fields_and_options() -> None:
    parser = FormParser()
    hidden_fields = parser.parse_hidden_fields(FILTER_HTML)
    selects = parser.parse_select_options(FILTER_HTML)
    assert hidden_fields["__VIEWSTATE"] == "abc123"
    assert selects["court_level"][1]["label"] == "TAND tối cao"


def test_listing_parser_extracts_records() -> None:
    parser = ListingParser()
    payload = parser.parse(LISTING_HTML, page_index=2)
    assert payload["total_results"] == 36519
    assert payload["total_pages"] == 1826
    assert len(payload["results"]) == 1
    record = payload["results"][0]
    assert record["document_number"] == "10/2026/KDTM-ST"
    assert record["court_name"] == "TAND Quận 1"
    assert record["page_index"] == 2


def test_detail_parser_dispatches_judgment() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_JUDGMENT_HTML, "https://example.com/ban-an")
    assert payload["document_type"] == "Bản án"
    assert payload["pdf_url"].endswith("banan.pdf")


def test_detail_parser_dispatches_decision() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_DECISION_HTML, "https://example.com/quyet-dinh")
    assert payload["document_type"] == "Quyết định"
    assert payload["pdf_url"].endswith("quyetdinh.pdf")


def test_source_router_switches_to_playwright_on_fallback() -> None:
    class RequestsClient:
        def load_filters(self) -> dict[str, object]:
            raise FallbackRequiredError("blocked")

    class PlaywrightClient:
        def load_filters(self) -> dict[str, object]:
            return {"selects": {"court_level": []}, "hidden_fields": {}}

    router = SourceRouter(RequestsClient(), PlaywrightClient())
    context = SourceContext(source_mode="requests", job_id=1)
    payload = router.call("load_filters", context)
    assert context.source_mode == "playwright"
    assert "selects" in payload
