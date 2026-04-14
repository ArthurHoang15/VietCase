# VietCase

VietCase là công cụ Python dùng để thu thập và chuẩn hóa dữ liệu bản án, quyết định từ cổng công bố bản án của Tòa án nhân dân. Phiên bản hiện tại được cấu hình để crawl nhóm `Kinh doanh thương mại` trong khoảng thời gian xác định, lưu cả dữ liệu thô và dữ liệu đã chuẩn hóa để phục vụ tra cứu, phân tích hoặc xử lý tiếp theo.

Project này phù hợp cho hai nhóm người dùng:

- Người cần chạy công cụ để tiếp tục quá trình crawl và lấy dữ liệu.
- Lập trình viên muốn hiểu cách crawler hoạt động, chỉnh sửa parser hoặc mở rộng luồng xử lý.

## Mục tiêu chính

- Tự động lấy danh sách bản án, quyết định theo bộ lọc tìm kiếm.
- Truy cập từng trang chi tiết để lấy metadata và nội dung toàn văn khi có thể.
- Tải file PDF gốc nếu trang chi tiết cung cấp.
- Ghi dữ liệu theo dạng có thể resume khi quá trình bị dừng giữa chừng.
- Tách rõ dữ liệu thô (`raw`) và dữ liệu chuẩn hóa (`normalized`).

## Tính năng hiện có

- CLI với 3 lệnh: `search`, `detail`, `resume`.
- Ưu tiên dùng Playwright để thao tác như trình duyệt thật.
- Tự fallback sang `requests` nếu browser Playwright bị chặn bởi website đích.
- Có retry, rate limit, checkpoint và khả năng chạy tiếp.
- Lưu metadata chi tiết dưới dạng JSON Lines (`.jsonl`).
- Tải PDF và trích text bằng `pypdf` nếu file PDF có text layer.
- Có test parser cơ bản cho trang danh sách, bản án và quyết định.

## Cấu trúc project

```text
VietCase/
├─ scrape_ban_an_kdtm.py
├─ requirements.txt
├─ tests/
│  └─ test_parsers.py
├─ output/
│  ├─ checkpoint.json
│  ├─ raw/
│  │  ├─ search/
│  │  ├─ detail/
│  │  └─ pdf/
│  └─ normalized/
│     ├─ search_results.jsonl
│     ├─ documents.jsonl
│     ├─ failures.jsonl
│     └─ run_config.json
└─ README.md
```

## Yêu cầu môi trường

- Python 3.11 hoặc mới hơn
- Windows PowerShell hoặc terminal tương đương
- Kết nối mạng ổn định

## Cài đặt

### 1. Cài thư viện Python

```bash
pip install -r requirements.txt
```

### 2. Cài browser cho Playwright

```bash
python -m playwright install chromium
```

Nếu môi trường không chạy được Playwright hoặc bị website chặn, script vẫn có thể fallback sang `requests` cho nhiều tác vụ crawl.

## Cách sử dụng

### 1. Crawl danh sách kết quả tìm kiếm

```bash
python scrape_ban_an_kdtm.py search --output-dir output
```

Lệnh này sẽ:

- Mở trang tìm kiếm.
- Áp bộ lọc ngày và loại vụ việc.
- Crawl từng trang danh sách.
- Ghi HTML thô vào `output/raw/search/`.
- Ghi kết quả chuẩn hóa vào `output/normalized/search_results.jsonl`.
- Cập nhật trạng thái vào `output/checkpoint.json`.

### 2. Crawl chi tiết từng hồ sơ

```bash
python scrape_ban_an_kdtm.py detail --output-dir output
```

Lệnh này sẽ:

- Đọc danh sách URL từ `search_results.jsonl`.
- Bỏ qua các URL đã có trong `documents.jsonl`.
- Tải trang chi tiết và file PDF nếu có.
- Ghi HTML chi tiết vào `output/raw/detail/`.
- Ghi PDF gốc vào `output/raw/pdf/`.
- Ghi bản ghi hoàn chỉnh vào `output/normalized/documents.jsonl`.

### 3. Chạy tiếp sau khi bị dừng

```bash
python scrape_ban_an_kdtm.py resume --output-dir output
```

Lệnh này sẽ:

- Kiểm tra `checkpoint.json`.
- Nếu phần `search` chưa xong thì chạy tiếp `search`.
- Sau đó tiếp tục phần `detail`.

## Tùy chọn dòng lệnh

Tất cả 3 lệnh đều hỗ trợ các tham số chính sau:

- `--date-from`: ngày bắt đầu, định dạng `YYYY-MM-DD`
- `--date-to`: ngày kết thúc, định dạng `YYYY-MM-DD`
- `--case-style`: mã loại vụ việc, mặc định là `2`
- `--include-document-types`: mặc định là `all`
- `--headless` hoặc `--no-headless`: bật hoặc tắt chế độ ẩn trình duyệt
- `--rate-limit-ms`: độ trễ giữa các lần xử lý
- `--max-retries`: số lần thử lại khi lỗi
- `--output-dir`: thư mục đầu ra
- `--resume`: bật chế độ resume
- `--max-pages`: giới hạn số trang danh sách
- `--max-details`: giới hạn số hồ sơ chi tiết

Ví dụ chạy thử trên quy mô nhỏ:

```bash
python scrape_ban_an_kdtm.py search --output-dir output --max-pages 5 --rate-limit-ms 500
python scrape_ban_an_kdtm.py detail --output-dir output --max-details 10 --rate-limit-ms 500
```

## Dữ liệu đầu ra

### `output/normalized/search_results.jsonl`

Chứa metadata lấy từ trang danh sách, ví dụ:

- `source_url`
- `document_id`
- `document_type`
- `case_style`
- `document_number`
- `issued_date`
- `court`
- `published_date`
- `title`
- `summary_text`
- `page_index`
- `result_index`

### `output/normalized/documents.jsonl`

Chứa bản ghi hoàn chỉnh sau khi crawl chi tiết, bao gồm thêm:

- `legal_relation`
- `level`
- `precedent_applied`
- `correction_count`
- `pdf_url`
- `pdf_path`
- `full_text`

### `output/checkpoint.json`

Chứa trạng thái tiến độ để có thể resume.

### `output/normalized/failures.jsonl`

Ghi các mục crawl thất bại để kiểm tra lại sau.

## Cách hoạt động ở mức kỹ thuật

Luồng chính của script gồm 3 lớp:

1. `CourtCrawler`

- Điều phối quá trình crawl danh sách và chi tiết.
- Quản lý retry, rate limit, checkpoint, persist dữ liệu.

2. `CourtParsers`

- Parse HTML trang danh sách.
- Parse HTML trang chi tiết.
- Chuẩn hóa một số trường như ngày tháng, số bản án, tên tòa.

3. `OutputLayout` và `CheckpointStore`

- Quản lý cấu trúc thư mục đầu ra.
- Lưu và đọc trạng thái crawl.

Về chiến lược truy cập:

- Script ưu tiên Playwright khi có thể.
- Nếu browser bị chặn, script fallback sang `requests`.
- Khi có PDF, script dùng `pypdf` để trích text.

## Kiểm thử

Chạy test:

```bash
python -m pytest -q
```

Test hiện tại tập trung vào parser:

- Parse 1 trang danh sách.
- Parse 1 trang chi tiết bản án.
- Parse 1 trang chi tiết quyết định.

## Giới hạn hiện tại

- Một số PDF là file scan hoặc không có text layer, khi đó `pypdf` có thể không trích được `full_text`.
- Chưa tích hợp OCR cho PDF scan.
- Website đích có thể thay đổi HTML hoặc cơ chế chống bot, khiến parser hoặc luồng Playwright cần cập nhật.
- Dữ liệu và số lượng kết quả có thể thay đổi theo thời gian vì website nguồn tiếp tục cập nhật.

## Lưu ý pháp lý

Project này tương tác với dữ liệu từ cổng công bố bản án của Tòa án nhân dân. Việc sử dụng, lưu trữ, chia sẻ hoặc tái phát hành dữ liệu cần được xem xét cẩn thận theo điều kiện sử dụng của website nguồn và các quy định pháp lý liên quan.

Bạn nên đặc biệt lưu ý:

- Chỉ sử dụng dữ liệu khi có căn cứ pháp lý hoặc mục đích phù hợp.
- Không mặc định coi dữ liệu scrape được là có thể tái phân phối công khai.
- Tự rà soát trách nhiệm pháp lý trước khi dùng dữ liệu cho sản phẩm, thương mại hóa hoặc công bố rộng rãi.

## Gợi ý vận hành

- Nếu muốn crawl dài hạn, nên chạy `search` trước rồi mới chạy `detail`.
- Nếu cần chuyển sang máy khác để crawl tiếp, chỉ cần mang các file trong `normalized/` và `checkpoint.json`; không nhất thiết phải mang toàn bộ `raw/`.
