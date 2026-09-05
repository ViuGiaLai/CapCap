# Yêu cầu Hệ thống & Quản lý Tài nguyên (Requirements)

VIUStudio được thiết kế linh hoạt để có thể vận hành ổn định trên cả máy tính văn phòng phổ thông (chỉ có CPU) lẫn máy trạm biên tập đồ họa chuyên nghiệp trang bị GPU NVIDIA cao cấp.

---

## 1. Yêu cầu Cấu hình Phần cứng

| Thành phần | Cấu hình Tối thiểu (CPU Mode) | Cấu hình Khuyến nghị (GPU Mode) |
| :--- | :--- | :--- |
| **Hệ điều hành** | Windows 10 / 11 (64-bit) | Windows 10 / 11 (64-bit) |
| **Bộ vi xử lý (CPU)** | Intel Core i3 / AMD Ryzen 3 (4 nhân) | Intel Core i7 / AMD Ryzen 7 (8 nhân trở lên) |
| **Bộ nhớ RAM** | 8 GB RAM | 16 GB - 32 GB RAM |
| **Card đồ họa (GPU)** | Đồ họa tích hợp (Intel UHD / AMD Radeon) | NVIDIA RTX 2060 / 3060 / 4060 trở lên (VRAM >= 6GB) |
| **Ổ cứng lưu trữ** | 10 GB dung lượng trống (ưu tiên SSD) | 50 GB SSD NVMe tốc độ cao |
| **Màn hình** | Độ phân giải 1280×720 (Scale 100%) | 1920×1080 (Full HD) hoặc 2K/4K |

---

## 2. Danh mục Tài nguyên Mô hình AI

Toàn bộ các mô hình AI có thể được tải tự động thông qua hộp thoại **Manage Resources** trong ứng dụng:

![Manage Resources](assets/screenshots/resource_manager.png)

| Tên mô hình | Mục đích sử dụng | Dung lượng | Vị trí lưu trữ |
| :--- | :--- | :--- | :--- |
| **SenseVoice Small** | Nhận diện giọng nói siêu nhanh trên CPU (Trung, Anh, Nhật, Hàn) | ~237 MB | `models/sensevoice/` |
| **Silero VAD** | Phân tách khoảng lặng giọng nói | ~2 MB | `bin/` |
| **Faster-Whisper Base** | Nhận diện giọng nói phổ thông trên CPU | ~145 MB | `models/faster_whisper/` |
| **Faster-Whisper Small/Medium** | Nhận diện giọng nói độ chính xác cao trên GPU | ~480 MB - 1.5 GB | `models/faster_whisper/` |
| **CUDA 12 Runtime Pack** | Thư viện tăng tốc GPU cho Whisper & OCR | ~450 MB | `bin/cuda12_fw/` |
| **Piper Voice (Tiếng Việt)** | Giọng đọc thuyết minh tự nhiên (Ngọc Huyền, Tuấn Khang) | ~60 MB / giọng | `models/piper/` |
| **Sherpa-ONNX Diarization** | Nhận diện phân tách người nói | ~40 MB | `models/pyannote/` |
| **PP-OCRv4 (ONNX)** | Nhận diện chữ phụ đề trên khung hình video | ~30 MB | `models/ocr/` |

---

## 3. Hướng dẫn Cài đặt Môi trường chạy từ Mã nguồn

### Bước 1: Clone kho mã nguồn
```bash
git clone https://github.com/ViuGiaLai/VIUStudio.git
cd VIUStudio
```

### Bước 2: Tạo môi trường ảo Python 3.11
```bash
python -m venv venv
venv\Scripts\activate
```

### Bước 3: Cài đặt thư viện phụ thuộc
```bash
pip install -r requirements-local.txt
```

### Bước 4: Khởi chạy ứng dụng
```bash
python ui/gui.py
```
