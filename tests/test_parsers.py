from scrape_ban_an_kdtm import CourtParsers


LISTING_HTML = """
<html>
  <body>
    <span id="ctl00_Content_home_Public_ctl00_lbl_count_record"><b>36494</b></span>
    <span id="ctl00_Content_home_Public_ctl00_LbShowtotal"><b>1825</b></span>
    <div class="list-group" id="List_group_pub">
      <div class="list-group-item">
        <a class="echo_id_pub" href="/2ta2086071t1cvn/chi-tiet-ban-an" target="_blank">
          <h4 class="list-group-item-heading">
            <label>Bản án:</label>
            <span>
              số 13/2025/KDTM-ST ngày 14/09/2025 của Tòa án nhân dân khu vực 3 - Tây Ninh, tỉnh Tây Ninh
              <time>(28.03.2026)</time>
            </span>
          </h4>
        </a>
        <div class="row">
          <div class="col-md-12">
            <p><label>Quan hệ pháp luật:</label><span>Tranh chấp về mua bán hàng hóa</span></p>
          </div>
        </div>
        <div class="row">
          <div class="col-md-6"><label>Cấp xét xử:</label><span>Sơ thẩm</span></div>
          <div class="col-md-6"><label>Áp dụng án lệ:</label><span>Không</span></div>
        </div>
        <div class="row">
          <div class="col-md-6"><label>Loại vụ/việc:</label><span>Kinh doanh thương mại</span></div>
          <div class="col-md-6"><label>Đính chính:</label><span>0</span></div>
        </div>
        <p class="Description_pub">
          <label>Thông tin về vụ/việc:</label>
          <span>Công ty D tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất</span>
        </p>
      </div>
    </div>
  </body>
</html>
"""


DETAIL_JUDGMENT_HTML = """
<html>
  <head>
    <title>Bản án: số 13/2025/KDTM-ST ngày 14/09/2025 của Tòa án nhân dân khu vực 3 - Tây Ninh</title>
  </head>
  <body>
    <li class="list-group-item">Tên bản án: Công ty D "Tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất" (28.03.2026)</li>
    <li class="list-group-item">Quan hệ pháp luật: Tranh chấp về mua bán hàng hóa</li>
    <li class="list-group-item">Cấp xét xử: Sơ thẩm</li>
    <li class="list-group-item">Loại vụ/việc: Kinh doanh thương mại</li>
    <li class="list-group-item">Tòa án xét xử: Tòa án nhân dân khu vực 3 - Tây Ninh, tỉnh Tây Ninh</li>
    <li class="list-group-item">Áp dụng án lệ: Không</li>
    <li class="list-group-item">Đính chính: 0</li>
    <li class="list-group-item">Thông tin về vụ/việc: Công ty D tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất</li>
    <div class="title_detai_tab_pub">Ngày tuyên án: 14/09/2025</div>
    <a href="/5ta2086071t1cvn/demco_toan_cau.pdf">13/2025/KDTM-ST.pdf</a>
  </body>
</html>
"""


DETAIL_DECISION_HTML = """
<html>
  <head>
    <title>Quyết định: số 124/2025/QĐST-KDTM ngày 20/11/2025 của Tòa án nhân dân khu vực 4 - Hà Nội</title>
  </head>
  <body>
    <li class="list-group-item">Tên quyết định: QUYẾT ĐỊNH ĐÌNH CHỈ GIẢI QUYẾT VỤ ÁN KINH DOANH THƯƠNG MẠI (28.03.2026)</li>
    <li class="list-group-item">Quan hệ pháp luật: Tranh chấp giữa công ty với các thành viên công ty</li>
    <li class="list-group-item">Cấp xét xử: Sơ thẩm</li>
    <li class="list-group-item">Loại vụ/việc: Kinh doanh thương mại</li>
    <li class="list-group-item">Tòa án xét xử: Tòa án nhân dân khu vực 4 - Hà Nội, TP. Hà Nội</li>
    <li class="list-group-item">Áp dụng án lệ: Không</li>
    <li class="list-group-item">Đính chính: 0</li>
    <li class="list-group-item">Thông tin về vụ/việc: ĐÌNH CHỈ GIẢI QUYẾT VỤ ÁN KINH DOANH THƯƠNG MẠI</li>
    <div class="title_detai_tab_pub">Ngày tuyên án: 20/11/2025</div>
    <iframe src="/Resources/pdfjs/web/viewer.html?file=%2F3ta2086316t1cvn%2F"></iframe>
    <a href="/5ta2086316t1cvn/QDDC_SILICONL.pdf">124/2025/QĐST-KDTM.pdf</a>
  </body>
</html>
"""


def test_parse_listing_page():
    result = CourtParsers.parse_listing_page(LISTING_HTML, page_index=1, crawl_time="2026-03-29T00:00:00Z")
    assert result.total_results == 36494
    assert result.total_pages == 1825
    assert len(result.records) == 1
    record = result.records[0]
    assert record["document_type"] == "Bản án"
    assert record["case_style"] == "Kinh doanh thương mại"
    assert record["document_number"] == "13/2025/KDTM-ST"
    assert record["issued_date"] == "2025-09-14"
    assert record["published_date"] == "2026-03-28"
    assert record["summary_text"] == "Công ty D tranh chấp hợp đồng chuyển nhượng quyền sử dụng đất"


def test_parse_detail_judgment_page():
    record = CourtParsers.parse_detail_page(
        DETAIL_JUDGMENT_HTML,
        source_url="https://congbobanan.toaan.gov.vn/2ta2086071t1cvn/chi-tiet-ban-an",
        crawl_time="2026-03-29T00:00:00Z",
    )
    assert record["document_type"] == "Bản án"
    assert record["issued_date"] == "2025-09-14"
    assert record["published_date"] == "2026-03-28"
    assert record["court"] == "Tòa án nhân dân khu vực 3 - Tây Ninh, tỉnh Tây Ninh"
    assert record["pdf_url"].endswith("/5ta2086071t1cvn/demco_toan_cau.pdf")


def test_parse_detail_decision_page():
    record = CourtParsers.parse_detail_page(
        DETAIL_DECISION_HTML,
        source_url="https://congbobanan.toaan.gov.vn/2ta2086316t1cvn/chi-tiet-ban-an",
        crawl_time="2026-03-29T00:00:00Z",
    )
    assert record["document_type"] == "Quyết định"
    assert record["issued_date"] == "2025-11-20"
    assert record["published_date"] == "2026-03-28"
    assert record["summary_text"] == "ĐÌNH CHỈ GIẢI QUYẾT VỤ ÁN KINH DOANH THƯƠNG MẠI"
    assert record["pdf_url"].endswith("/5ta2086316t1cvn/QDDC_SILICONL.pdf")
