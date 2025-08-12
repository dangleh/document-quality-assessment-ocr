# Document Quality Assessment for OCR

## Mô tả

Hệ thống kiểm tra chất lượng tài liệu PDF và TIFF trước khi thực hiện OCR. Project này giúp đảm bảo tài liệu đáp ứng các tiêu chuẩn chất lượng cần thiết để OCR có thể hoạt động hiệu quả.

## Tính năng chính

- **Kiểm tra độ phân giải**: Đảm bảo DPI và kích thước tối thiểu
- **Đánh giá chất lượng ảnh**: Độ sáng, độ tương phản, độ mờ
- **Phát hiện vấn đề**: Góc lệch, nhiễu, watermark, artifact nén
- **Hỗ trợ đa định dạng**: PDF, TIFF, và các định dạng ảnh khác
- **Batch processing**: Xử lý nhiều tài liệu cùng lúc
- **Cấu hình linh hoạt**: Tùy chỉnh tiêu chí đánh giá qua JSON config

## Cài đặt

### Yêu cầu hệ thống

- Python 3.8+
- pip

### Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### Dependencies chính

- `pillow`: Xử lý ảnh
- `numpy`: Tính toán số học
- `opencv-python`: Xử lý ảnh nâng cao
- `pymupdf`: Xử lý PDF
- `pydantic`: Validation dữ liệu
- `pytest`: Testing

## Cách sử dụng

### 1. Chuẩn bị dữ liệu đầu vào

Tạo file JSON với cấu trúc:

```json
[
  {
    "customerID": "123456789",
    "transactionID": "TXN001",
    "documents": [
      {
        "documentID": "doc1",
        "documentType": "công văn",
        "documentFormat": "pdf",
        "documentPath": "path/to/document.pdf",
        "requiresOCR": true
      }
    ]
  }
]
```

### 2. Chạy chương trình

```bash
# Sử dụng script
./run.sh

# Hoặc chạy trực tiếp
python src/main.py --input input.json --output output.json
```

### 3. Kết quả

- File output.json chứa kết quả đánh giá
- Logs được lưu trong thư mục `logs/`
- Mỗi document sẽ có trường `isAccepted` cho biết có đạt tiêu chuẩn không

## Cấu hình

### Tiêu chí đánh giá (criteria_config.json)

- **required**: Tiêu chí bắt buộc, fail sẽ từ chối tài liệu
- **recommended**: Tiêu chí khuyến nghị, fail sẽ cảnh báo
- **warning**: Tiêu chí cảnh báo, không ảnh hưởng đến kết quả cuối

### Các tiêu chí chính

1. **file_integrity**: Kiểm tra file có mở được không
2. **resolution**: Độ phân giải tối thiểu (DPI, width)
3. **brightness**: Độ sáng và tương phản
4. **blur**: Độ mờ/nhòe
5. **skew**: Góc lệch
6. **text_density**: Mật độ văn bản
7. **noise**: Nhiễu nền
8. **watermark**: Watermark che lấp
9. **compression**: Artifact nén
10. **missing_pages**: Thiếu trang/mất góc

## Cấu trúc project

```
document-quality-assessment-ocr/
├── config/                 # Cấu hình
│   ├── app_config.json    # Cấu hình ứng dụng
│   └── criteria_config.json # Tiêu chí đánh giá
├── data/                  # Dữ liệu mẫu
├── logs/                  # Log files
├── src/                   # Source code
│   ├── handlers/          # Xử lý file PDF/TIFF
│   ├── criteria.py        # Logic đánh giá
│   ├── evaluator.py       # Pipeline chính
│   ├── main.py           # Entry point
│   └── utils.py          # Utilities
├── tests/                 # Test cases
├── requirements.txt       # Dependencies
└── run.sh                # Script chạy
```

## Testing

```bash
# Chạy tất cả tests
pytest

# Chạy test cụ thể
pytest tests/test_evaluation.py
```

## Troubleshooting

### Lỗi thường gặp

1. **File không mở được**: Kiểm tra đường dẫn và quyền truy cập
2. **Memory error**: Giảm max_pages trong config
3. **DPI detection fail**: Kiểm tra metadata của file

### Logs

- Logs được lưu trong `logs/` với format `run_YYYYMMDD_HHMMSS.json`
- Sử dụng `logging` để debug

## Đóng góp

1. Fork project
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

## License

MIT License

## Liên hệ

Nếu có vấn đề hoặc góp ý, vui lòng tạo issue trên GitHub.
