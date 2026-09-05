# Kiến trúc Kỹ thuật & Công nghệ (Technical Stack)

VIUStudio được xây dựng trên nền tảng kiến trúc hiện đại, kết hợp sức mạnh giao diện của **PySide6 (Qt 6)**, engine giải mã đa phương tiện **libmpv / FFmpeg**, cùng các mô hình trí tuệ nhân tạo (AI) chạy suy luận cực nhanh trên cả CPU và GPU NVIDIA.

---

## 1. Bảng tổng hợp công nghệ

| Phân hệ (Subsystem) | Công nghệ / Thư viện | Vai trò & Mục đích |
| :--- | :--- | :--- |
| **Giao diện Desktop** | PySide6 (Qt for Python 6.11+) | Cung cấp UI phản hồi nhanh, dark theme hiện đại, hệ thống tín hiệu/slot mạnh mẽ. |
| **Trình phát Video** | libmpv (C-API bindings) / Qt Multimedia | Phát video thời gian thực siêu mượt, hỗ trợ OSD overlay, phụ đề ASS/SRT và canvas tương tác. |
| **Nhận diện giọng nói (ASR)** | Faster-Whisper (CTranslate2), SenseVoice (Sherpa-ONNX) | Chuyển giọng nói từ video/audio thành văn bản với độ chính xác cao và mốc thời gian chi tiết. |
| **Trích xuất chữ (OCR)** | RapidOCR PP-OCRv4 (ONNX Runtime) | Quét và nhận diện phụ đề cứng bị nhúng vào khung hình video với tốc độ cao. |
| **Phân đoạn giọng nói (VAD)** | Silero VAD (ONNX) | Phát hiện chính xác các khoảng lặng để phân tách câu tự nhiên và lọc nhiễu nền. |
| **Phân tách người nói (Diarization)** | Sherpa-ONNX Diarization | Nhận diện và gán nhãn từng người nói (`Speaker 1`, `Speaker 2`, ...) trong hội thoại. |
| **Dịch thuật AI (Translation)** | Llama.cpp (Local GGUF), Google AI Studio (Gemini), OpenAI | Chuyển ngữ phụ đề với văn phong tự nhiên, hỗ trợ cả offline hoàn toàn và Cloud API. |
| **Lồng tiếng tự động (TTS)** | Piper TTS (Offline Neural), Edge TTS (Cloud) | Tạo giọng đọc thuyết minh tiếng Việt tự nhiên, đa cảm xúc, đồng bộ thời gian với câu thoại. |
| **Xử lý Đa phương tiện** | FFmpeg 6+, pydub, NumPy, SciPy, soundfile | Cắt ghép video, trích xuất âm thanh, tạo waveform, chuẩn hóa âm lượng (LUFS), ducking. |
| **Đóng gói ứng dụng** | PyInstaller, Inno Setup | Đóng gói thành bản cài đặt EXE độc lập trên Windows mà không cần cài Python thủ công. |

---

## 2. Kiến trúc Module Hệ thống

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        VIUStudio User Interface                         │
│   ┌─────────────────────┐  ┌────────────────────┐  ┌────────────────┐   │
│   │   Launcher Window   │  │  Editor Workbench  │  │ Dialogs & Modals│   │
│   └─────────────────────┘  └────────────────────┘  └────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Qt Signals / Slots
┌────────────────────────────────────▼────────────────────────────────────┐
│                       UI Controllers & Feature Mixins                   │
│   ├── PipelineController       ├── SubtitleController                   │
│   ├── VideoFilterController    ├── TimelineEditingMixin                 │
│   ├── SpeakerVoiceMixin        ├── VisualLayerEditorMixin               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Domain Bridge / State
┌────────────────────────────────────▼────────────────────────────────────┐
│                        Application Core & Workflows                     │
│   ├── ProjectService           ├── AutoRecapEngine                      │
│   ├── PrepareWorkflow          ├── VoiceWorkflow                        │
│   ├── ExportWorkflow           ├── Timeline & Layer Models (Blur/Text)  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Async Workers / Subprocesses
┌────────────────────────────────────▼────────────────────────────────────┐
│                        AI Engines & Media Drivers                       │
│   ├── Faster-Whisper (CUDA/CPU)├── Piper & Edge TTS                     │
│   ├── SenseVoice & Silero VAD  ├── Llama.cpp & Cloud Translation        │
│   ├── RapidOCR (ONNX)          ├── libmpv & FFmpeg Pipeline             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Đặc điểm Kỹ thuật Nổi bật

### 3.1 Ảo hóa Timeline cho Video dài (Virtualized Timeline Rendering)
- Khi làm video recap phim dài từ 30 phút đến vài tiếng với hàng ngàn câu phụ đề, việc render toàn bộ QWidget sẽ gây giật lag.
- Timeline của VIUStudio sử dụng cơ chế **Viewport Virtualization & Custom QPainter**:
  - Chỉ tính toán bố cục và vẽ các clip nằm trong khung nhìn hiển thị cộng thêm một vùng đệm nhỏ hai bên.
  - Sử dụng cấu trúc chỉ mục khoảng thời gian (Interval Index) để truy vấn nhanh clip trong phạm vi `[view_start, view_end]`.
  - Cache text elision và dạng sóng âm thanh (waveform) theo hash dữ liệu để tránh vẽ lại không cần thiết.

### 3.2 Bộ nhớ đệm Waveform & Thumbnails thông minh
- Dạng sóng âm thanh (Audio Waveform) được trích xuất bằng FFmpeg thành định dạng PCM 16-bit và nén mẫu (downsampling) thành file cache dạng mảng nhị phân.
- Khi người dùng cuộn hoặc phóng to timeline, waveform được vẽ bằng đồ họa vector tức thì mà không cần đọc lại file âm thanh gốc.

### 3.3 Cách ly tiến trình (Worker Isolation)
- Toàn bộ tác vụ nặng (nhận diện Whisper, trích xuất OCR, gọi API dịch, sinh giọng Piper) đều được đưa vào các luồng `QThread` riêng biệt.
- Giao diện người dùng (UI thread) luôn phản hồi mượt mà ở 60 FPS, không bao giờ bị hiện tượng `Not Responding`.
