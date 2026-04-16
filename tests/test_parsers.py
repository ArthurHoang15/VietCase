from __future__ import annotations

import requests

from vietcase.parsers.detail_common_parser import DetailCommonParser
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from requests import Response

from vietcase.services.search_service import SearchService
from vietcase.services.source_client_requests import RequestsSourceClient
from vietcase.services.source_router import FallbackRequiredError, SourceContext, SourceRouter


FILTER_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="abc123" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword_top" name="ctl00$Content_home_Public$ctl00$txtKeyword_top" type="text" />
  <label>C?p T?a ?n</label>
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels_top" name="ctl00$Content_home_Public$ctl00$Drop_Levels_top">
    <option value="">-----ch?n-----</option>
    <option value="TW">TAND t?i cao</option>
  </select>
  <label>T?a ?n</label>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts_top" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top">
    <option value="">-----ch?n-----</option>
  </select>
  <input id="ctl00_Content_home_Public_ctl00_cmd_search_banner" name="ctl00$Content_home_Public$ctl00$cmd_search_banner" type="submit" value="T?m ki?m" />
  <select id="ctl00_Content_home_Public_ctl00_DropPages" name="ctl00$Content_home_Public$ctl00$DropPages"><option value="1">1</option></select>
</form>
"""

LISTING_HTML = """
<div id="ctl00_Content_home_Public_ctl00_lbl_count_record">36.519</div>
<div id="ctl00_Content_home_Public_ctl00_LbShowtotal">1826</div>
<div id="List_group_pub">
  <a class="echo_id_pub" href="/2ta100/chi-tiet-ban-an">
    <h4 class="list-group-item-heading"><label>B?n ?n: </label><span>s? 10/2026/KDTM-ST ng?y 29/03/2026 c?a TAND Qu?n 1 <time>(30.03.2026)</time></span></h4>
  </a>
  <div class="row">
    <div class="col-md-12"><p><label>Quan h? ph?p lu?t:</label><span>Tranh ch?p h?p ??ng</span></p></div>
  </div>
  <div class="row">
    <div class="col-md-6"><label>C?p x?t x?: </label><span>S? th?m</span></div>
    <div class="col-md-6"><label>?p d?ng ?n l?: </label><span> Kh?ng</span></div>
  </div>
  <div class="row">
    <div class="col-md-6"><label>Lo?i v?/vi?c:</label><span>Kinh doanh th??ng m?i</span></div>
    <div class="col-md-6"><label>??nh ch?nh: </label><span>0</span></div>
  </div>
  <p class="Description_pub"><label>Th?ng tin v? v?/vi?c: </label><span>T?m t?t v? vi?c</span></p>
</div>
"""

DETAIL_JUDGMENT_HTML = """
<ul>
  <li class="list-group-item">T\u00ean b\u1ea3n \u00e1n: B\u1ea3n \u00e1n kinh doanh th\u01b0\u01a1ng m\u1ea1i s\u01a1 th\u1ea9m</li>
  <li class="list-group-item">S\u1ed1 b\u1ea3n \u00e1n: 10/2026/KDTM-ST</li>
  <li class="list-group-item">Ng\u00e0y ban h\u00e0nh: 29/03/2026</li>
  <li class="list-group-item">Ng\u00e0y c\u00f4ng b\u1ed1: 30/03/2026</li>
  <li class="list-group-item">T\u00f2a \u00e1n: TAND Qu\u1eadn 1</li>
  <li class="list-group-item">Quan h\u1ec7 ph\u00e1p lu\u1eadt: Tranh ch\u1ea5p h\u1ee3p \u0111\u1ed3ng</li>
  <li class="list-group-item">C\u1ea5p gi\u1ea3i quy\u1ebft/x\u00e9t x\u1eed: S\u01a1 th\u1ea9m</li>
</ul>
<a href="/xuatfile/banan.pdf">PDF</a>
"""

DETAIL_DECISION_HTML = """
<ul>
  <li class="list-group-item">T\u00ean quy\u1ebft \u0111\u1ecbnh: Quy\u1ebft \u0111\u1ecbnh c\u00f4ng nh\u1eadn h\u00f2a gi\u1ea3i th\u00e0nh</li>
  <li class="list-group-item">S\u1ed1 quy\u1ebft \u0111\u1ecbnh: 15/2026/Q\u0110-KDTM</li>
  <li class="list-group-item">Ng\u00e0y ban h\u00e0nh: 29/03/2026</li>
  <li class="list-group-item">Ng\u00e0y c\u00f4ng b\u1ed1: 30/03/2026</li>
  <li class="list-group-item">T\u00f2a \u00e1n: TAND Qu\u1eadn 3</li>
  <li class="list-group-item">Quan h\u1ec7 ph\u00e1p lu\u1eadt: Tranh ch\u1ea5p c\u1ed5 ph\u1ea7n</li>
  <li class="list-group-item">C\u1ea5p gi\u1ea3i quy\u1ebft/x\u00e9t x\u1eed: Ph\u00fac th\u1ea9m</li>
</ul>
<a href="/xuatfile/quyetdinh.pdf">PDF</a>
"""


def test_form_parser_extracts_hidden_fields_and_field_metadata() -> None:
    parser = FormParser()
    payload = parser.parse_form_state(FILTER_HTML)
    assert payload["hidden_fields"]["__VIEWSTATE"] == "abc123"
    assert payload["fields"]["court_level"]["name"] == "ctl00$Content_home_Public$ctl00$Drop_Levels_top"
    assert payload["fields"]["keyword"]["name"] == "ctl00$Content_home_Public$ctl00$txtKeyword_top"
    assert payload["search_button_name"] == "ctl00$Content_home_Public$ctl00$cmd_search_banner"
    assert payload["pagination_name"] == "ctl00$Content_home_Public$ctl00$DropPages"


def test_listing_parser_extracts_records() -> None:
    parser = ListingParser()
    payload = parser.parse(LISTING_HTML, page_index=2)
    assert payload["total_results"] == 36519
    assert payload["total_pages"] == 1826
    assert len(payload["results"]) == 1
    record = payload["results"][0]
    assert record["document_number"] == "10/2026/KDTM-ST"
    assert record["court_name"] == "TAND Qu?n 1"
    assert record["case_style"] == "Kinh doanh th??ng m?i"
    assert record["legal_relation"] == "Tranh ch?p h?p ??ng"
    assert record["adjudication_level"] == "S? th?m"
    assert record["page_index"] == 2


def test_detail_parser_dispatches_judgment() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_JUDGMENT_HTML, "https://example.com/ban-an")
    assert payload["document_type"] == "B\u1ea3n \u00e1n"
    assert payload["pdf_url"].endswith("banan.pdf")


def test_detail_parser_dispatches_decision() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_DECISION_HTML, "https://example.com/quyet-dinh")
    assert payload["document_type"] == "Quy\u1ebft \u0111\u1ecbnh"
    assert payload["pdf_url"].endswith("quyetdinh.pdf")


def test_source_router_uses_playwright_for_search_actions() -> None:
    calls: list[str] = []

    class RequestsClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("requests")
            return {"unexpected": True}

    class PlaywrightClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("playwright")
            return {"selects": {"court_level": []}, "hidden_fields": {}}

    router = SourceRouter(RequestsClient(), PlaywrightClient())
    context = SourceContext(source_mode="requests", job_id=1)
    payload = router.call("load_filters", context)
    assert calls == ["playwright"]
    assert context.source_mode == "playwright"
    assert "selects" in payload


def test_source_router_switches_to_playwright_on_detail_fallback() -> None:
    class RequestsClient:
        def load_detail(self, source_url: str) -> dict[str, object]:
            raise FallbackRequiredError("blocked")

    class PlaywrightClient:
        def load_detail(self, source_url: str) -> dict[str, object]:
            return {"html": "<a href='/xuatfile/test.pdf'>PDF</a>", "source_url": source_url}

    router = SourceRouter(RequestsClient(), PlaywrightClient())
    context = SourceContext(source_mode="requests", job_id=1)
    payload = router.call("load_detail", context, "https://example.com")
    assert context.source_mode == "playwright"
    assert payload["source_url"] == "https://example.com"


def test_search_service_preview_and_page_keep_preview_state() -> None:
    class FakeRouter:
        def __init__(self) -> None:
            self.calls = []

        def call(self, action: str, context: SourceContext, filters: dict, page_index: int, state: dict | None) -> dict[str, object]:
            self.calls.append((action, context.source_mode, page_index, state))
            return {
                "total_results": 20,
                "total_pages": 2,
                "results": [{"source_url": f"https://example.com/{page_index}", "page_index": page_index}],
                "state": {"page": page_index},
            }

    service = SearchService(FakeRouter())
    preview = service.preview({"case_style": "4"}, page_index=1)
    page2 = service.page(preview.preview_id, 2)
    assert preview.preview_id
    assert preview.source_mode == "playwright"
    assert page2.current_page == 2
    assert page2.results[0]["page_index"] == 2


def test_requests_client_remembers_compatibility_mode_per_host() -> None:
    client = RequestsSourceClient()
    calls: list[tuple[str, bool]] = []

    def fake_send(method: str, url: str, *, verify: bool, **kwargs: object) -> Response:
        calls.append((url, verify))
        if len(calls) == 1 and verify:
            raise requests.exceptions.SSLError('tls failed')
        response = Response()
        response.status_code = 200
        response._content = b'ok'
        response.encoding = 'utf-8'
        response.url = url
        return response

    client._send = fake_send  # type: ignore[method-assign]

    response, tls_mode = client._request('GET', 'https://example.com/first')
    assert response.status_code == 200
    assert tls_mode == 'compatibility'
    assert calls == [
        ('https://example.com/first', True),
        ('https://example.com/first', False),
    ]

    calls.clear()
    response, tls_mode = client._request('GET', 'https://example.com/second')
    assert response.status_code == 200
    assert tls_mode == 'compatibility'
    assert calls == [('https://example.com/second', False)]


def test_requests_client_warm_up_tls_cache_primes_host_cache() -> None:
    client = RequestsSourceClient()
    calls: list[tuple[str, bool, bool]] = []

    def fake_send(method: str, url: str, *, verify: bool, **kwargs: object) -> Response:
        calls.append((url, verify, bool(kwargs.get('stream'))))
        if len(calls) == 1 and verify:
            raise requests.exceptions.SSLError('tls failed')
        response = Response()
        response.status_code = 200
        response._content = b''
        response.encoding = 'utf-8'
        response.url = url
        return response

    client._send = fake_send  # type: ignore[method-assign]

    tls_mode = client.warm_up_tls_cache('https://example.com/bootstrap')
    assert tls_mode == 'compatibility'
    assert calls == [
        ('https://example.com/bootstrap', True, True),
        ('https://example.com/bootstrap', False, True),
    ]

    calls.clear()
    response, tls_mode = client._request('GET', 'https://example.com/next')
    assert response.status_code == 200
    assert tls_mode == 'compatibility'
    assert calls == [('https://example.com/next', False, False)]
