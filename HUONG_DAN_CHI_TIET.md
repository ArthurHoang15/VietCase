# Hướng Dẫn Setup Và Sử Dụng VietCase Từ Đầu

Tài liệu này dành cho người không rành kỹ thuật. Chỉ cần làm đúng từng bước là có thể chạy được.

## 1. VietCase là gì?

VietCase là một ứng dụng chạy trên máy của bạn để:

- tìm kiếm bản án, quyết định
- tải file PDF về máy
- theo dõi tiến độ tải
- tìm lại các file đã tải sau này

Bạn sẽ dùng VietCase qua trình duyệt web, không phải dùng dòng lệnh hằng ngày.

## 2. Bạn cần chuẩn bị gì?

Trước khi cài, máy cần có:

- Windows
- Internet
- Python 3.11 hoặc mới hơn

Nếu bạn chưa có Python:

1. vào trang Python chính thức: `https://www.python.org/downloads/`
2. tải bản mới cho Windows
3. khi cài, nhớ tick ô `Add Python to PATH`
4. bấm `Install Now`

## 3. Tải VietCase về máy

Nếu bạn đã có sẵn thư mục `VietCase` thì bỏ qua bước này.

Nếu chưa có:

1. mở trang GitHub của dự án VietCase trên trình duyệt
2. tìm nút màu xanh tên là `Code`
3. bấm vào nút `Code`
4. trong bảng vừa hiện ra, bấm `Download ZIP`

Làm theo thứ tự này:

1. mở trang GitHub của dự án
2. bấm nút xanh `Code`
3. bấm `Download ZIP`
4. chờ máy tải xong file `.zip`
5. vào thư mục `Downloads` của máy
6. tìm file vừa tải về, thường có tên gần giống `VietCase-main.zip`
7. nhấp chuột phải vào file `.zip`
8. chọn `Extract All...` hoặc `Giải nén tất cả...`
9. bấm `Extract`
10. sau khi giải nén xong, bạn sẽ thấy một thư mục mới, thường có tên `VietCase-main`
11. nếu muốn dễ nhớ hơn, bạn có thể đổi tên thư mục đó thành `VietCase`
12. đặt thư mục ở nơi dễ tìm, ví dụ:

```text
C:\Users\TênBạn\Downloads\VietCase
```

Nếu bạn chưa từng dùng GitHub:

- bạn không cần biết cách dùng `git`
- bạn không cần cài GitHub Desktop
- bạn chỉ cần bấm `Code` rồi bấm `Download ZIP`
- sau đó giải nén như một file nén bình thường là đủ

## 4. Mở cửa sổ lệnh

Cách dễ nhất:

1. vào thư mục cha đang chứa folder `VietCase`
2. nhấp chuột phải vào chính folder `VietCase`
3. chọn `Open in Terminal`

Lúc này sẽ hiện một cửa sổ màu xanh hoặc đen. Đó là nơi bạn nhập lệnh cài và chạy app.

Nếu máy bạn không thấy nút `Open in Terminal`, làm theo cách dự phòng:

1. mở thư mục `VietCase`
2. bấm vào thanh địa chỉ của thư mục
3. gõ `powershell`
4. bấm `Enter`

## 5. Cài thư viện cần thiết

Trong cửa sổ PowerShell, nhập:

```bash
python -m pip install -r requirements.txt
```

Chờ đến khi chạy xong.

Nếu mất vài phút thì đó là bình thường.

## 6. Cài trình duyệt Chromium cho Playwright

Nhập tiếp:

```bash
python -m playwright install chromium
```

Lệnh này chỉ cần làm khi setup lần đầu, hoặc khi máy chưa có browser mà Playwright cần.

## 7. Chạy VietCase

Nhập:

```bash
python -m vietcase
```

Nếu chạy thành công, bạn sẽ thấy terminal hiện thông tin kiểu:

```text
Uvicorn running on http://127.0.0.1:8000
```

## 8. Mở app trên trình duyệt

Mở Chrome hoặc Edge, rồi vào:

```text
http://127.0.0.1:8000
```

Bạn sẽ thấy giao diện VietCase.

## 9. Cách dùng 3 trang chính

### Trang 1: Tìm kiếm

Đây là nơi bạn:

- nhập từ khóa
- chọn bộ lọc
- bấm `Tìm kiếm`
- xem kết quả
- chọn mục cần tải

Các nút tải ở trang này:

- `Tải mục đã chọn`: chỉ tải các kết quả bạn đã tick
- `Tải trang hiện tại`: tải toàn bộ kết quả đang hiện trên trang đó
- `Tải toàn bộ theo bộ lọc`: tải toàn bộ kết quả đúng theo bộ lọc bạn đã chọn

Sau khi bấm tải, app sẽ chuyển bạn sang trang `Lịch sử tải`.

### Trang 2: Lịch sử tải

Đây là nơi bạn theo dõi các đợt tải.

Bạn sẽ thấy:

- trạng thái job
- tiến độ đã tải được bao nhiêu
- số lỗi
- nguồn truy cập đang dùng

Ý nghĩa một số trạng thái:

- `Đang chờ`: job đang xếp hàng
- `Đang chạy`: job đang tải
- `Tạm dừng`: job đã tạm dừng
- `Đã hủy`: job đã bị hủy
- `Hoàn tất`: job đã tải xong
- `Bị gián đoạn`: app bị tắt trong lúc job đang chạy

Các nút:

- `Tiếp tục`: chạy lại job đang tạm dừng hoặc bị gián đoạn
- `Tạm dừng`: tạm dừng job đang chạy
- `Hủy`: dừng hẳn job
- `Xóa`: xóa job khỏi lịch sử

Lưu ý:

- xóa job khỏi lịch sử không có nghĩa là xóa file PDF đã tải

### Trang 3: Tài liệu đã tải

Đây là nơi tìm lại các file PDF đã lưu về máy.

Bạn có thể:

- tìm theo từ khóa
- lọc theo loại văn bản, tòa án, loại vụ việc, quan hệ pháp luật, ngày
- bấm `Mở tài liệu` để mở PDF trong tab mới
- xóa từng file hoặc xóa nhiều file

## 10. File tải về nằm ở đâu?

Các file PDF được lưu trong thư mục:

```text
downloads\
```

Mỗi đợt tải sẽ có một thư mục riêng theo thời gian, ví dụ:

```text
downloads\18-04-2026-11-00
```

Trong mỗi thư mục job sẽ là các file PDF của đợt tải đó.

## 11. Cách tắt app

Quay lại cửa sổ PowerShell đang chạy VietCase, rồi bấm:

```text
Ctrl + C
```

Nếu được hỏi có muốn dừng không, gõ:

```text
Y
```

## 12. Lần sau mở lại thì làm thế nào?

Mỗi lần muốn dùng lại:

1. mở thư mục `VietCase`
2. nhấp chuột phải vào folder `VietCase`, chọn `Open in Terminal`
3. chạy:

```bash
python -m vietcase
```

4. mở trình duyệt vào:

```text
http://127.0.0.1:8000
```

Bạn không cần cài lại thư viện mỗi lần.

## 13. Nếu gặp lỗi thường gặp

### Lỗi `python is not recognized`

Nguyên nhân:

- máy chưa cài Python
- hoặc cài rồi nhưng chưa tick `Add Python to PATH`

Cách xử lý:

- cài lại Python và nhớ tick `Add Python to PATH`

### Lỗi không mở được trang web

Thử:

- kiểm tra terminal còn đang chạy không
- mở đúng địa chỉ `http://127.0.0.1:8000`
- nếu cổng 8000 bận, chạy:

```bash
python -m vietcase --port 8010
```

Sau đó mở:

```text
http://127.0.0.1:8010
```

### Lỗi thiếu thư viện

Chạy lại:

```bash
python -m pip install -r requirements.txt
```

### Dropdown tải chậm hoặc search chậm

Thông thường app hiện tại đã tối ưu để nhanh hơn nhiều.

Nếu vẫn chậm:

- kiểm tra mạng
- tắt app rồi mở lại
- refresh trình duyệt bằng `Ctrl + F5`

## 14. Khi cập nhật VietCase

Nếu có bản mới:

1. cập nhật source code
2. chạy lại:

```bash
python -m pip install -r requirements.txt
```

3. nếu có thay đổi liên quan Playwright, chạy thêm:

```bash
python -m playwright install chromium
```

4. chạy lại app:

```bash
python -m vietcase
```

## 15. Gợi ý cách dùng an toàn

- Nên thử tìm kiếm và tải ít file trước để làm quen.
- Khi tải nhiều, theo dõi ở trang `Lịch sử tải`.
- Không xóa trực tiếp file trong `downloads` nếu vẫn muốn danh sách trên web khớp hoàn toàn.
- Nếu đã xóa file bằng File Explorer, một số bản ghi cũ trên app có thể hiện là file không còn trên máy.

## 16. Lưu ý pháp lý

VietCase lấy dữ liệu từ cổng công bố bản án, quyết định của Tòa án.

Bạn cần tự rà soát:

- quy định sử dụng dữ liệu
- cách lưu trữ
- việc chia sẻ lại
- việc tái công bố dữ liệu

Nói ngắn gọn: chỉ dùng dữ liệu khi bạn hiểu rõ mục đích và trách nhiệm pháp lý của mình.
