# TODO: Nâng cấp dự án để sẵn sàng cho Production

Dự án này là một PoC (Proof of Concept) tốt. Tuy nhiên, để có thể hoạt động ổn định, hiệu quả và an toàn trên môi trường production với lượng dữ liệu lớn, chúng ta cần thực hiện các cải tiến dưới đây.

## 1. Hiệu suất và Khả năng mở rộng (Scalability & Performance)

- **Tận dụng GPU:**

  - Các tác vụ xử lý ảnh (như kiểm tra độ mờ, độ nhiễu, góc nghiêng) sẽ nhanh hơn rất nhiều nếu chạy trên GPU.
  - **Việc cần làm:**
    - Cài đặt phiên bản OpenCV hỗ trợ CUDA (GPU của NVIDIA).
    - Cập nhật lại code ở `src/document_assessor/criteria.py` để sử dụng các hàm tính toán trên GPU.

- **Hệ thống xử lý phân tán (Distributed Processing):**
  - Hiện tại, dự án chỉ chạy song song trên các core CPU của một máy duy nhất. Khi dữ liệu quá lớn, một máy sẽ không đủ sức.
  - **Việc cần làm:**
    - Chuyển đổi kiến trúc sang hệ thống phân tán sử dụng message queue (như RabbitMQ, Kafka) và các worker (sử dụng Celery).
    - Hoặc sử dụng các dịch vụ serverless trên cloud (AWS Lambda, Google Cloud Functions) để mỗi file được xử lý bởi một function riêng biệt, giúp hệ thống tự động co giãn gần như vô hạn.

## 2. Kiến trúc và Luồng dữ liệu (Architecture & Data Flow)

- **Nguồn dữ liệu đầu vào:**

  - Hiện tại, hệ thống đang đọc danh sách file từ một file `input.json`. Điều này không phù hợp với môi trường production.
  - **Việc cần làm:**
    - Xây dựng một API endpoint (sử dụng FastAPI hoặc Flask) để tiếp nhận yêu cầu xử lý tài liệu theo thời gian thực.
    - Hoặc thiết lập cơ chế tự động quét các file mới được tải lên một storage service (như AWS S3, Google Cloud Storage).

- **Lưu trữ kết quả:**
  - Kết quả đang được ghi ra file `output.json`. Việc này gây khó khăn cho việc truy vấn và phân tích.
  - **Việc cần làm:**
    - Lưu kết quả đánh giá vào một cơ sở dữ liệu (ví dụ: PostgreSQL, MongoDB, hoặc Elasticsearch).
    - Elasticsearch sẽ là một lựa chọn mạnh mẽ nếu có nhu cầu tìm kiếm và tổng hợp thông tin từ kết quả.

## 3. Độ tin cậy và Xử lý lỗi (Robustness & Error Handling)

- **Cơ chế Retry:**

  - Cần có cơ chế tự động thử lại (retry) đối với các lỗi tạm thời (ví dụ: lỗi mạng, không thể truy cập file tạm thời).
  - **Việc cần làm:**
    - Tích hợp logic retry với thuật toán exponential backoff vào các worker xử lý.

- **Dead-Letter Queue (DLQ):**
  - Đối với những tài liệu liên tục xử lý thất bại, cần chuyển chúng vào một hàng đợi riêng (DLQ) để phân tích thủ công, tránh làm tắc nghẽn hệ thống.
  - **Việc cần làm:**
    - Cấu hình DLQ trong hệ thống message queue.

## 4. Giám sát và Ghi log (Monitoring & Logging)

- **Structured Logging:**

  - Chuyển đổi log từ dạng text thuần sang dạng structured (JSON). Điều này giúp việc truy vấn và phân tích log trên các hệ thống như ELK Stack (Elasticsearch, Logstash, Kibana) hoặc Datadog trở nên dễ dàng hơn.
  - **Việc cần làm:**
    - Cấu hình lại logger để output ra định dạng JSON.

- **Monitoring và Alerting:**
  - Cần theo dõi các chỉ số quan trọng của hệ thống theo thời gian thực.
  - **Việc cần làm:**
    - Tích hợp Prometheus để thu thập các metrics (ví dụ: số lượng tài liệu đang xử lý, thời gian xử lý trung bình, tỷ lệ lỗi).
    - Sử dụng Grafana để visualize các metrics và thiết lập cảnh báo (alerting) khi có sự cố (ví dụ: hệ thống xử lý chậm, tỷ lệ lỗi tăng cao).

## 5. Triển khai và Vận hành (Deployment & CI/CD)

- **Containerization:**

  - Dự án đã có `Dockerfile`, đây là một khởi đầu tốt.
  - **Việc cần làm:**
    - Tối ưu hóa Dockerfile cho production (multi-stage builds) để giảm kích thước image.
    - Sử dụng Docker Compose cho môi trường phát triển để giả lập các service liên quan (như database, message queue).

- **Orchestration:**

  - Để quản lý, scale và tự động hóa việc triển khai các container, cần một hệ thống điều phối.
  - **Việc cần làm:**
    - Viết file triển khai cho Kubernetes (Deployment, Service, ConfigMap).
    - Hoặc sử dụng các dịch vụ managed container như Amazon ECS, Google Kubernetes Engine (GKE).

- **CI/CD:**
  - Xây dựng một quy trình tích hợp và triển khai liên tục.
  - **Việc cần làm:**
    - Thiết lập pipeline sử dụng GitHub Actions, Jenkins, hoặc GitLab CI để tự động chạy test, build Docker image và triển khai lên các môi trường (staging, production) mỗi khi có thay đổi ở source code.
