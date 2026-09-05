# Cẩm nang Quy trình Sản xuất Video Recap (Workflow Guide)

Quy trình chuẩn hóa 5 bước của VIUStudio giúp nhà sáng tạo nội dung sản xuất video recap/review phim nhanh gấp 5 lần so với phương pháp thủ công, đảm bảo chuẩn âm thanh, phụ đề và tránh vi phạm bản quyền.

---

## Sơ đồ Tổng quan Quy trình

```text
[BƯỚC 1: NHẬP & CHUẨN BỊ]
   │  • Nạp video nguồn
   │  • Cấu hình tỷ lệ 16:9 hoặc 9:16
   ▼
[BƯỚC 2: TRÍCH XUẤT LỜI THOẠI (ASR / OCR)]
   │  • Nhận diện giọng nói với Whisper / SenseVoice
   │  • Hoặc quét phụ đề cứng với RapidOCR
   ▼
[BƯỚC 3: DỊCH THUẬT & BIÊN TẬP VĂN PHONG]
   │  • Dịch tiếng Việt qua LLaMA GGUF local hoặc Google Gemini API
   │  • Sử dụng AI Rewrite tinh chỉnh câu văn kịch tính
   ▼
[BƯỚC 4: THUYẾT MINH & XỬ LÝ HÌNH ẢNH]
   │  • Lồng tiếng AI (Piper / Edge TTS)
   │  • Vẽ vùng che mờ (Blur) logo, đài truyền hình
   ▼
[BƯỚC 5: TỰ ĐỘNG DỰNG & XUẤT BẢN]
   │  • Áp dụng Auto Edit Recap (Smart Zoom, Motion Reframe, Ducking)
   │  • Xuất video chất lượng cao với phụ đề nhúng cứng
```

---

## Bí quyết Tối ưu cho Video Recap Triệu View

1. **Chọn giọng đọc phù hợp**:
   - Dùng giọng nữ truyền cảm (Ngọc Huyền / Hoài My) cho phim tình cảm, tâm lý.
   - Dùng giọng nam trầm ấm, dứt khoát (Tuấn Khang / Nam Minh) cho phim hành động, kinh dị, trinh thám.
2. **Xử lý nhạc nền (Audio Ducking)**:
   - Luôn bật chế độ Voiceover Ducking ở mức `-12 dB` để khi giọng thuyết minh cất lên, nhạc phim tự động nhỏ xuống giúp khán giả nghe rõ từng từ.
3. **Chống bản quyền hình ảnh**:
   - Sử dụng công cụ **Blur** trên thanh Preview để che logo đài truyền hình ở góc trên bên phải.
   - Bật tính năng **Horizontal Flip** trong Auto Edit Recap để lật gương các phân cảnh lặp lại.
