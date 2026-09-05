# Cấu trúc Dự án (Project Structure)

Mã nguồn VIUStudio được tổ chức theo kiến trúc phân tầng rõ ràng (Clean Layered Architecture), tách biệt giữa giao diện (UI), tầng điều khiển (Controllers/Features), dịch vụ nghiệp vụ (Services/Workflows) và các bộ máy xử lý (Engines).

---

## 1. Cây thư mục tổng thể

```text
VIUStudio/
├── app/                           # Tầng nghiệp vụ, mô hình dữ liệu và các engine AI
│   ├── core/                      # Trạng thái dự án và cấu hình cốt lõi (state.py, config.py)
│   ├── engines/                   # Adapter cho các engine bên ngoài (Whisper, OCR, TTS)
│   ├── layers/                    # Mô hình miền dữ liệu Timeline (Timeline, Track, Blur, Text)
│   ├── services/                  # Các dịch vụ độc lập (Project, Resource, Diarization, AutoRecap)
│   ├── translation/               # Bộ điều phối dịch thuật và các provider (Google, OpenAI, LLaMA)
│   ├── workflows/                 # Kịch bản thực thi theo luồng (Prepare, Voice, Export)
│   ├── ocr_processor.py           # Engine xử lý OCR nhận diện phụ đề cứng
│   ├── sensevoice_processor.py    # Engine nhận diện giọng nói SenseVoice
│   └── whisper_processor.py       # Engine nhận diện giọng nói Faster-Whisper
├── ui/                            # Tầng giao diện người dùng (PySide6)
│   ├── controllers/               # Điều phối viên giao diện và kết nối nghiệp vụ
│   ├── dialogs/                   # Các hộp thoại phụ (AutoRecap, Update, Settings)
│   ├── features/                  # Các Mixin bổ sung chức năng cho cửa sổ chính
│   ├── inspectors/                # Bảng thuộc tính đối tượng (Subtitle, Blur, Visual)
│   ├── panels/                    # Các panel công cụ
│   ├── views/                     # Các khung nhìn chính (Launcher, MainWindow, Timeline, Preview)
│   │   ├── editor/                # Timeline view và track labels view
│   │   ├── launcher.py            # Màn hình khởi động và chọn dự án
│   │   ├── main_window.py         # Cửa sổ làm việc chính (Workbench)
│   │   ├── preview_panel.py       # Panel phát video và thanh điều khiển
│   │   └── resource_manager.py    # Hộp thoại quản lý tải mô hình AI
│   ├── widgets/                   # Các thành phần giao diện tùy biến (MPV view, Table dialog)
│   ├── worker_adapters/           # Adapter chuyển đổi giữa Worker nghiệp vụ và Qt Signal
│   ├── gui.py                     # Điểm khởi chạy ứng dụng (Entrypoint)
│   └── main_window.py             # Lớp VideoTranslatorGUI chính
├── bin/                           # Chứa các file thực thi nhị phân đi kèm (FFmpeg, MPV, CUDA pack)
├── models/                        # Thư mục lưu trữ các mô hình AI đã tải về
├── assets/                        # Biểu tượng, logo, font chữ và hình ảnh giao diện
├── docs/                          # Toàn bộ tài liệu hướng dẫn và cổng thông tin web
│   ├── assets/screenshots/        # Bộ ảnh chụp màn hình thực tế của hệ thống
│   ├── index.html                 # Cổng tài liệu và giới thiệu tương tác hiện đại
│   ├── how-to-use.md              # Hướng dẫn sử dụng chi tiết
│   ├── technical-stack.md         # Tài liệu kiến trúc kỹ thuật
│   ├── project-structure.md       # Cấu trúc mã nguồn
│   ├── requirements.md            # Yêu cầu hệ thống và tài nguyên
│   ├── workflow-guide.md          # Cẩm nang quy trình sản xuất video recap
│   ├── keyboard-shortcuts.md      # Bảng tra cứu phím tắt
│   └── troubleshooting.md         # Hướng dẫn xử lý sự cố
├── projects/                      # Thư mục lưu trữ dữ liệu các dự án của người dùng
├── temp/                          # Thư mục tạm lưu cache waveform, thumbnails, preview
├── requirements-base.txt          # Gói phụ thuộc cơ bản
├── requirements-local.txt         # Gói phụ thuộc đầy đủ cho chạy máy nội bộ
└── requirements.txt               # Gói phụ thuộc chính
```

---

## 2. Chi tiết các thành phần trọng yếu

### 2.1 Tầng Giao diện (`ui/`)
- `ui/gui.py`: Kiểm tra đơn phiên (Single-Instance Mutex), nạp biến môi trường `.env`, khởi tạo `QApplication`, mở màn hình Launcher và chuyển tiếp vào cửa sổ Editor.
- `ui/main_window.py`: Lớp `VideoTranslatorGUI` tích hợp toàn bộ các Mixin tính năng từ `ui/features/` và định nghĩa giao diện tối ưu (Design System Theme).
- `ui/views/editor/timeline.py`: Thành phần Timeline đồ họa tùy biến xử lý đa track, thước thời gian, con trỏ playhead, zoom tỷ lệ và các clip phụ đề/hiệu ứng.
- `ui/views/preview_panel.py`: Màn hình phát video tích hợp libmpv với các công cụ vẽ vùng che mờ (Blur), chèn logo và quét OCR trực tiếp.

### 2.2 Tầng Nghiệp vụ & Dịch vụ (`app/`)
- `app/services/project_service.py`: Quản lý cấu trúc thư mục dự án (`project.json`, `subtitle/`, `timeline/`, `audio/`, `export/`), sao lưu tự động và khôi phục khi gặp sự cố.
- `app/services/auto_recap_engine.py`: Thuật toán phân tích nhịp điệu phim, tạo chuyển động camera tự động (Smart Zoom, Pan, Reframe), lật hình chống bản quyền và giảm âm thanh nền (Ducking).
- `app/translation/translator.py`: Bộ điều phối dịch thuật hỗ trợ cơ chế retry, chia chunk văn bản dài, và fallback tự động sang Google Translate khi mất kết nối mạng.
