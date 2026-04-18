# VietCase

VietCase là ứng dụng web chạy trên máy cá nhân để:

- tra cứu bản án, quyết định từ cổng công bố của Tòa án
- tải PDF về máy
- theo dõi lịch sử tải
- tìm lại các tài liệu đã tải

Nếu bạn muốn hướng dẫn rất dễ làm theo cho người không rành kỹ thuật, xem:

- [HUONG_DAN_CHI_TIET.md](HUONG_DAN_CHI_TIET.md)

## Chạy nhanh

### 1. Cài thư viện

```bash
python -m pip install -r requirements.txt
```

### 2. Cài Chromium cho Playwright

```bash
python -m playwright install chromium
```

### 3. Mở ứng dụng

```bash
python -m vietcase
```

Sau đó mở trình duyệt tại:

```text
http://127.0.0.1:8000
```

## Các trang chính

- `Tìm kiếm`: chọn bộ lọc, xem kết quả, tải mục đã chọn hoặc tải toàn bộ theo bộ lọc
- `Lịch sử tải`: theo dõi job đang chạy, tạm dừng, hủy, xóa
- `Tài liệu đã tải`: tìm lại file PDF đã lưu trên máy, mở file, xóa file

## Cấu trúc dữ liệu chính

- `downloads/`: nơi lưu các file PDF đã tải
- `data/app.db`: cơ sở dữ liệu cục bộ của ứng dụng
- `data/logs/`: log chạy ứng dụng
- `data/search_debug/`: snapshot debug search khi được bật

## Yêu cầu môi trường

- Python 3.11 hoặc mới hơn
- Windows
- Kết nối mạng ổn định

## Lưu ý

- Ứng dụng ưu tiên `requests` cho tìm kiếm để nhanh hơn, và chỉ dùng `Playwright` khi cần fallback.
- Một số PDF scan có thể không trích được text đầy đủ.
- Dữ liệu lấy từ cổng công bố bản án của Tòa án. Người dùng cần tự rà soát quy định sử dụng, lưu trữ, chia sẻ và tái công bố dữ liệu.
