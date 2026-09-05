# Hướng dẫn Xử lý Sự cố (Troubleshooting)

Tổng hợp các vấn đề thường gặp và cách khắc phục nhanh chóng khi sử dụng VIUStudio.

---

## 1. Lỗi không nhận diện được GPU NVIDIA (CUDA)
- **Hiện tượng**: Launcher chỉ hiển thị chế độ `CPU` hoặc báo lỗi `CUDA not found`.
- **Nguyên nhân**: Máy tính chưa cài driver NVIDIA mới nhất hoặc chưa tải gói runtime CUDA.
- **Cách khắc phục**:
  1. Cập nhật NVIDIA Graphics Driver lên phiên bản mới nhất từ trang chủ NVIDIA.
  2. Mở VIUStudio ➔ vào **Manage Resources**.
  3. Tìm mục **CUDA 12 Runtime Pack** và bấm **Download**. Sau khi tải xong, khởi động lại ứng dụng.

---

## 2. Tiếng thuyết minh bị lệch so với phụ đề
- **Hiện tượng**: Giọng đọc phát trước hoặc sau khi phụ đề xuất hiện trên màn hình.
- **Nguyên nhân**: Tốc độ đọc của giọng TTS không khớp với độ dài thời gian hiển thị câu thoại gốc.
- **Cách khắc phục**:
  1. Trong tab `04 Voice`, chọn chế độ **Voice Timing Sync Mode** thành `Smart` hoặc `Fit to segment`.
  2. Tinh chỉnh lại thanh trượt **Voice Speed** (tăng lên `1.1x` hoặc `1.2x` nếu câu thoại dài).

---

## 3. Phụ đề tiếng Việt bị lỗi font (hiển thị ô vuông hoặc dấu hỏi)
- **Hiện tượng**: Các ký tự có dấu như `ơ, ư, đ, ẽ` bị vỡ nét hoặc thành ký tự lạ.
- **Cách khắc phục**:
  1. Vào tab `05 Style`.
  2. Chọn các font chữ Unicode chuẩn được hỗ trợ sẵn: `Segoe UI`, `Inter`, `Arial`, `Roboto`, `Montserrat`.
  3. Không sử dụng các font VNI cũ hoặc font viết hoa không hỗ trợ tiếng Việt đầy đủ.

---

## 4. Lỗi hết bộ nhớ RAM khi xử lý video 4K dài
- **Hiện tượng**: Ứng dụng bị chậm hoặc thoát đột ngột khi trích xuất âm thanh hoặc render video.
- **Cách khắc phục**:
  1. Sử dụng công cụ **Split Video** tại Launcher để chia video thành các phần 20-30 phút trước khi làm.
  2. Đóng bớt các ứng dụng nặng khác trên Windows để giải phóng RAM.
