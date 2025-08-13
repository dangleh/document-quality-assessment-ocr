# Phân Tích Tiêu Chí Chất Lượng Tài Liệu

Tài liệu này phân tích chi tiết các tiêu chí được sử dụng trong dự án để đánh giá chất lượng của tài liệu đầu vào. Mỗi tiêu chí được mô tả về mục đích, cách thức hoạt động và hàm/logic cụ thể được sử dụng để kiểm tra.

---

### 1. File Integrity (Tính toàn vẹn của tệp)

- **Mô tả:** Kiểm tra xem tệp có bị hỏng hay không và có thể mở và xử lý được không. Đây là một tiêu chí bắt buộc (`required`).
- **Cách Hoạt Động:** Hệ thống cố gắng trích xuất hình ảnh từ tệp tài liệu (PDF, TIFF, v.v.). Nếu quá trình này thành công và trả về ít nhất một hình ảnh, tệp được coi là hợp lệ. Nếu có lỗi xảy ra trong quá trình trích xuất, tệp sẽ bị từ chối.
- **Hàm/Logic Chính:** `_get_images_from_path` trong `src/criteria.py`.

---

### 2. Resolution (Độ phân giải)

- **Mô tả:** Đảm bảo tài liệu có đủ độ phân giải (DPI) để có thể đọc và xử lý OCR một cách chính xác. Đây là một tiêu chí bắt buộc (`required`).
- **Cách Hoạt Động:**
    1.  Đầu tiên, hệ thống cố gắng đọc thông tin DPI từ siêu dữ liệu (metadata) của hình ảnh.
    2.  Nếu không có thông tin DPI (phổ biến với các tệp PDF được tạo từ nhiều nguồn), hệ thống sẽ sử dụng một phương pháp ước tính: nó phân tích hình ảnh, tìm các đường viền (contour) trông giống như ký tự và tính toán chiều cao trung vị của chúng. Dựa trên chiều cao ký tự trung bình mong đợi (ví dụ: 2.5mm), nó ước tính DPI của hình ảnh.
    3.  DPI cuối cùng (từ siêu dữ liệu hoặc ước tính) được so sánh với ngưỡng `min_dpi` trong tệp cấu hình.
- **Hàm/Logic Chính:**
    - `check_criteria` (nhánh `resolution`) trong `src/criteria.py`.
    - `estimate_dpi_from_image` trong `src/criteria.py` để ước tính DPI.

---

### 3. Brightness (Độ sáng)

- **Mô tả:** Kiểm tra xem hình ảnh có quá tối hoặc quá sáng không, điều này có thể ảnh hưởng đến khả năng đọc. Đây là một tiêu chí bắt buộc (`required`).
- **Cách Hoạt Động:** Hệ thống tính toán giá trị độ sáng trung bình của tất cả các pixel trong mỗi hình ảnh trang. Giá trị trung bình này sau đó được so sánh với một phạm vi cho phép (`min` và `max`) được định cấu hình.
- **Hàm/Logic Chính:** `ImageStat.Stat(img).mean[0]` trong `src/criteria.py` (nhánh `brightness`).

---

### 4. Blur (Độ mờ)

- **Mô tả:** Phát hiện các hình ảnh bị mờ, không rõ nét, gây khó khăn cho việc nhận dạng ký tự. Đây là một tiêu chí bắt buộc (`required`).
- **Cách Hoạt Động:** Hệ thống áp dụng bộ lọc Laplacian cho hình ảnh. Phương sai (variance) của kết quả từ bộ lọc Laplacian là một chỉ số tốt về độ sắc nét; giá trị phương sai thấp cho thấy hình ảnh bị mờ. Giá trị này được so sánh với ngưỡng `min_variance`.
- **Hàm/Logic Chính:** `cv2.Laplacian(cv_img, cv2.CV_64F).var()` trong `src/criteria.py` (nhánh `blur`).

---

### 5. Skew (Độ nghiêng)

- **Mô tả:** Kiểm tra xem tài liệu có bị xoay nghiêng hay không. Đây là một tiêu chí đề xuất (`recommended`).
- **Cách Hoạt Động:** Hệ thống thử xoay hình ảnh theo các góc nhỏ (ví dụ: từ -5 đến +5 độ). Ở mỗi góc, nó tính toán phương sai của tổng các pixel theo hàng ngang. Góc xoay nào cho ra phương sai lớn nhất thường là góc nghiêng của tài liệu. Góc nghiêng được phát hiện sẽ được so sánh với `max_deg`.
- **Hàm/Logic Chính:** `calculate_skew` trong `src/criteria.py`.

---

### 6. Watermark (Hình mờ)

- **Mô tả:** Phát hiện sự hiện diện của các hình mờ hoặc các mẫu lặp lại có thể cản trở việc đọc nội dung. Đây là một tiêu chí cảnh báo (`warning`).
- **Cách Hoạt Động:** Sử dụng một phương pháp tự tương quan (autocorrelation) cơ bản trên dữ liệu pixel của hình ảnh. Một đỉnh tự tương quan cao có thể chỉ ra một mẫu lặp lại, chẳng hạn như hình mờ. Kết quả được so sánh với `max_overlap`.
- **Hàm/Logic Chính:** `detect_overlap` trong `src/criteria.py`.

---

### 7. Missing Pages / Text Density (Thiếu trang / Mật độ văn bản)

- **Mô tả:** Các tiêu chí `missing_pages` và `text_density` cùng nhằm mục đích phát hiện các trang trống hoặc có quá ít nội dung.
- **Cách Hoạt Động:**
    - Hệ thống có một hàm để tính toán "tỷ lệ nội dung" bằng cách chuyển đổi hình ảnh sang dạng đen trắng và tính phần trăm pixel đen (được coi là nội dung) so với tổng số pixel.
    - Tỷ lệ này có thể được sử dụng để xác định xem một trang có gần như trống không (cho `missing_pages`) hoặc có nằm trong phạm vi mật độ văn bản bình thường không (cho `text_density`).
- **Hàm/Logic Chính:** `calculate_content_ratio` trong `src/criteria.py`.
- **Lưu ý:** Tại thời điểm phân tích, logic cho các tiêu chí `missing_pages`, `text_density`, `noise`, và `compression` **chưa được triển khai** trong hàm `check_criteria` chính, mặc dù các hàm hỗ trợ và cấu hình đã tồn tại.

---

### 8. Noise (Nhiễu) & Compression (Nén)

- **Mô tả:** Các tiêu chí này được định nghĩa trong cấu hình nhưng logic kiểm tra của chúng chưa được triển khai trong mã nguồn.
    - `noise`: Có thể được thiết kế để phát hiện các chấm hoặc đốm ngẫu nhiên trên nền.
    - `compression`: Có thể được thiết kế để phát hiện các tạo tác (artifacts) do nén ảnh chất lượng thấp (ví dụ: JPEG).
- **Cách Hoạt Động:** (Chưa triển khai).
- **Hàm/Logic Chính:** (Chưa triển khai).
