# Đặc tả nâng cấp toàn bộ UI/UX CapCap

> Trạng thái: **Bản đề xuất để duyệt trước khi triển khai**  
> Phiên bản tài liệu: 1.1 — cập nhật sau vòng phản biện định hướng recap  
> Ngày lập: 28/08/2026  
> Phạm vi: Launcher, Editor, Timeline, Inspector, Settings, Resource Manager và các hộp thoại liên quan  
> Ràng buộc: **Chưa thay đổi mã nguồn UI hoặc hành vi nghiệp vụ trong giai đoạn tài liệu**

---

## 1. Mục tiêu của lần nâng cấp

CapCap cần chuyển từ giao diện “nhiều bảng điều khiển kỹ thuật” sang một sản phẩm biên tập video chuyên nghiệp, dễ học và dễ thao tác lâu dài. Giao diện mới phải tạo cảm giác thống nhất như một editor hoàn chỉnh, không phải tập hợp nhiều form và nút chức năng.

Các mục tiêu chính:

1. Thay đổi toàn bộ ngôn ngữ hình ảnh: bố cục, màu sắc, typography, icon, khoảng cách, trạng thái và chuyển động.
2. Giảm tải nhận thức: tại mỗi thời điểm chỉ hiển thị công cụ liên quan đến tác vụ hoặc đối tượng đang chọn.
3. Đưa video và timeline thành trung tâm của trải nghiệm biên tập.
4. Làm rõ quy trình **Prepare → Transcript → Translate → Voice → Export** mà không chiếm một cột lớn cố định.
5. Chuẩn hóa UI thành một design system có token và component dùng lại được, không tiếp tục đặt stylesheet rải rác.
6. Hoạt động tốt từ màn hình laptop 1280×720 đến màn hình desktop lớn và khi thay đổi DPI.
7. Giữ nguyên logic xử lý, dữ liệu dự án, pipeline, controller và định dạng file trong giai đoạn thay UI.
8. Tạo nền tảng để bổ sung theme sáng, đa ngôn ngữ và tính năng editor mới trong tương lai.

### 1.1 Quyết định sản phẩm đã chốt ở phiên bản 1.1

Phiên bản này điều chỉnh đặc tả theo cách người dùng làm video recap thực sự suy nghĩ và thao tác:

1. Tool rail dùng ngôn ngữ tác vụ: **Edit, Subtitles, Voice, Style, Media, Effects**.
2. Transcript và Translate là bước trong **AI Workflow**, không phải destination cố định trên rail.
3. Workflow không chiếm một sidebar thường trực; chỉ mở khi người dùng gọi Generate hoặc cần xem tiến trình.
4. App bar không có nút Preview riêng vì Preview luôn hiện trong workspace.
5. Thứ tự ưu tiên không gian bắt buộc: **Preview > Timeline > Inspector > Task Panel**.
6. Subtitle Inspector ưu tiên **Text → Timing → Voice → Style**; metadata/highlight/animation là nội dung phụ.
7. Timeline phải được thiết kế và kiểm thử cho hàng trăm đến hàng nghìn subtitle, không chỉ thay màu sắc.
8. Giao diện dùng panel phẳng và divider nhẹ; card chỉ dùng khi một nhóm cần ranh giới ngữ nghĩa thực sự.

### Chỉ số thành công đề xuất

- Người dùng mới có thể tạo dự án và tìm được thao tác Generate mà không cần hướng dẫn riêng.
- Các thao tác thường dùng: mở dự án, generate, sửa subtitle, thêm layer, preview và export đều có đường đi trực tiếp, tối đa 1–2 lần bấm từ workspace chính.
- Không còn control bị cắt hoặc chồng nhau ở 1280×720, scale Windows 100%, 125% và 150%.
- Tất cả thành phần tương tác đều có hover, focus, pressed, disabled và trạng thái xử lý rõ ràng.
- Không còn màu, font, padding, radius quan trọng được hard-code tùy ý trong từng màn hình.
- Thời gian mở Editor và hiệu năng phát video/timeline không kém bản hiện tại một cách nhận biết được.
- Timeline vẫn thao tác được với tối thiểu 1.000, 5.000 và 10.000 subtitle segment trong bộ stress test, không layout/paint toàn bộ text ngoài viewport.

---

## 2. Hiện trạng đã khảo sát

### 2.1 Nền tảng và cấu trúc

- Desktop UI: PySide6.
- Preview: libmpv, có Qt Multimedia fallback.
- Cửa sổ chính: `ui/main_window.py`.
- Cấu trúc giao diện: `ui/views/`.
- Editor/timeline: `ui/views/editor/` và `ui/views/preview_panel.py`.
- Hành vi UI: nhiều mixin trong `ui/features/`.
- Controller nghiệp vụ: `ui/controllers/`.
- Font đã có: Inter, Roboto, Montserrat, Poppins.
- UI tối thiểu hiện tại: 1024×640; có hai profile responsive desktop/compact.

### 2.2 Bố cục hiện tại

Editor hiện được chia thành:

- Header chứa thương hiệu, tên dự án, Generate, Export, Fast Preview, Projects, More và nút cửa sổ.
- Cột trái cố định chứa workflow và toàn bộ cấu hình Media, Audio, Language, Voice, Style, Advanced.
- Khu vực trên bên phải chứa Preview và Inspector.
- Khu vực dưới bên phải chứa Timeline cùng nhiều action trên một hàng.

### 2.3 Điểm tốt cần giữ

- Workflow nghiệp vụ rõ ràng và đã phản ánh đúng pipeline sản phẩm.
- Preview, Inspector và Timeline đã liên kết theo selection.
- Timeline có video, audio, subtitle và visual layer.
- Có trạng thái hoàn thành của từng bước.
- Có responsive handling, scroll area và splitter cơ bản.
- Logic xử lý đã tách một phần khỏi view qua controller, service và feature mixin.
- Dark theme phù hợp với phần mềm xử lý video.

### 2.4 Vấn đề cần giải quyết

#### Kiến trúc thông tin

- Cột trái chứa quá nhiều nhóm, buộc người dùng cuộn dài và ghi nhớ vị trí.
- “Workflow step”, “thiết lập dự án” và “thuộc tính đối tượng” đang bị trộn trong cùng trải nghiệm.
- Action cấp ứng dụng, cấp dự án và cấp selection chưa phân tầng rõ.
- Một số tính năng quan trọng nằm trong More; một số action ít dùng lại xuất hiện thường trực.
- Inspector có nhiều loại đối tượng nhưng chưa có cấu trúc section thống nhất.

#### Phân cấp thị giác

- Nhiều card có cùng mức nổi, đường viền và độ tương phản nên khó biết vùng nào quan trọng nhất.
- Nhiều nút cùng hình thức khiến primary action và utility action cạnh tranh nhau.
- Hàng công cụ timeline dày, chủ yếu dùng chữ, khó quét nhanh.
- Màu accent đang được dùng cho nhiều mục đích; màu track và màu trạng thái chưa thuộc một hệ thống chung.

#### Tính nhất quán

- Stylesheet toàn cục lớn trong `ui/main_window.py`, đồng thời nhiều widget tiếp tục tự đặt stylesheet cục bộ.
- Radius, kích thước, màu và font size khác nhau giữa launcher, editor, timeline và dialog.
- Có nút dùng emoji hoặc text thay cho icon thống nhất.
- Kích thước cố định xuất hiện nhiều, gây khó cho DPI và localization.

#### Khả dụng

- Preview bị giảm diện tích khi cả cột trái và Inspector cùng mở.
- Các thiết lập ít dùng chiếm không gian thường trực.
- Tên action chưa hoàn toàn nhất quán, ví dụ Fast Preview/Preview, Clean/Exit và một số nhãn kỹ thuật.
- Chưa thể hiện đầy đủ shortcut, tooltip và trạng thái focus bàn phím.
- Thông báo tiến trình và lỗi nằm ở nhiều hình thức khác nhau, chưa có notification system chung.

#### Khả năng bảo trì

- View lớn và nhiều control được tạo trực tiếp trong một số file dài.
- Style gắn với object name và chuỗi QSS, khó đổi theme toàn cục.
- Việc đổi toàn bộ UI trực tiếp trên view cũ có nguy cơ làm hỏng signal binding và state đồng bộ.

---

## 3. Định hướng trải nghiệm mới

### 3.1 Tuyên bố thiết kế

**CapCap Studio** là một editor tập trung, nhanh và tin cậy: nội dung ở giữa, ngữ cảnh ở hai bên, tiến trình ở trên, thời gian ở dưới.

Ba nguyên tắc chủ đạo:

1. **Content first:** Video và timeline luôn là vùng nổi bật nhất.
2. **Contextual controls:** Chỉ hiện thuộc tính liên quan đến đối tượng/tác vụ đang chọn.
3. **Progressive disclosure:** Thiết lập cơ bản hiện trước; cấu hình nâng cao nằm trong section mở rộng hoặc Settings.

### 3.2 Tính cách hình ảnh

- Chuyên nghiệp, hiện đại, gọn, có chiều sâu nhẹ.
- Dark neutral thay vì phủ xanh toàn bộ nền.
- Accent indigo–cyan dùng có kiểm soát cho selection và primary action.
- Bo góc vừa phải, không biến mọi vùng thành card.
- Icon nét đồng nhất, nhãn ngắn, tooltip rõ.
- Chuyển động ngắn và có mục đích, không tạo hiệu ứng trang trí dư thừa.

---

## 4. Kiến trúc thông tin đề xuất

### 4.1 Cấp ứng dụng

- Projects
- Editor
- Settings
- Resource Manager
- Help/About

### 4.2 Điều hướng thường trực trong Editor

Tool rail phản ánh công việc người dùng muốn làm, không phản ánh tên module kỹ thuật:

- Edit
- Subtitles
- Voice
- Style
- Media
- Effects

### 4.3 AI Workflow theo nhu cầu

Pipeline nghiệp vụ vẫn được bảo toàn nhưng chỉ xuất hiện khi người dùng bấm **Generate**, mở tiến trình hoặc cần xử lý lại một bước:

1. Prepare
2. Transcript
3. Translate
4. Voice
5. Subtitles
6. Edit
7. Export

`Transcript` và `Translate` nằm trong AI Workflow và task panel của Subtitles. Chúng không chiếm hai vị trí cố định trên tool rail.

### 4.4 Cấp đối tượng trong Editor

- Video
- Audio
- Subtitle
- Blur
- Logo
- Mask
- Text
- Selection range

### 4.5 Quy tắc đặt action

| Loại action | Vị trí | Ví dụ |
| --- | --- | --- |
| Cấp ứng dụng | App menu / Settings | Resources, About, Logs |
| Cấp dự án | Top bar | Save state, Generate, Export |
| Cấp workflow | Generate / AI Workflow theo nhu cầu | Prepare, Transcript, Translate, Voice |
| Cấp timeline | Toolbar ngay trên timeline | Undo, Redo, Split, Delete, Zoom |
| Cấp selection | Inspector | Timing, speaker, opacity, transform |
| Cấp preview | Toolbar dưới preview | Play, seek, volume, speed, fit |

---

## 5. Khung ứng dụng mới

### 5.1 Bố cục tổng thể

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ App bar: Logo | Project | Saved | Undo Redo         Generate | Export       │
├───────┬──────────────────────────────────────────────────────┬───────────────┤
│ Tool  │                                                      │ Inspector     │
│ rail  │                 Video Preview                        │ theo selection │
│       │                                                      │               │
│       ├──────────────────────────────────────────────────────┤               │
│       │ Timeline toolbar                                     │               │
│       ├──────────────────────────────────────────────────────┤               │
│       │ Timeline                                             │               │
├───────┴──────────────────────────────────────────────────────┴───────────────┤
│ Status bar: task nền | engine/device | timecode | cảnh báo                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Thứ tự ưu tiên và kích thước vùng

Khi không đủ không gian, layout phải bảo vệ vùng làm việc theo đúng thứ tự:

```text
Preview > Timeline > Inspector > Task Panel
```

Điều này có nghĩa là Task Panel phải thu gọn/overlay trước, sau đó Inspector phải đóng hoặc overlay; không được bóp Preview để cố giữ cả hai panel phụ trên màn hình.

- App bar: 56 px logical.
- Tool rail: 56–60 px ở compact, 64 px ở desktop.
- Task Panel: 280–320 px khi dock; dạng overlay/collapsible ở compact.
- Inspector: 280–420 px; mặc định đóng ở 1280×720 và có thể overlay.
- Timeline: đủ cao để đọc và chỉnh subtitle; kéo splitter được, không dùng tỷ lệ cứng cho mọi màn hình.
- Status bar: 28 px.
- Preview được cấp phần không gian còn lại lớn nhất. Mốc 480×270 chỉ là guardrail cuối; hệ thống phải đóng panel phụ trước khi chạm mốc này.

### 5.3 App bar

Bên trái:

- Logo CapCap.
- Nút quay lại Projects.
- Tên dự án, có ellipsis khi dài.
- Chấm trạng thái: Saved / Saving / Unsaved / Error.

Bên phải:

- Undo/Redo ở cấp dự án nếu cần đồng bộ toàn editor.
- Nút **Generate** dạng split button.
- Nút **Export** là primary action khi pipeline đủ điều kiện.
- App menu: Settings, Resources, Logs, Help, Exit project.
- Minimize, maximize/restore, close theo chuẩn Windows.

Quy tắc:

- Chỉ có một primary action nổi bật tại một thời điểm.
- Khi đang xử lý, nút liên quan đổi thành trạng thái progress/cancel phù hợp.
- Không có nút Preview cấp ứng dụng; playback và preview control nằm ngay dưới video.
- Không đặt các action quản trị file SRT thường trực trên app bar; chuyển vào Export hoặc menu của Transcript.

### 5.4 Tool rail và task panel

Tool rail dùng icon + tooltip, gồm:

1. Edit
2. Subtitles
3. Voice
4. Style
5. Media
6. Effects

Khi bấm một mục, task panel mở cạnh rail và hiển thị công cụ liên quan. Bấm lại hoặc dùng shortcut để thu gọn, trả không gian cho Preview. Ở compact laptop, task panel ưu tiên hiển thị dạng overlay và tự đóng sau khi người dùng hoàn tất lựa chọn nếu thao tác không cần panel tồn tại liên tục.

**Generate** mở AI Workflow gồm Prepare, Transcript, Translate và Voice. Workflow progress chỉ xuất hiện dạng popover/task view theo nhu cầu hoặc trạng thái nhỏ trong status bar; tuyệt đối không trở lại thành sidebar lớn thường trực.

Ý nghĩa từng mục:

| Mục | Nội dung chính |
| --- | --- |
| Edit | Công cụ chỉnh sửa chung, selection và các thao tác edit hiện tại |
| Subtitles | Danh sách/biên tập subtitle, AI Workflow Transcript–Translate, import/export SRT |
| Voice | TTS, speaker, voice assignment và regenerate |
| Style | Preset, typography, position, highlight và animation |
| Media | Video, audio, framing và media sources |
| Effects | Blur, Logo, Mask, Text và các effect/layer trực quan |

### 5.5 Inspector

Inspector chỉ phản ánh selection hiện tại:

- Không chọn gì: thông tin dự án/empty state và shortcut hữu ích.
- Chọn subtitle: Text, Timing, Voice và Style trước; Animation/highlight/metadata nằm trong section phụ.
- Chọn audio: gain, speed, fade, mute/solo.
- Chọn visual layer: transform, appearance, timing và replace/delete.
- Chọn video: filter, intensity, framing.
- Chọn nhiều đối tượng: chỉ hiển thị thuộc tính chung và số lượng selection.

Mỗi inspector dùng cùng cấu trúc:

1. Header: icon, tên/type, visibility, lock, menu.
2. Summary: time range hoặc metadata quan trọng.
3. Các section có thể thu gọn.
4. Action nguy hiểm đặt cuối, màu danger và cần xác nhận khi mất dữ liệu.

### 5.6 Status bar

- Trái: tác vụ nền đang chạy và progress rút gọn.
- Giữa: cảnh báo tài nguyên/model nếu có.
- Phải: CPU/GPU, backend preview, timecode và trạng thái autosave.
- Bấm vào tác vụ nền mở Activity Center.

---

## 6. Đặc tả từng màn hình

## 6.1 Launcher / Projects

### Mục tiêu

Giúp người dùng bắt đầu hoặc quay lại dự án trong vài giây; không trộn cấu hình kỹ thuật vào luồng chọn dự án.

### Bố cục

- Header: logo, “Projects”, Settings, Resources, Help.
- Hero gọn: **New project** và vùng kéo-thả video.
- Recent projects dạng grid responsive.
- Bộ lọc/sort: Recent, Name, Status; ô tìm kiếm khi có nhiều dự án.
- Device selector CPU/GPU đặt trong header hoặc settings popover, hiển thị trạng thái tài nguyên ngay bên cạnh.

### Project card

- Thumbnail tỷ lệ 16:9.
- Tên file/dự án tối đa hai dòng.
- Duration, lần mở gần nhất.
- Progress chip: Prepared, Transcribed, Translated, Voiced, Exported.
- Menu ba chấm: Open, Show in folder, Remove from recent, Delete generated data.
- Hover hiển thị nút Open rõ ràng.

### Empty state

- Minh họa hoặc icon đơn giản.
- Tiêu đề “Create your first localization project”.
- Nút New project.
- Dòng hỗ trợ định dạng file.

### Trạng thái lỗi

- File nguồn bị di chuyển: card vẫn tồn tại nhưng có badge Missing source và action Locate.
- Thiếu model/resource: không khóa toàn bộ project card; cho phép mở dự án và hướng dẫn cài đúng resource khi chạy tác vụ cần nó.

---

## 6.2 Media/Edit task panel và bước Prepare

Nội dung:

- Source video: thumbnail nhỏ, tên, duration, resolution, frame rate.
- Subtitle source: Audio (SenseVoice/Whisper) hoặc Video (OCR).
- Source/target language.
- Audio preparation: keep original / remove voice / background source.
- Output framing: ratio, canvas, scale mode.
- Các thiết lập ít dùng được thu gọn dưới tiêu đề mô tả đúng nội dung, không dùng một nhóm “Advanced” chung chung.

Khi Prepare được gọi từ Generate, AI Workflow tái sử dụng các giá trị trên và chỉ hỏi những lựa chọn còn thiếu. Footer task panel:

- Trạng thái readiness.
- Action phù hợp: Prepare hoặc Generate next step.

---

## 6.3 AI Workflow — bước Transcript

Bước này mở trong AI Workflow hoặc khu vực xử lý AI của **Subtitles**, không có icon riêng trên tool rail.

- Engine selector và model.
- Speaker diarization toggle kèm mô tả ngắn.
- Segmentation: single line, words per segment.
- Import source SRT.
- Action Transcribe.
- Sau khi có kết quả: thống kê số segment, speakers, duration, lỗi/đoạn cần kiểm tra.
- Export source SRT đặt trong menu của section kết quả.

Transcript đầy đủ không chỉnh trong một text area dài ở task panel. Chỉnh nội dung diễn ra qua Inspector hoặc Subtitle Editor dạng workspace/dialog chuyên dụng.

---

## 6.4 AI Workflow — bước Translate

Bước này nối tiếp Transcript trong AI Workflow hoặc được gọi lại từ **Subtitles** khi người dùng muốn dịch lại.

- Provider.
- Model/provider status.
- Source → target language.
- Style/tone preset nếu có.
- Test connection ở contextual menu hoặc inline khi cấu hình chưa xác thực.
- Action Translate.
- Kết quả: số dòng đã dịch, số lỗi, cảnh báo độ dài/timing.
- Rewrite/Refine là secondary action sau khi có bản dịch.

API key và base URL chuyển về Settings; không lặp trong panel tác vụ.

---

## 6.5 Voice panel

- TTS engine.
- Default voice.
- Voice type/filter.
- Speaker list dạng compact rows có màu định danh.
- Mỗi speaker: tên, số segment, voice được gán, preview và menu.
- Bulk assign rõ ràng, có preview trước khi áp dụng.
- Action Generate voice.
- Nếu không cần TTS, dùng action “Skip voice” có giải thích ảnh hưởng output.

Không hiển thị tất cả speaker thành card lớn kéo dài. Dùng danh sách ảo hóa hoặc scroll list với row cao 44–52 px.

---

## 6.6 Style panel

- Preset gallery: TikTok, YouTube, Minimal, Custom.
- Preview preset trực tiếp trên video hoặc thumbnail mẫu.
- Typography: font, size, weight, color.
- Outline/shadow/background.
- Position và safe area.
- Animation/highlight.
- Save as preset / reset.

Mọi thay đổi phải phản ánh ngay trên Preview và có debounce để không gây giật.

---

## 6.7 Video Preview

### Canvas

- Nền gần đen để tập trung nội dung.
- Video căn giữa theo tỷ lệ, không bị ép méo.
- Safe-area overlay chỉ hiện khi bật.
- Selection box dùng handle rõ, cursor đúng ngữ cảnh.
- Overlay OCR/blur/logo/mask/text phải dùng cùng hệ selection.

### Control bar

Thứ tự đề xuất:

- Play/Pause.
- Previous/next edit hoặc frame step nếu được hỗ trợ.
- Timecode current / total.
- Seek bar.
- Volume/mute.
- Playback speed.
- Fit/100%/fullscreen preview.
- Menu overlay/view options.

Các action tạo Blur, Logo, Mask, Text chuyển sang nút **Add** chung hoặc Tool rail; không trộn với playback control.

### Trạng thái

- No media: drop zone + Open video.
- Loading: skeleton/spinner không chặn toàn app.
- Preview render đang chạy: progress overlay nhỏ, có Cancel.
- Backend error: thông báo rõ MPV/fallback và action Retry/Diagnostics.

---

## 6.8 Timeline

Timeline là vùng làm việc quan trọng thứ hai sau Preview. Khi cần thu hẹp layout, phải đóng Task Panel rồi Inspector trước khi giảm Timeline xuống dưới mức có thể đọc và chỉnh clip subtitle.

### Toolbar

Nhóm theo chức năng và dùng icon:

- History: Undo, Redo.
- Edit: Split, Delete.
- Selection: Select range, Clear.
- Add: Subtitle, Blur, Logo, Mask, Text.
- View: Track visibility, Snap, Zoom out/in, Fit.
- Alt transcription xuất hiện khi có selection range hợp lệ, không luôn chiếm chỗ.

### Ruler và playhead

- Ruler có major/minor tick theo zoom.
- Playhead tương phản cao, vùng kéo rộng hơn đường hiển thị.
- Time tooltip khi hover/scrub.
- Selection range có fill trong suốt, handles và duration label.

### Track header

- Màu type indicator.
- Icon + tên track.
- Mute/visibility/lock tùy loại track.
- Height resize hoặc preset compact/normal nếu cần.
- Context menu cho rename, duplicate, remove đối với track hỗ trợ.

### Layer/clip

- Selected: border accent + handle rõ.
- Hover: nâng contrast, hiển thị tooltip.
- Disabled/locked: giảm saturation nhưng vẫn đọc được.
- Clip subtitle hiển thị tối đa 1–2 dòng theo chiều cao track; text vượt quá dùng ellipsis.
- Hover subtitle clip hiển thị tooltip toàn văn cùng start/end time; tooltip không che playhead hoặc điểm đang kéo.
- Audio hiển thị waveform; video hiển thị thumbnail theo mức zoom phù hợp.
- Không dựa riêng vào màu để phân biệt speaker hoặc trạng thái; bổ sung nhãn/icon/pattern phù hợp.

### Quy mô subtitle và virtualized rendering

Yêu cầu này là bắt buộc đối với video recap dài:

- Chỉ paint và layout text cho clip nằm trong viewport cộng một vùng đệm nhỏ hai bên.
- Không tạo một QWidget con cho mỗi subtitle clip; dùng custom paint/QGraphics item nhẹ hoặc cơ chế tương đương.
- Dùng time-range index để tìm clip nhìn thấy, không duyệt và layout lại toàn bộ danh sách ở mỗi frame/scroll.
- Cache text elision/layout theo `segment id + text + zoom + track height`; invalidation chỉ xảy ra khi dữ liệu liên quan đổi.
- Ở zoom thấp, ưu tiên khối màu/biên clip; chỉ vẽ text khi chiều rộng đủ đọc.
- Tooltip toàn văn được tạo theo nhu cầu khi hover, không tồn tại thường trực cho mọi clip.
- Selection, playhead và drag feedback phải cập nhật độc lập với tác vụ persist nặng; persist dùng debounce khi an toàn.
- Stress test bắt buộc với ít nhất 1.000, 5.000 và 10.000 subtitle segment.

### Màu track đề xuất

| Loại | Màu nhận diện | Token |
| --- | --- | --- |
| Video | Blue | `track.video` |
| Audio | Emerald | `track.audio` |
| Subtitle | Violet | `track.subtitle` |
| Voice/TTS | Orange | `track.voice` |
| Blur | Cyan | `track.blur` |
| Logo/Image | Pink | `track.image` |
| Mask | Amber | `track.mask` |
| Text | Purple | `track.text` |

---

## 6.9 Subtitle Inspector

Thứ tự section bắt buộc phản ánh tần suất chỉnh sửa của người làm recap:

```text
Subtitle
├─ Text
├─ Timing
├─ Voice
├─ Style
└─ Animation / More
```

`Text`, `Timing` và `Style` phải truy cập nhanh nhất. Speaker/Voice đứng sau Timing. Highlight, metadata và các tùy chọn hiếm dùng nằm trong Animation/More hoặc section thu gọn, không ngang cấp về thị giác với nội dung chính.

### Header

- “Subtitle” + segment index.
- Start–end time chip.
- Visibility/lock/menu nếu phù hợp.

### Text

- Source text readonly/collapsible.
- Translated text editor chính.
- Counter số ký tự/tốc độ đọc; cảnh báo khi vượt ngưỡng.
- Save tự động khi blur hoặc sau debounce, có trạng thái Saved.

### Timing

- Start, End, Duration.
- Validate `start < end`, không âm, không vượt video.
- Nút align to playhead cho start/end.

### Speaker & voice

- Speaker selector có chấm màu + tên.
- Voice speed.
- Regenerate voice chỉ bật khi có translated text và voice hợp lệ.

### Style

- Preset/style hiện tại và các override quan trọng của riêng segment nếu hệ thống hỗ trợ.
- Các thao tác style thường dùng được hiển thị trực tiếp; thiết lập đầy đủ mở sang Style panel.

### Animation / More

- Animation, highlight và metadata nằm trong section mặc định thu gọn.
- Không để các tùy chọn này đẩy Text hoặc Timing ra khỏi vùng nhìn đầu tiên.

### Actions

- Rewrite.
- Open Subtitle Editor.
- Add highlight from selection nằm trong Animation/More.
- Delete segment ở cuối panel, style danger.

---

## 6.10 Visual Layer Inspectors

Tất cả Blur, Logo, Mask và Text dùng schema chung:

- General: name, visible, locked.
- Timing: start, end, duration.
- Transform: position X/Y, scale, rotation nếu hỗ trợ.
- Appearance: opacity và thuộc tính riêng.
- Quick position: lưới 3×3 thay cho năm nút text riêng.
- Reset section.
- Replace source khi áp dụng.
- Delete layer.

Giá trị slider luôn có input số đi kèm để vừa thao tác nhanh vừa nhập chính xác.

---

## 6.11 Export

Export nên là sheet/dialog chuyên dụng thay vì dồn trong panel trái.

### Bố cục hai cột

Trái:

- Output mode.
- Quality/preset.
- Resolution/canvas/ratio/frame rate.
- Audio handling.
- Subtitle burn-in/SRT options.
- Output folder và tên file.

Phải:

- Summary đầu ra.
- Ước lượng hợp lệ nếu có thể lấy nhanh.
- Checklist readiness: video, transcript, translation, voice, resources.
- Cảnh báo có thể bấm để quay về nơi sửa.

Footer:

- Cancel.
- Export.
- Khi chạy: progress tổng, phase hiện tại, ETA nếu đáng tin cậy, Background và Cancel.

---

## 6.12 Settings

Navigation bên trái, nội dung bên phải:

- General: language, autosave, recent projects.
- Processing: device, ASR engine defaults, concurrency.
- Translation: provider, model, API key, base URL, test connection.
- Voice: engine/defaults.
- Preview: backend, caching.
- Appearance: theme, UI scale nếu cần.
- Resources: shortcut sang Resource Manager.
- Diagnostics & Paths: paths, logs và chẩn đoán kỹ thuật.

API key hiển thị dạng password, có Show/Hide và không ghi vào log.

---

## 6.13 Resource Manager

- Summary: Ready / Action required.
- Filter theo Installed, Missing, Optional.
- Resource row: tên, mục đích, dung lượng, trạng thái, path và action.
- Download có progress riêng, pause/cancel nếu backend hỗ trợ.
- Trạng thái Partial phải giải thích thiếu thành phần nào.
- Sau khi cài, validate lại và cập nhật UI không cần restart nếu có thể.

---

## 6.14 Activity Center, thông báo và dialog

### Activity Center

- Danh sách pipeline/export/download đang chạy hoặc vừa hoàn tất.
- Mỗi task: tên, phase, progress, thời gian, status, action mở log/cancel/retry.
- Task nền không chiếm modal nếu không bắt buộc.

### Toast

- Success: tự đóng sau 3–5 giây.
- Info: tự đóng hoặc có action.
- Warning/Error: giữ lâu hơn; lỗi quan trọng cần action View details.
- Tối đa ba toast xếp chồng.

### Dialog

- Dùng dialog cho xác nhận phá hủy, cấu hình tập trung hoặc lỗi cần quyết định.
- Không dùng dialog cho thông báo thành công thông thường.
- Nút theo thứ tự Windows; primary ở bên phải, danger được phân biệt rõ.

---

## 6.15 Ngôn ngữ hiển thị và nhãn chuẩn

Tên chức năng phải ngắn, quen thuộc với người làm recap và mô tả kết quả người dùng muốn đạt được. Không dùng tên kiến trúc hoặc thuật ngữ kỹ thuật làm navigation label.

### Nhãn đã chốt

```text
Tool rail:   Edit | Subtitles | Voice | Style | Media | Effects
Header:      ProjectName.mp4 | Saved | Undo | Redo | Generate | Export
Workflow:    Prepare | Transcript | Translate | Voice | Subtitles | Edit | Export
Inspector:   Subtitle | Text | Timing | Voice | Style | Animation
Timeline:    Video | Audio | Voice | Subtitle
```

### Nhãn cần tránh khi không phải tên tính năng chính thức

```text
Media Workflow
Voice Timing Synchronization
Advanced
Show Progress
```

Nếu cần phần nâng cao, dùng tiêu đề cụ thể theo nội dung hoặc đặt trong menu/section phụ. Nếu cần xem tiến trình, trạng thái task và Activity Center phải tự thể hiện thay vì nút “Show Progress” mơ hồ.

---

## 7. Design system

## 7.1 Màu sắc — theme “CapCap Studio Dark”

### Surface

| Token | Giá trị đề xuất | Mục đích |
| --- | --- | --- |
| `surface.canvas` | `#0B0D12` | Nền app |
| `surface.panel` | `#11141B` | Panel chính |
| `surface.elevated` | `#171B24` | Popover/dialog/card nổi |
| `surface.hover` | `#1C2230` | Hover |
| `surface.selected` | `#202A44` | Selection nền |
| `surface.input` | `#0F1218` | Input |

### Border

| Token | Giá trị đề xuất | Mục đích |
| --- | --- | --- |
| `border.subtle` | `#242A36` | Phân vùng nhẹ |
| `border.default` | `#303847` | Control/card |
| `border.strong` | `#475569` | Focus phụ |
| `border.focus` | `#7C8CFF` | Focus chính |

### Text

| Token | Giá trị đề xuất | Mục đích |
| --- | --- | --- |
| `text.primary` | `#F4F7FB` | Tiêu đề/nội dung chính |
| `text.secondary` | `#B4BDCA` | Nội dung phụ |
| `text.muted` | `#7E8999` | Metadata/helper |
| `text.disabled` | `#535D6C` | Disabled |
| `text.inverse` | `#0A0C10` | Trên nền sáng |

### Accent và semantic

| Token | Giá trị đề xuất | Mục đích |
| --- | --- | --- |
| `accent.primary` | `#7C8CFF` | Primary/selection |
| `accent.hover` | `#94A2FF` | Hover primary |
| `accent.pressed` | `#6575E8` | Pressed |
| `semantic.success` | `#45D39C` | Thành công |
| `semantic.warning` | `#F5B94C` | Cảnh báo |
| `semantic.danger` | `#F06A77` | Lỗi/xóa |
| `semantic.info` | `#57B8FF` | Thông tin |

Yêu cầu contrast phải được kiểm tra thực tế; giá trị trên là baseline, được tinh chỉnh trong visual QA nếu chưa đạt.

## 7.2 Typography

- UI font chính: **Inter Variable** đã có trong assets.
- Subtitle preview vẫn cho phép Roboto, Montserrat, Poppins và font tùy chọn.
- Không dùng quá ba weight thường xuyên: 400, 500/600, 700.

| Style | Size | Weight | Line height | Dùng cho |
| --- | ---: | ---: | ---: | --- |
| Display | 24 | 700 | 32 | Empty state/launcher |
| Heading 1 | 18 | 650–700 | 26 | Tên màn hình/dialog |
| Heading 2 | 15 | 600 | 22 | Section/card title |
| Body | 13 | 400 | 20 | Nội dung chính |
| Body small | 12 | 400 | 18 | Helper/metadata |
| Label | 12 | 600 | 16 | Control label |
| Caption | 11 | 500 | 16 | Chip/timecode |

Không dùng chữ dưới 11 px cho thông tin cần đọc.

## 7.3 Spacing

Dùng lưới 4 px:

- `space.1 = 4`
- `space.2 = 8`
- `space.3 = 12`
- `space.4 = 16`
- `space.5 = 20`
- `space.6 = 24`
- `space.8 = 32`

Mặc định:

- Khoảng cách label–control: 6–8 px.
- Control trong nhóm: 8–12 px.
- Section: 20–24 px.
- Panel padding: 16 px.
- Dialog padding: 20–24 px.

## 7.4 Radius và elevation

- Control: 6 px.
- Button/input lớn: 8 px.
- Dialog/popover: 10 px.
- Pill/chip: radius bằng nửa chiều cao.
- Elevation chủ yếu bằng border + chênh surface; hạn chế shadow nặng trong desktop Qt.

### Quy tắc panel phẳng

- App shell, task panel, Inspector và Timeline là các mặt phẳng chính, phân cách bằng divider hoặc chênh surface nhẹ.
- Không bọc mỗi section hoặc setting trong một card riêng.
- Section dùng heading, spacing và divider trước khi dùng background/border riêng.
- Card chỉ dùng cho project card, empty state/action group đặc biệt, cảnh báo quan trọng hoặc nhóm có ranh giới ngữ nghĩa độc lập.
- Không lồng card trong card.
- Visual QA phải kiểm tra mật độ để UI gần với editor desktop hiện đại, không giống dashboard web gồm nhiều hộp.

## 7.5 Icon

- Một bộ icon SVG nét thống nhất, kích thước gốc 20 hoặc 24 px.
- Kích thước trong toolbar: 18–20 px.
- Không dùng emoji làm icon sản phẩm.
- Icon-only button luôn có tooltip và accessible name.
- Các icon nguy hiểm không được dựa riêng vào màu.
- Trước triển khai cần chọn một bộ icon có license phù hợp và lưu asset cục bộ để app hoạt động offline.

## 7.6 Component chuẩn

Danh mục tối thiểu:

- `CcButton`: primary, secondary, ghost, danger, icon.
- `CcIconButton`.
- `CcSplitButton`.
- `CcTextField`, `CcTextArea`, `CcNumberField`.
- `CcSelect`, `CcSearchField`.
- `CcCheckbox`, `CcRadio`, `CcSwitch`.
- `CcSliderField` gồm slider + số.
- `CcChip`, `CcStatusBadge`.
- `CcSection`, `CcCollapsibleSection`.
- `CcPanelHeader`, `CcInspectorHeader`.
- `CcEmptyState`.
- `CcToast`, `CcInlineAlert`.
- `CcProgress`, `CcTaskRow`.
- `CcMenu`, `CcTooltip`.
- `CcDialog`, `CcSheet`.
- `CcPropertyRow`.

Mỗi component phải có state: default, hover, focus-visible, pressed, disabled; component nhập liệu thêm error, warning và success nếu phù hợp.

---

## 8. Tương tác và motion

- Hover/focus transition: 100–150 ms.
- Panel mở/đóng: 160–220 ms, ease-out.
- Toast vào/ra: 160–200 ms.
- Không animate layout nặng trong lúc video phát.
- Tôn trọng tùy chọn reduced motion nếu có thể lấy từ hệ điều hành hoặc settings.
- Drag timeline/overlay phải ưu tiên phản hồi tức thời; persist có debounce.
- Autosave hiển thị trạng thái nhỏ, không bật dialog.
- Action mất dữ liệu cần confirmation hoặc undo.

### Quy ước feedback

| Tình huống | Feedback |
| --- | --- |
| Click action nhanh | Spinner trong nút nếu >300 ms |
| Tác vụ dài | Activity Center + status bar |
| Thành công thông thường | Toast |
| Validation lỗi | Inline dưới field + focus field đầu tiên |
| Lỗi hệ thống | Inline alert/toast có View details |
| Xóa clip/layer | Undo toast nếu có thể; nếu không thì confirm |

---

## 9. Responsive và DPI

### Profile A — Compact laptop

- Kích thước mục tiêu: 1280×720 logical trở lên.
- Tool rail 56–60 px.
- Task Panel không dock thường trực; mở dạng overlay/collapsible 280 px và đóng nhanh bằng `Esc` hoặc bấm lại tool.
- Inspector mặc định đóng; khi mở dùng overlay hoặc chiếm 288–320 px chỉ khi Preview vẫn đạt guardrail.
- App bar 52 px; action ít dùng chuyển vào menu.
- Preview nhận phần không gian lớn nhất; Timeline được giữ đủ cao cho subtitle editing.
- Timeline toolbar tự gom action phụ vào overflow.
- Không cho phép Task Panel và Inspector cùng dock nếu làm Preview nhỏ hơn guardrail.

### Profile B — Standard desktop

- 1440×900 đến 1920×1080.
- Rail 64 px, task panel 300–320 px.
- Inspector 320–360 px.
- Preview vẫn ưu tiên hơn Timeline; Inspector hoặc Task Panel có thể mở, nhưng layout không mặc định ép cả hai panel cùng tồn tại.

### Profile C — Large desktop

- Trên 1920 px hoặc màn hình ultrawide.
- Inspector tối đa 420 px.
- Có thể mở task panel và Inspector đồng thời mà Preview vẫn giữ kích thước lớn.
- Không kéo giãn text/input vô hạn; dùng max width hợp lý.

### Quy tắc kỹ thuật

Mọi profile phải áp dụng thứ tự co/ẩn sau:

1. Đưa action ít dùng vào overflow.
2. Thu gọn hoặc overlay Task Panel.
3. Đóng hoặc overlay Inspector.
4. Giảm phần trống/chrome không thiết yếu.
5. Chỉ sau đó mới giảm Timeline và Preview, vẫn phải tôn trọng guardrail sử dụng.

- Dùng logical pixels và layout stretch/minimum, hạn chế `setFixedSize`.
- Chỉ fixed size cho icon button hoặc control thực sự bất biến.
- Kiểm tra Windows scaling 100%, 125%, 150%, 175%.
- Font và icon không được mờ ở DPR khác nhau.
- Ghi nhớ splitter/panel state theo profile hoặc screen geometry hợp lệ.
- Khi màn hình thay đổi, clamp kích thước panel về vùng hợp lệ.

---

## 10. Accessibility và khả năng sử dụng

- Tất cả control có accessible name; icon-only có description/tooltip.
- Tab order theo thứ tự nhìn từ trên xuống, trái sang phải.
- Focus ring luôn nhìn thấy khi dùng bàn phím.
- Shortcut không xung đột với nhập text.
- Màu chữ và control hướng tới WCAG 2.1 AA cho nội dung thông thường.
- Không dùng màu là dấu hiệu duy nhất của trạng thái/speaker/track.
- Vùng click tối thiểu 28×28 px; action chính hướng tới 32–36 px trở lên.
- Tooltip mô tả tác dụng, có shortcut nếu tồn tại.
- Lỗi phải nói rõ điều gì sai và cách sửa.
- Text hỗ trợ localization: không ghép câu bằng nhiều label; chừa chỗ cho nhãn dài hơn 30–50%.

### Shortcut baseline đề xuất

| Shortcut | Hành động |
| --- | --- |
| Space | Play/Pause khi không focus ô nhập |
| Ctrl+Z / Ctrl+Shift+Z | Undo/Redo |
| Delete | Xóa selection hợp lệ |
| Ctrl+S | Lưu/persist ngay |
| Ctrl+E | Mở Export |
| Ctrl+, | Settings |
| `+` / `-` | Zoom timeline khi timeline focus |
| Esc | Hủy tool/range/overlay hoặc đóng popover |

Shortcut cuối cùng phải được kiểm tra với hành vi hiện có trước khi triển khai.

---

## 11. Kiến trúc triển khai đề xuất

### 11.1 Nguyên tắc

- Không viết lại engine xử lý media.
- Giữ controller/service/workflow hiện có; thay view theo từng lớp.
- Tạo design system trước, sau đó mới dựng màn hình.
- Giảm dần stylesheet cục bộ, không tiếp tục thêm chuỗi QSS mới trong view.
- Dùng feature flag hoặc nhánh triển khai riêng để UI mới có thể được kiểm thử trước khi thay hoàn toàn.

### 11.2 Cấu trúc thư mục đích

```text
ui/
├── design_system/
│   ├── tokens.py
│   ├── theme.py
│   ├── icons.py
│   ├── typography.py
│   └── components/
├── shell/
│   ├── app_bar.py
│   ├── tool_rail.py
│   ├── task_panel.py
│   ├── inspector_host.py
│   ├── status_bar.py
│   └── workspace.py
├── panels/
│   ├── edit_panel.py
│   ├── subtitles_panel.py
│   ├── voice_panel.py
│   ├── style_panel.py
│   ├── media_panel.py
│   └── effects_panel.py
├── workflow_ui/
│   ├── ai_workflow.py
│   └── steps/
│       ├── prepare_step.py
│       ├── transcript_step.py
│       ├── translate_step.py
│       └── voice_step.py
├── inspectors/
│   ├── subtitle_inspector.py
│   ├── audio_inspector.py
│   ├── video_inspector.py
│   └── visual_layer_inspectors.py
├── timeline/
├── dialogs/
├── controllers/
├── features/
└── legacy/                  # Chỉ tồn tại trong giai đoạn chuyển đổi
```

Tên thư mục cuối cùng có thể điều chỉnh theo convention hiện tại, nhưng ranh giới design system/shell/panel/inspector cần được giữ.

### 11.3 State và signal

- Xác định một view-state rõ cho project readiness, active workflow step, selection, running tasks và panel visibility.
- View không tự suy luận trạng thái nghiệp vụ từ text của widget.
- Signal từ component phải mang dữ liệu có kiểu/ngữ nghĩa rõ.
- Mapping từ state hiện tại sang UI mới đặt trong presenter/view-model hoặc adapter, không nhúng vào stylesheet.
- Khi thay từng panel, giữ API tương thích tạm thời với các feature mixin để tránh big-bang rewrite.

### 11.4 Theme

- Token Python là nguồn sự thật duy nhất.
- QSS được tạo hoặc ghép từ token theo component.
- Màu timeline custom paint cũng lấy từ token, không hard-code riêng.
- Icon tint theo semantic role.
- Launcher, main window, dialog và toast dùng cùng theme manager.

### 11.5 Hiệu năng

- Không tạo lại toàn bộ inspector khi selection thay đổi; dùng stacked/lazy panels.
- Không phát sinh pixmap/icon mới liên tục; có cache theo size/color/DPR.
- Không animate geometry của video surface trong khi playback nếu gây giật.
- Speaker list dài nên lazy/virtualized hoặc giới hạn widget phức tạp.
- Timeline paint phải giữ logic tối ưu hiện tại và chỉ thay visual theo token.
- Subtitle timeline cần viewport culling, time-range index, lazy text layout và cache theo zoom như mục 6.8.
- Không dùng một QWidget cho mỗi subtitle/speaker row khi số lượng có thể lên hàng nghìn.
- Instrument số clip được layout/paint trong mỗi viewport để phát hiện việc render ngoài vùng nhìn.
- Benchmark phải tách thao tác scroll, zoom, scrub, select, drag và sửa text; không chỉ đo thời gian mở project.

---

## 12. Lộ trình triển khai

## Giai đoạn 0 — Chốt thiết kế

Đầu ra:

- Duyệt tài liệu này.
- Chốt concept màu, typography và bố cục.
- Chốt ngôn ngữ UI: English hiện tại, Vietnamese, hoặc cơ chế đa ngôn ngữ.
- Chốt icon set và license.
- Chụp baseline UI ở các độ phân giải mục tiêu.

Không sửa UI sản phẩm trước khi hoàn tất giai đoạn này.

## Giai đoạn 1 — Design system foundation

- Tokens.
- Theme manager.
- Font loading.
- Icon loader/cache.
- Button, input, select, switch, slider field, badge, section, tooltip, dialog.
- Gallery/demo nội bộ cho component và state.
- Test screenshot/component cơ bản.

Tiêu chí ra khỏi giai đoạn: component không phụ thuộc màn hình cụ thể và hoạt động ở nhiều DPI.

## Giai đoạn 2 — Launcher và Settings

- Launcher mới.
- Project card mới.
- Settings navigation.
- Resource Manager mới.
- Dialog/toast/inline alert chuẩn.

Lý do làm trước: ít phụ thuộc timeline, giúp kiểm chứng design system với rủi ro thấp hơn Editor.

## Giai đoạn 3 — Editor shell

- App bar.
- Tool rail/task panel host.
- Inspector host.
- Status bar/Activity Center.
- Splitter, persistence và responsive profiles.
- Áp dụng thứ tự không gian `Preview > Timeline > Inspector > Task Panel` và compact overlay behavior.
- Giữ Preview và Timeline cũ bên trong shell mới ở bước đầu.

## Giai đoạn 4 — Task panels và AI Workflow

- Edit.
- Subtitles, gồm Transcript/Translate trong AI Workflow.
- Voice.
- Style.
- Media/Prepare.
- Effects.
- Phân loại lại các thiết lập cũ trong Advanced và đưa từng mục về đúng panel hoặc Diagnostics & Paths.

Mỗi panel phải map đủ signal/hành vi cũ trước khi xóa view tương ứng.

## Giai đoạn 5 — Inspectors và Preview controls

- Subtitle inspector.
- Audio/video inspector.
- Blur/logo/mask/text inspector.
- Preview toolbar và overlay states.
- Validation, autosave indicator và keyboard focus.

## Giai đoạn 6 — Timeline visual overhaul

- Toolbar grouping/overflow.
- Ruler/playhead/selection.
- Track headers.
- Clip/layer visual states.
- Subtitle preview 1–2 dòng, ellipsis và tooltip toàn văn.
- Virtualized rendering/culling và text-layout cache.
- Context menu, tooltip và keyboard navigation.
- Performance benchmark với 1.000, 5.000 và 10.000 subtitle segment.

## Giai đoạn 7 — Export và Activity Center

- Export sheet/dialog.
- Progress/background/cancel.
- Unified task state.
- Error details và log access.

## Giai đoạn 8 — Loại bỏ legacy và hoàn thiện

- Xóa stylesheet/view không còn dùng sau khi đối chiếu chức năng.
- Kiểm tra toàn bộ workflow CPU/GPU.
- Accessibility pass.
- DPI/responsive pass.
- Polish copy, tooltip, empty/loading/error states.
- Cập nhật README, How to Use và ảnh preview.

---

## 13. Ma trận bảo toàn chức năng

| Chức năng hiện tại | Nơi mới | Yêu cầu bảo toàn |
| --- | --- | --- |
| New/Open recent project | Launcher | Đường dẫn, recent history, thumbnail/cache |
| CPU/GPU | Launcher/Settings/Status | Kiểm tra resource và fallback |
| Prepare/extract/separate | Media panel / AI Workflow | Luồng và output hiện có |
| Whisper/SenseVoice/OCR | Subtitles / AI Workflow | Engine settings và validation |
| Import/export SRT | Subtitles menu, Export | Không đổi format |
| Translate/rewrite | Subtitles / AI Workflow / Inspector | Provider và prompt behavior |
| TTS/speaker assignment | Voice panel/Subtitle Inspector | Voice preview và regenerate |
| Subtitle presets/style | Style panel | Live preview và persistence |
| Fast Preview | Preview control/menu | Giữ render 5 giây; không cần nút app bar riêng |
| OCR Translator | Add/tools/view menu | Không thay transcript project |
| Blur/Logo/Mask/Text | Add menu + Inspector | Timing, transform, persist, export |
| Timeline split/delete/range | Timeline toolbar | Selection semantics hiện tại |
| Track visibility/lock | Track header | Không đổi ý nghĩa preview/export |
| Export | Export sheet | Chất lượng, ratio, audio, folder |
| Logs/resources | Activity Center/Settings | Export/clear log và resource status |

Không được coi một màn hình mới là hoàn tất nếu bất kỳ hành vi tương ứng nào trong bảng bị mất.

---

## 14. Kiểm thử và nghiệm thu

### 14.1 Functional regression

- Tạo và mở project.
- Prepare với các mode hỗ trợ.
- Transcript bằng từng engine khả dụng.
- Import source SRT.
- Translate và rewrite.
- Generate/skip TTS.
- Speaker diarization và voice assignment.
- Chỉnh subtitle text/timing/speaker/speed.
- Add/edit/split/delete từng loại layer.
- Range selection và alt transcription.
- Fast Preview.
- Export từng output mode chính.
- Autosave, mở lại và khôi phục đúng state.

### 14.2 Visual QA

Các kích thước tối thiểu:

- 1280×720 @ 100%.
- 1366×768 @ 125%.
- 1920×1080 @ 100% và 150%.
- Màn hình ultrawide nếu có.

Kiểm tra:

- Không clip/overlap.
- Ellipsis và tooltip đúng.
- Popup không ra ngoài màn hình.
- Focus ring và tab order.
- Contrast, disabled state, error state.
- Icon sắc nét.
- Splitter và panel state khôi phục hợp lệ.

### 14.3 Performance QA

- Thời gian Launcher mở.
- Thời gian Editor sẵn sàng.
- FPS/độ mượt preview trước và sau.
- Độ trễ kéo playhead, drag clip, resize overlay.
- Timeline với video dài/nhiều subtitle.
- Memory khi đổi selection/inspector liên tục.

Bộ dữ liệu timeline bắt buộc:

| Bộ test | Mục đích |
| --- | --- |
| 1.000 segment | Kịch bản recap dài thông thường |
| 5.000 segment | Kịch bản nặng, kiểm tra scroll/zoom/scrub |
| 10.000 segment | Stress test culling, memory và text-layout cache |

Với mỗi bộ cần ghi lại: thời gian mở timeline, memory tăng thêm, số clip được layout/paint trong viewport, độ trễ scroll/zoom/scrub/select/drag và độ trễ sau khi sửa text. Không nghiệm thu nếu chi phí paint/layout tăng theo toàn bộ số segment trong khi viewport không đổi.

Ngưỡng cụ thể cần lấy từ baseline trước triển khai; mục tiêu là không có regression đáng kể.

### 14.4 Accessibility QA

- Hoàn thành luồng cơ bản chỉ bằng bàn phím ở mức hợp lý.
- Screen reader đọc được tên control quan trọng.
- Không có action icon-only thiếu accessible name.
- Không có thông tin chỉ truyền bằng màu.
- Text không bị mất khi scale lớn.

---

## 15. Tiêu chí nghiệm thu cuối cùng

UI mới chỉ được coi là hoàn tất khi:

1. Toàn bộ màn hình trong phạm vi đã dùng design system chung.
2. Launcher, Editor, Timeline, Inspector, Settings, Resource Manager và Export có cùng ngôn ngữ hình ảnh.
3. Không mất chức năng so với ma trận bảo toàn.
4. Không có lỗi layout nghiêm trọng ở các cấu hình màn hình/DPI mục tiêu.
5. Primary/secondary/danger action rõ và nhất quán.
6. Có đầy đủ empty, loading, success, warning, error và disabled state.
7. Shortcut, tooltip, focus và accessible name quan trọng đã được bổ sung.
8. Playback, timeline và tác vụ nền không có regression đáng kể.
9. Stylesheet cục bộ cũ đã được loại bỏ hoặc có lý do tồn tại rõ ràng.
10. Tài liệu sử dụng và ảnh sản phẩm được cập nhật theo UI mới.
11. Timeline đạt yêu cầu hiển thị subtitle 1–2 dòng, ellipsis, tooltip toàn văn và vượt qua bộ test 1.000/5.000/10.000 segment.

---

## 16. Rủi ro và cách giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Viết lại UI làm đứt signal/state | Cao | Adapter tương thích, thay từng panel, regression checklist |
| QSS/custom widget khác nhau theo DPI | Cao | Component gallery, test nhiều scale từ giai đoạn 1 |
| Timeline mới giảm hiệu năng | Cao | Giữ logic paint, benchmark trước/sau, cache icon/pixmap |
| Phạm vi lan sang engine | Trung bình | Khóa phạm vi: UI/view-state, không đổi workflow engine |
| Có quá nhiều setting trong panel mới | Trung bình | Progressive disclosure, chuyển config hệ thống về Settings |
| Người dùng cũ khó thích nghi | Trung bình | Giữ tên workflow, onboarding ngắn, tooltip và migration notes |
| Icon hoặc font làm tăng package | Thấp | Asset SVG tối ưu, font đã có, kiểm tra license |

---

## 17. Ngoài phạm vi của lần nâng cấp UI

Trừ khi được phê duyệt riêng, lần triển khai này không bao gồm:

- Thay engine Whisper, SenseVoice, OCR, TTS, FFmpeg hoặc translation provider.
- Thay định dạng project, subtitle hoặc output.
- Viết lại timeline domain model.
- Thêm cloud sync/collaboration.
- Đổi Windows desktop app sang web/Electron.
- Thêm tính năng edit video nghiệp vụ mới không tồn tại trong bản hiện tại.
- Đổi thuật toán transcription, translation, voice hoặc export.

---

## 18. Quyết định đã chốt và còn cần duyệt

### Đã chốt sau vòng phản biện 1.1

1. Giữ bố cục **Tool Rail | Preview + Timeline | Contextual Inspector**.
2. Tool rail dùng **Edit, Subtitles, Voice, Style, Media, Effects**.
3. Transcript/Translate nằm trong AI Workflow, không là mục rail độc lập.
4. Workflow/Task Panel chỉ mở khi cần, không chiếm sidebar thường trực.
5. Header dùng **Project, Saved, Undo, Redo, Generate, Export**; bỏ nút Preview cấp ứng dụng.
6. Thứ tự không gian là **Preview > Timeline > Inspector > Task Panel**.
7. Inspector mặc định đóng/overlay ở 1280×720.
8. Subtitle Inspector ưu tiên **Text, Timing, Voice, Style**.
9. Timeline subtitle bắt buộc hỗ trợ 1–2 dòng, ellipsis, tooltip toàn văn và virtualized rendering.
10. UI dùng panel phẳng; không lạm dụng card.

### Còn cần chốt trước khi triển khai

1. Có dùng theme **CapCap Studio Dark** với accent indigo `#7C8CFF` hay muốn một hướng màu khác.
2. UI tiếp tục dùng tiếng Anh, chuyển sang tiếng Việt, hay chuẩn bị song ngữ ngay từ đầu.
3. Export dùng modal dialog hay right-side sheet; tài liệu đề xuất dialog/sheet chuyên dụng.
4. Có giữ tên sản phẩm “CapCap” hay dùng nhãn giao diện “CapCap Studio”.
5. Có cho phép xây component gallery/screenshot baseline trước khi dựng màn hình thật hay không.

### Đề xuất mặc định

- Dùng CapCap Studio Dark.
- Chuẩn bị code cho localization nhưng giữ English làm ngôn ngữ mặc định trong lần đầu.
- Export dùng dialog lớn không modal trong tương lai nếu kiến trúc cho phép; giai đoạn đầu có thể dùng modal để giảm rủi ro.
- Giữ thương hiệu hiển thị “CapCap”; “Studio Dark” chỉ là tên design system nội bộ.
- Bắt buộc có component gallery và baseline trước khi migration Editor.

---

## 19. Thứ tự phê duyệt đề xuất

1. Duyệt mục tiêu và phạm vi.
2. Duyệt wireframe/bố cục tổng thể.
3. Duyệt màu, font, spacing và component style.
4. Duyệt đặc tả Launcher và Editor chính.
5. Chốt các quyết định ở mục 18.
6. Sau đó mới bắt đầu Giai đoạn 1 — Design system foundation.

Tài liệu này là nguồn tham chiếu triển khai. Mọi thay đổi lớn về bố cục, workflow hoặc phạm vi sau khi duyệt cần được ghi lại trong phần quyết định thay đổi để tránh UI mới phát triển không nhất quán.
