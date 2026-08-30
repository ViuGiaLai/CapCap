from __future__ import annotations

APP_VERSION = "1.2.0"
APP_NAME = "VIUStudio Video & Auto Edit Recap"
AUTO_RECAP_VERSION = "1.0.0"

RELEASE_NOTES = """✨ VIUStudio v1.2.0 - Auto Edit Recap Release

Hạng mục tính năng mới:
• ✨ Auto Edit Recap Engine (12 Core Rules V1): Chia ranh giới hiệu ứng không bỏ nội dung, Zoom/Pan/Crop, Speed Accent, Freeze Frame & Audio Ducking.
• 🎛️ Consumer UI Tier 1 & Tier 2: Checkbox khởi động nhanh & Modal tùy chỉnh phong cách dựng video (Subtle, Balanced, Dynamic).
• 🎯 Generate Dropdown Top Bar: Nút bấm thiết kế nổi bật góc trên bên phải với menu tùy chọn linh hoạt.
• 📊 Bảng Tiến Trình 5 Bước Chuyên Biệt: Hiển thị minh bạch Analyzing Video, Building Recap, Applying Smart Edits, Processing Audio, Rendering Recap.
• 🛡️ Graceful Audio Fallback: Tự động chuyển hướng an toàn khi mô hình tách giọng thiếu hoặc gặp sự cố.
• 📂 Export Direct Output: Tự động kích hoạt nút Export & mở thư mục kết quả video ngay khi hoàn tất.
"""


def get_app_version_string() -> str:
    return f"{APP_NAME} v{APP_VERSION} (Recap Engine v{AUTO_RECAP_VERSION})"
