from __future__ import annotations

import requests
from requests import Response

from vietcase.parsers.detail_common_parser import DetailCommonParser
from vietcase.parsers.form_parser import FormParser
from vietcase.parsers.listing_parser import ListingParser
from vietcase.services.search_service import SearchService
from vietcase.services.source_client_requests import RequestsSourceClient
from vietcase.services.source_router import FallbackRequiredError, SourceContext, SourceRouter


FILTER_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="abc123" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword_top" name="ctl00$Content_home_Public$ctl00$txtKeyword_top" type="text" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword" name="ctl00$Content_home_Public$ctl00$txtKeyword" type="text" />
  <label>C?p T?a ?n</label>
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels_top" name="ctl00$Content_home_Public$ctl00$Drop_Levels_top">
    <option value="">-----ch?n-----</option>
    <option value="TW">TAND t?i cao</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels" name="ctl00$Content_home_Public$ctl00$Drop_Levels">
    <option value="">-----ch?n-----</option>
    <option value="TW">TAND t?i cao</option>
  </select>
  <label>T?a ?n</label>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts_top" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <label>C?p gi?i quy?t/x?t x?</label>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="PT">Ph?c th?m</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="PT">Ph?c th?m</option>
  </select>
  <label>B?n ?n/quy?t ??nh</label>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="BA">B?n ?n</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="BA">B?n ?n</option>
  </select>
  <label>Lo?i v?/vi?c</label>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <label>T?i danh/quan h? ph?p lu?t/bi?n ph?p x? l?</label>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search_top" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search_top">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM_top" type="text" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM" type="text" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO_top" type="text" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO" type="text" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_top" name="ctl00$Content_home_Public$ctl00$check_anle_top" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle" name="ctl00$Content_home_Public$ctl00$check_anle" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted_top" name="ctl00$Content_home_Public$ctl00$check_anle_voted_top" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted" name="ctl00$Content_home_Public$ctl00$check_anle_voted" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_cmd_search_banner" name="ctl00$Content_home_Public$ctl00$cmd_search_banner" type="submit" value="T?m ki?m" />
  <select id="ctl00_Content_home_Public_ctl00_DropPages" name="ctl00$Content_home_Public$ctl00$DropPages"><option value="1">1</option></select>
</form>
"""

DEPENDENT_COURT_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="after-court" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword_top" name="ctl00$Content_home_Public$ctl00$txtKeyword_top" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword" name="ctl00$Content_home_Public$ctl00$txtKeyword" type="text" value="" />
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels_top" name="ctl00$Content_home_Public$ctl00$Drop_Levels_top">
    <option value="">-----ch?n-----</option>
    <option value="TW" selected>TAND t?i cao</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels" name="ctl00$Content_home_Public$ctl00$Drop_Levels">
    <option value="">-----ch?n-----</option>
    <option value="TW" selected>TAND t?i cao</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts_top" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="2">Gi?m ??c th?m</option>
    <option value="3">T?i th?m</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="2">Gi?m ??c th?m</option>
    <option value="3">T?i th?m</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="0">B?n ?n</option>
    <option value="1">Quy?t ??nh</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="0">B?n ?n</option>
    <option value="1">Quy?t ??nh</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search_top" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search_top">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM_top" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO_top" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_top" name="ctl00$Content_home_Public$ctl00$check_anle_top" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle" name="ctl00$Content_home_Public$ctl00$check_anle" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted_top" name="ctl00$Content_home_Public$ctl00$check_anle_voted_top" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted" name="ctl00$Content_home_Public$ctl00$check_anle_voted" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_cmd_search_banner" name="ctl00$Content_home_Public$ctl00$cmd_search_banner" type="submit" value="T?m ki?m" />
  <select id="ctl00_Content_home_Public_ctl00_DropPages" name="ctl00$Content_home_Public$ctl00$DropPages"><option value="1">1</option></select>
</form>
"""

SEARCH_RESULTS_WITH_SELECTION_HTML = """
<form>
  <input type="hidden" name="__VIEWSTATE" value="after-search" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword_top" name="ctl00$Content_home_Public$ctl00$txtKeyword_top" type="text" value="" />
  <input id="ctl00_Content_home_Public_ctl00_txtKeyword" name="ctl00$Content_home_Public$ctl00$txtKeyword" type="text" value="" />
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels_top" name="ctl00$Content_home_Public$ctl00$Drop_Levels_top">
    <option value="">-----ch?n-----</option>
    <option value="TW" selected>TAND t?i cao</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_Levels" name="ctl00$Content_home_Public$ctl00$Drop_Levels">
    <option value="">-----ch?n-----</option>
    <option value="TW" selected>TAND t?i cao</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts_top" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Drop_Courts" name="ctl00$Content_home_Public$ctl00$Ra_Drop_Courts">
    <option value="">-----ch?n-----</option>
    <option value="TANDTC">T?a ?n m?u</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="2" selected>Gi?m ??c th?m</option>
    <option value="3">T?i th?m</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="2" selected>Gi?m ??c th?m</option>
    <option value="3">T?i th?m</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="0">B?n ?n</option>
    <option value="1" selected>Quy?t ??nh</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="0">B?n ?n</option>
    <option value="1" selected>Quy?t ??nh</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH_top" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH" name="ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH">
    <option value="">-----ch?n-----</option>
    <option value="DS">D?n s?</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search_top" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search_top">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <select id="ctl00_Content_home_Public_ctl00_Ra_Case_shows_search" name="ctl00$Content_home_Public$ctl00$Ra_Case_shows_search">
    <option value="">-----ch?n-----</option>
    <option value="QHPL">Tranh ch?p quy?n s? d?ng ??t</option>
  </select>
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM_top" type="text" value="01/01/2026" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_FROM" name="ctl00$Content_home_Public$ctl00$Rad_DATE_FROM" type="text" value="01/01/2026" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO_top" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO_top" type="text" value="02/03/2026" />
  <input id="ctl00_Content_home_Public_ctl00_Rad_DATE_TO" name="ctl00$Content_home_Public$ctl00$Rad_DATE_TO" type="text" value="02/03/2026" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_top" name="ctl00$Content_home_Public$ctl00$check_anle_top" type="checkbox" checked />
  <input id="ctl00_Content_home_Public_ctl00_check_anle" name="ctl00$Content_home_Public$ctl00$check_anle" type="checkbox" checked />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted_top" name="ctl00$Content_home_Public$ctl00$check_anle_voted_top" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_check_anle_voted" name="ctl00$Content_home_Public$ctl00$check_anle_voted" type="checkbox" />
  <input id="ctl00_Content_home_Public_ctl00_cmd_search_banner" name="ctl00$Content_home_Public$ctl00$cmd_search_banner" type="submit" value="T?m ki?m" />
  <select id="ctl00_Content_home_Public_ctl00_DropPages" name="ctl00$Content_home_Public$ctl00$DropPages"><option value="1" selected>1</option></select>
</form>
"""

LISTING_HTML = """
<div id="ctl00_Content_home_Public_ctl00_lbl_count_record">5.907</div>
<div id="ctl00_Content_home_Public_ctl00_LbShowtotal">296</div>
<div id="List_group_pub">
  <a class="echo_id_pub" href="/2ta100/chi-tiet-ban-an">
    <h4 class="list-group-item-heading">
      <label>Bản án:</label>
      <span>số 47/2026/DS-PT ngày 23/01/2026 của Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội <time>(01.03.2026)</time></span>
    </h4>
  </a>
  <div class="row">
    <div class="col-md-12"><p><label>Quan hệ pháp luật:</label><span>Tranh chấp về thừa kế tài sản</span></p></div>
  </div>
  <div class="row">
    <div class="col-md-6"><label>Cấp xét xử:</label><span>Phúc thẩm</span></div>
    <div class="col-md-6"><label>Áp dụng án lệ:</label><span>Không</span></div>
  </div>
  <div class="row">
    <div class="col-md-6"><label>Loại vụ/việc:</label><span>Dân sự</span></div>
    <div class="col-md-6"><label>Đính chính:</label><span>0</span></div>
  </div>
  <p class="Description_pub"><label>Thông tin về vụ/việc:</label><span>Tranh chấp quyền sử dụng đất và yêu cầu chia di sản thừa kế</span></p>
  <div class="row">
    <div class="col-md-12"><label>Tổng số lượt được bình chọn làm nguồn phát triển án lệ:</label><span>0</span></div>
  </div>
</div>
"""

LISTING_HTML_WITH_WEAK_NUMBER = """
<div id="ctl00_Content_home_Public_ctl00_lbl_count_record">1</div>
<div id="ctl00_Content_home_Public_ctl00_LbShowtotal">1</div>
<div id="List_group_pub">
  <a class="echo_id_pub" href="/2ta200/chi-tiet-ban-an">
    <h4 class="list-group-item-heading">
      <label>Quyết định:</label>
      <span>số 03 ngày 20/01/2026 của Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội <time>(26.03.2026)</time></span>
    </h4>
  </a>
  <div class="row">
    <div class="col-md-12"><p><label>Quan hệ pháp luật:</label><span>Tranh chấp mẫu</span></p></div>
  </div>
</div>
"""

SEARCH_RESULTS_WITH_SELECTION_PAGE = SEARCH_RESULTS_WITH_SELECTION_HTML + LISTING_HTML

DETAIL_JUDGMENT_HTML = """
<ul>
  <li class="list-group-item">Tên bản án: Bản án dân sự phúc thẩm số 47/2026/DS-PT</li>
  <li class="list-group-item">Số bản án: 47/2026/DS-PT</li>
  <li class="list-group-item">Ngày ban hành: 23/01/2026</li>
  <li class="list-group-item">Ngày công bố: 01/03/2026</li>
  <li class="list-group-item">Tòa án: Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội</li>
  <li class="list-group-item">Quan hệ pháp luật: Tranh chấp về thừa kế tài sản</li>
  <li class="list-group-item">Cấp giải quyết/xét xử: Phúc thẩm</li>
  <li class="list-group-item">Áp dụng án lệ: Không</li>
  <li class="list-group-item">Đính chính: 0</li>
</ul>
<a href="/xuatfile/banan.pdf">PDF</a>
"""

DETAIL_DECISION_HTML = """
<ul>
  <li class="list-group-item">Tên quyết định: Quyết định công nhận hòa giải thành</li>
  <li class="list-group-item">Số quyết định: 15/2026/QĐ-PT</li>
  <li class="list-group-item">Ngày ban hành: 29/03/2026</li>
  <li class="list-group-item">Ngày công bố: 30/03/2026</li>
  <li class="list-group-item">Tòa án: TAND cấp cao tại Hà Nội</li>
  <li class="list-group-item">Quan hệ pháp luật: Tranh chấp cổ phần</li>
  <li class="list-group-item">Cấp giải quyết/xét xử: Phúc thẩm</li>
  <li class="list-group-item">Áp dụng án lệ: Không</li>
  <li class="list-group-item">Đính chính: 0</li>
</ul>
<a href="/xuatfile/quyetdinh.pdf">PDF</a>
"""

DETAIL_DECISION_WITH_WEAK_HEADING_HTML = """
<html>
  <head><title>Bản án số: 03 ngày 20/01/2026</title></head>
  <body>
    <ul>
      <li class="list-group-item">Tên quyết định: Bản án số: 03 ngày 20/01/2026</li>
      <li class="list-group-item">Ngày ban hành: 20/01/2026</li>
      <li class="list-group-item">Tòa án: Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội</li>
    </ul>
    <a href="/xuatfile/sample.pdf">PDF</a>
  </body>
</html>
"""


def test_form_parser_extracts_hidden_fields_and_field_metadata() -> None:
    parser = FormParser()
    payload = parser.parse_form_state(FILTER_HTML)
    assert payload["hidden_fields"]["__VIEWSTATE"] == "abc123"
    assert payload["fields"]["court_level"]["name"] == "ctl00$Content_home_Public$ctl00$Drop_Levels_top"
    assert payload["fields"]["keyword"]["name"] == "ctl00$Content_home_Public$ctl00$txtKeyword_top"
    assert {alias["name"] for alias in payload["fields"]["keyword"]["aliases"]} == {
        "ctl00$Content_home_Public$ctl00$txtKeyword_top",
        "ctl00$Content_home_Public$ctl00$txtKeyword",
    }
    assert payload["search_button_name"] == "ctl00$Content_home_Public$ctl00$cmd_search_banner"
    assert payload["pagination_name"] == "ctl00$Content_home_Public$ctl00$DropPages"


def test_form_parser_extracts_current_values_and_checked_state() -> None:
    parser = FormParser()
    payload = parser.parse_form_state(SEARCH_RESULTS_WITH_SELECTION_HTML)
    assert payload["fields"]["court_level"]["current_value"] == "TW"
    assert payload["fields"]["adjudication_level"]["current_value"] == "2"
    assert payload["fields"]["document_type"]["current_value"] == "1"
    assert payload["fields"]["date_from"]["current_value"] == "01/01/2026"
    assert payload["fields"]["date_to"]["current_value"] == "02/03/2026"
    assert payload["fields"]["precedent_applied"]["checked"] is True
    assert payload["fields"]["precedent_voted"]["checked"] is False


def test_listing_parser_extracts_source_card_metadata() -> None:
    parser = ListingParser()
    payload = parser.parse(LISTING_HTML, page_index=2)
    assert payload["total_results"] == 5907
    assert payload["total_pages"] == 296
    assert len(payload["results"]) == 1
    record = payload["results"][0]
    assert record["title"].startswith("số 47/2026/DS-PT")
    assert record["document_type"] == "Bản án"
    assert record["document_number"] == "47/2026/DS-PT"
    assert record["issued_date"] == "2026-01-23"
    assert record["published_date"] == "2026-03-01"
    assert record["court_name"] == "Tòa Phúc thẩm Tòa án nhân dân tối cao tại Hà Nội"
    assert record["case_style"] == "Dân sự"
    assert record["legal_relation"] == "Tranh chấp về thừa kế tài sản"
    assert record["adjudication_level"] == "Phúc thẩm"
    assert record["precedent_applied"] == "Không"
    assert record["correction_count"] == "0"
    assert record["precedent_vote_count"] == "0"
    assert "Tranh chấp quyền sử dụng đất" in record["summary_text"]
    assert "Tổng số lượt được bình chọn" in record["source_card_text"]
    assert "Description_pub" in record["source_card_html"]
    assert record["page_index"] == 2


def test_listing_parser_ignores_weak_document_numbers() -> None:
    parser = ListingParser()
    payload = parser.parse(LISTING_HTML_WITH_WEAK_NUMBER, page_index=1)
    assert payload["results"][0]["document_number"] == ""


def test_detail_parser_dispatches_judgment() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_JUDGMENT_HTML, "https://example.com/ban-an")
    assert payload["document_type"] == "Bản án"
    assert payload["title"] == "Bản án dân sự phúc thẩm số 47/2026/DS-PT"
    assert payload["document_number"] == "47/2026/DS-PT"
    assert payload["precedent_applied"] == "Không"
    assert payload["correction_count"] == "0"
    assert payload["pdf_url"].endswith("banan.pdf")


def test_detail_parser_dispatches_decision() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_DECISION_HTML, "https://example.com/quyet-dinh")
    assert payload["document_type"] == "Quyết định"
    assert payload["title"] == "Quyết định công nhận hòa giải thành"
    assert payload["document_number"] == "15/2026/QĐ-PT"
    assert payload["precedent_applied"] == "Không"
    assert payload["pdf_url"].endswith("quyetdinh.pdf")


def test_detail_parser_keeps_document_number_empty_when_heading_number_is_weak() -> None:
    parser = DetailCommonParser()
    payload = parser.parse(DETAIL_DECISION_WITH_WEAK_HEADING_HTML, "https://example.com/quyet-dinh-weak")
    assert payload["document_number"] == ""


def test_source_router_uses_playwright_for_search_actions_when_context_requests_it() -> None:
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
    context = SourceContext(source_mode="playwright", job_id=1)
    payload = router.call("load_filters", context)
    assert calls == ["playwright"]
    assert context.source_mode == "playwright"
    assert "selects" in payload


def test_source_router_keeps_requests_sticky_for_search_actions() -> None:
    calls: list[str] = []

    class RequestsClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("requests")
            return {"selects": {"court_level": []}, "hidden_fields": {}}

    class PlaywrightClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("playwright")
            return {"unexpected": True}

    router = SourceRouter(RequestsClient(), PlaywrightClient())
    context = SourceContext(source_mode="requests", job_id=1)
    payload = router.call("load_filters", context)
    assert calls == ["requests"]
    assert context.source_mode == "requests"
    assert "selects" in payload


def test_source_router_falls_back_to_requests_and_sticks_for_search_session() -> None:
    calls: list[str] = []

    class RequestsClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("requests")
            return {"selects": {"court_level": []}, "hidden_fields": {}}

    class PlaywrightClient:
        def load_filters(self) -> dict[str, object]:
            calls.append("playwright")
            raise RuntimeError("playwright timed out")

    router = SourceRouter(RequestsClient(), PlaywrightClient())
    context = SourceContext(source_mode="playwright", job_id=1)
    payload = router.call("load_filters", context)
    assert calls == ["playwright", "requests"]
    assert context.source_mode == "requests"
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


def test_search_service_falls_back_to_playwright_when_requests_pagination_changes_result_scope() -> None:
    class FakeRouter:
        def __init__(self) -> None:
            self.calls = []

        def call(self, action: str, context: SourceContext, filters: dict, page_index: int, state: dict | None) -> dict[str, object]:
            self.calls.append((action, context.source_mode, page_index, state))
            if page_index == 1:
                return {
                    "total_results": 37,
                    "total_pages": 2,
                    "results": [{"source_url": "https://example.com/1", "page_index": 1}],
                    "state": {"page": 1, "values": filters},
                }
            if context.source_mode == "requests":
                return {
                    "total_results": 764,
                    "total_pages": 39,
                    "results": [{"source_url": "https://example.com/2", "page_index": 2}],
                    "state": {"page": 2, "values": filters},
                }
            return {
                "total_results": 37,
                "total_pages": 2,
                "results": [{"source_url": "https://example.com/2-good", "page_index": 2}],
                "state": {"page": 2, "values": filters},
            }

    service = SearchService(FakeRouter())
    preview = service.preview({"keyword": "tranh chap", "date_from": "2026-01-01", "date_to": "2026-03-02"}, page_index=1, context=SourceContext(source_mode="requests"))
    page2 = service.page(preview.preview_id, 2)
    assert preview.source_mode == "requests"
    assert page2.source_mode == "playwright"
    assert page2.total_results == 37
    assert page2.total_pages == 2
    assert page2.results[0]["source_url"] == "https://example.com/2-good"


def test_requests_client_remembers_compatibility_mode_per_host() -> None:
    client = RequestsSourceClient()
    calls: list[tuple[str, bool]] = []

    def fake_send(method: str, url: str, *, verify: bool, **kwargs: object) -> Response:
        calls.append((url, verify))
        if len(calls) == 1 and verify:
            raise requests.exceptions.SSLError("tls failed")
        response = Response()
        response.status_code = 200
        response._content = b"ok"
        response.encoding = "utf-8"
        response.url = url
        return response

    client._send = fake_send  # type: ignore[method-assign]

    response, tls_mode = client._request("GET", "https://example.com/first")
    assert response.status_code == 200
    assert tls_mode == "compatibility"
    assert calls == [
        ("https://example.com/first", True),
        ("https://example.com/first", False),
    ]

    calls.clear()
    response, tls_mode = client._request("GET", "https://example.com/second")
    assert response.status_code == 200
    assert tls_mode == "compatibility"
    assert calls == [("https://example.com/second", False)]


def test_requests_client_warm_up_tls_cache_primes_host_cache() -> None:
    client = RequestsSourceClient()
    calls: list[tuple[str, bool, bool]] = []

    def fake_send(method: str, url: str, *, verify: bool, **kwargs: object) -> Response:
        calls.append((url, verify, bool(kwargs.get("stream"))))
        if len(calls) == 1 and verify:
            raise requests.exceptions.SSLError("tls failed")
        response = Response()
        response.status_code = 200
        response._content = b""
        response.encoding = "utf-8"
        response.url = url
        return response

    client._send = fake_send  # type: ignore[method-assign]

    tls_mode = client.warm_up_tls_cache("https://example.com/bootstrap")
    assert tls_mode == "compatibility"
    assert calls == [
        ("https://example.com/bootstrap", True, True),
        ("https://example.com/bootstrap", False, True),
    ]

    calls.clear()
    response, tls_mode = client._request("GET", "https://example.com/next")
    assert response.status_code == 200
    assert tls_mode == "compatibility"
    assert calls == [("https://example.com/next", False, False)]


def test_requests_client_search_page_posts_webforms_pagination_eventtarget() -> None:
    client = RequestsSourceClient()
    captured_posts: list[dict[str, object]] = []

    def fake_request(method: str, url: str, *, data: dict[str, object] | None = None, tls_mode: str | None = None, **kwargs: object):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.url = url
        if method == "GET":
            response._content = FILTER_HTML.encode("utf-8")
            return response, "secure"
        captured_posts.append(dict(data or {}))
        response._content = (FILTER_HTML + LISTING_HTML).encode("utf-8")
        return response, "secure"

    client._request = fake_request  # type: ignore[method-assign]

    filters = {
        "keyword": "tranh chap",
        "court_level": "TW",
        "court": "TANDTC",
        "adjudication_level": "PT",
        "document_type": "BA",
        "case_style": "DS",
        "legal_relation": "QHPL",
        "date_from": "2026-01-01",
        "date_to": "02/03/2026",
        "precedent_applied": True,
        "precedent_voted": True,
    }
    first = client.search_preview(filters, page_index=1, state=None)
    second = client.search_preview(filters, page_index=5, state=first["state"])

    assert second["results"][0]["page_index"] == 5
    assert len(captured_posts) == 4
    assert captured_posts[0]["__EVENTTARGET"] == "ctl00$Content_home_Public$ctl00$Drop_Levels_top"
    assert captured_posts[1]["__EVENTTARGET"] == "ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top"
    assert captured_posts[2]["__EVENTTARGET"] == ""
    page_post = captured_posts[3]
    assert page_post["__EVENTTARGET"] == "ctl00$Content_home_Public$ctl00$DropPages"
    assert page_post["ctl00$Content_home_Public$ctl00$DropPages"] == "5"
    assert page_post["ctl00$Content_home_Public$ctl00$txtKeyword_top"] == "tranh chap"
    assert page_post["ctl00$Content_home_Public$ctl00$txtKeyword"] == "tranh chap"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_Levels_top"] == "TW"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_Levels"] == "TW"
    assert page_post["ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top"] == "TANDTC"
    assert page_post["ctl00$Content_home_Public$ctl00$Ra_Drop_Courts"] == "TANDTC"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH_top"] == "PT"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH"] == "PT"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH_top"] == "BA"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH"] == "BA"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH_top"] == "DS"
    assert page_post["ctl00$Content_home_Public$ctl00$Drop_CASES_STYLES_SEARCH"] == "DS"
    assert page_post["ctl00$Content_home_Public$ctl00$Ra_Case_shows_search_top"] == "QHPL"
    assert page_post["ctl00$Content_home_Public$ctl00$Ra_Case_shows_search"] == "QHPL"
    assert page_post["ctl00$Content_home_Public$ctl00$Rad_DATE_FROM_top"] == "01/01/2026"
    assert page_post["ctl00$Content_home_Public$ctl00$Rad_DATE_FROM"] == "01/01/2026"
    assert page_post["ctl00$Content_home_Public$ctl00$Rad_DATE_TO_top"] == "02/03/2026"
    assert page_post["ctl00$Content_home_Public$ctl00$Rad_DATE_TO"] == "02/03/2026"
    assert page_post["ctl00$Content_home_Public$ctl00$check_anle_top"] == "on"
    assert page_post["ctl00$Content_home_Public$ctl00$check_anle"] == "on"
    assert page_post["ctl00$Content_home_Public$ctl00$check_anle_voted_top"] == "on"
    assert page_post["ctl00$Content_home_Public$ctl00$check_anle_voted"] == "on"


def test_requests_client_dependent_options_posts_primary_control_names_only() -> None:
    client = RequestsSourceClient()
    captured_posts: list[dict[str, object]] = []

    def fake_request(method: str, url: str, *, data: dict[str, object] | None = None, tls_mode: str | None = None, **kwargs: object):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.url = url
        if method == "GET":
            response._content = FILTER_HTML.encode("utf-8")
            return response, "secure"
        captured_posts.append(dict(data or {}))
        response._content = FILTER_HTML.encode("utf-8")
        return response, "secure"

    client._request = fake_request  # type: ignore[method-assign]

    state = client.load_filters()["state"]
    client.load_dependent_options("court_level", "TW", state)

    assert len(captured_posts) == 1
    dependent_post = captured_posts[0]
    assert dependent_post["__EVENTTARGET"] == "ctl00$Content_home_Public$ctl00$Drop_Levels_top"
    assert dependent_post["ctl00$Content_home_Public$ctl00$Drop_Levels_top"] == "TW"
    assert "ctl00$Content_home_Public$ctl00$Drop_Levels" not in dependent_post
    assert "ctl00$Content_home_Public$ctl00$Ra_Drop_Courts" not in dependent_post
    assert "ctl00$Content_home_Public$ctl00$Ra_Drop_Courts_top" not in dependent_post


def test_requests_client_court_level_dependency_returns_court_and_adjudication_level() -> None:
    client = RequestsSourceClient()

    def fake_request(method: str, url: str, *, data: dict[str, object] | None = None, tls_mode: str | None = None, **kwargs: object):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.url = url
        response._content = FILTER_HTML.encode("utf-8")
        return response, "secure"

    client._request = fake_request  # type: ignore[method-assign]

    payload = client.load_dependent_options("court_level", "TW", {"fields": FormParser().parse_form_state(FILTER_HTML)["fields"]})

    assert "court" in payload["selects"]
    assert "adjudication_level" in payload["selects"]


def test_requests_client_search_preview_uses_latest_hidden_fields_after_court_level_postback() -> None:
    client = RequestsSourceClient()
    captured_posts: list[dict[str, object]] = []

    def fake_request(method: str, url: str, *, data: dict[str, object] | None = None, tls_mode: str | None = None, **kwargs: object):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.url = url
        if method == "GET":
            response._content = FILTER_HTML.encode("utf-8")
            return response, "secure"
        captured_posts.append(dict(data or {}))
        if len(captured_posts) == 1:
            response._content = DEPENDENT_COURT_HTML.encode("utf-8")
        else:
            response._content = SEARCH_RESULTS_WITH_SELECTION_PAGE.encode("utf-8")
        return response, "secure"

    client._request = fake_request  # type: ignore[method-assign]

    payload = client.search_preview(
        {
            "court_level": "TW",
            "adjudication_level": "2",
            "document_type": "1",
            "date_from": "2026-01-01",
            "date_to": "2026-03-02",
            "precedent_applied": True,
        },
        page_index=1,
        state=None,
    )

    assert len(captured_posts) == 2
    dependent_post = captured_posts[0]
    final_post = captured_posts[1]
    assert dependent_post["__EVENTTARGET"] == "ctl00$Content_home_Public$ctl00$Drop_Levels_top"
    assert final_post["__VIEWSTATE"] == "after-court"
    assert final_post["ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH_top"] == "2"
    assert final_post["ctl00$Content_home_Public$ctl00$Drop_LEVEL_JUDGMENT_SEARCH"] == "2"
    assert final_post["ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH_top"] == "1"
    assert final_post["ctl00$Content_home_Public$ctl00$Drop_STATUS_JUDGMENT_SEARCH"] == "1"
    assert payload["state"]["strict_filter_valid"] is True
    assert payload["state"]["invalid_fields"] == []


def test_requests_client_marks_invalid_search_state_when_echoed_values_do_not_match() -> None:
    client = RequestsSourceClient()

    def fake_request(method: str, url: str, *, data: dict[str, object] | None = None, tls_mode: str | None = None, **kwargs: object):
        response = Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response.url = url
        if method == "GET":
            response._content = FILTER_HTML.encode("utf-8")
            return response, "secure"
        response._content = (FILTER_HTML + LISTING_HTML).encode("utf-8")
        return response, "secure"

    client._request = fake_request  # type: ignore[method-assign]

    payload = client.search_preview({"document_type": "1", "adjudication_level": "2"}, page_index=1, state=None)
    assert payload["state"]["strict_filter_valid"] is False
    assert "document_type" in payload["state"]["invalid_fields"]
    assert "adjudication_level" in payload["state"]["invalid_fields"]


def test_form_service_dependent_options_reset_stale_child_values() -> None:
    from vietcase.services.form_service import FormService

    class FakeRouter:
        def call(self, action: str, context: SourceContext, parent_field: str, parent_value: str, source_state: dict[str, object]) -> dict[str, object]:
            assert action == "load_dependent_options"
            return {
                "selects": {
                    "court": [{"value": "", "label": "-----ch?n-----"}],
                    "adjudication_level": [{"value": "", "label": "-----ch?n-----"}],
                },
                "fields": {},
                "state": {"values": {"court_level": parent_value}},
            }

    service = FormService(FakeRouter())  # type: ignore[arg-type]
    form_state_id = service._save_state(
        {
            "source_state": {
                "values": {
                    "court_level": "OLD",
                    "court": "OLD_CHILD",
                    "adjudication_level": "OLD_ADJ",
                }
            },
            "source_mode": "requests",
            "values": {
                "court_level": "OLD",
                "court": "OLD_CHILD",
                "adjudication_level": "OLD_ADJ",
            },
        }
    )

    service.get_dependent_options("court_level", "TW", form_state_id)
    saved = service.get_state(form_state_id)
    assert saved is not None
    assert saved["values"]["court_level"] == "TW"
    assert "court" not in saved["values"]
    assert "adjudication_level" not in saved["values"]


def test_search_service_preview_falls_back_to_playwright_when_requests_filter_state_invalid() -> None:
    class FakeRouter:
        def __init__(self) -> None:
            self.calls = []

        def call(self, action: str, context: SourceContext, filters: dict, page_index: int, state: dict | None) -> dict[str, object]:
            self.calls.append((action, context.source_mode, page_index, state))
            if context.source_mode == "requests":
                return {
                    "total_results": 502,
                    "total_pages": 26,
                    "results": [{"source_url": "https://example.com/bad", "page_index": 1}],
                    "state": {
                        "values": filters,
                        "strict_filter_valid": False,
                        "invalid_fields": ["document_type", "adjudication_level"],
                        "echoed_values": {"document_type": "", "adjudication_level": ""},
                    },
                }
            return {
                "total_results": 12,
                "total_pages": 1,
                "results": [{"source_url": "https://example.com/good", "page_index": 1}],
                "state": {
                    "values": filters,
                    "strict_filter_valid": True,
                    "invalid_fields": [],
                    "echoed_values": {"document_type": "1", "adjudication_level": "2"},
                },
            }

    service = SearchService(FakeRouter())
    preview = service.preview(
        {"document_type": "1", "adjudication_level": "2"},
        page_index=1,
        context=SourceContext(source_mode="requests"),
    )
    assert preview.source_mode == "playwright"
    assert preview.total_results == 12
    assert preview.results[0]["source_url"] == "https://example.com/good"
