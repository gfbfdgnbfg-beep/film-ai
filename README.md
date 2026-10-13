# AI Film Factory V0.5 — HYBRID FREE (GitHub / Render / Windows)

**Đây là gói V0.5 mới, xây dựng trực tiếp từ V0.4.** OpenAI API **đã bị loại khỏi backend và giao diện**: không còn endpoint AI Writer, `OPENAI_API_KEY` không được sử dụng. V0.5 giữ quản lý dự án / nhân vật / storyboard / node editor / sao lưu và thêm công cụ điều phối Ollama + FFmpeg trên Windows.

## Đã hoạt động trong V0.5

1. **Website mới tại `/`**: tạo dự án, nhập kịch bản người dùng viết, xem trạng thái Desktop Agent, hàng đợi, storyboard, tài nguyên từng shot, đầu ra.
2. **Ollama AI Director thật** (trên PC, mặc định `qwen2.5:7b`): đọc kịch bản và phân tích nhân vật, bối cảnh, hành động, góc máy, prompt ảnh/video theo từng nhóm 7 shot. Không tự ý thay nội dung gốc. AI vẫn có thể hiểu sai: cần người kiểm tra và duyệt. Giữ storyboard cũ khi tác vụ lỗi.
3. **Desktop Agent** kết nối chủ động tới Render bằng một token bí mật riêng (header `X-Film-Agent-Token`), không mở cổng máy ở nhà; tác vụ được queue và tiếp tục xử lý khi PC online.
4. **Asset Manager**: tải lên ảnh PNG/JPG/WEBP, video MP4, giọng Việt MP3/WAV riêng cho từng shot. Có nút sao chép prompt để sử dụng với công cụ khác. `browser_extension/` là một tiện ích **tùy chọn** để nhận diện tab và dán prompt vào ô nhập sau khi chính bạn bấm nút; không tự tạo/tải video.
5. **FFmpeg dựng phim thật trên Windows**: lấy ảnh/video/voice theo từng shot, ghép clip có tiếng hoặc silent, tạo `.srt` và xuất `.mp4` dọc 480×854 (bản xem thử tối đa 120 giây). Nếu FFmpeg có libass, cố gắng chèn phụ đề vào video; nếu không, SRT vẫn được cung cấp riêng. Video tạo từ ảnh vẫn là ảnh tĩnh; không giả vờ có AI motion.
6. **Mục Đầu ra** trên Render: xem MP4, tải MP4/SRT và sao lưu phim ZIP. **Trình chỉnh sửa nâng cao V0.4** được giữ tại `/studio` sau khi loại bỏ nút OpenAI.

## Chưa tích hợp — không tuyên bố tự động sai sự thật

- **Chưa có chuỗi tác vụ tự thao tác trên mọi tab Chrome, Google Flow, Kling, Dola, Vbee, ElevenLabs.** Phần Browser Manager hiện chỉ mở trang HTTPS thủ công và sao chép prompt; tiện ích Chrome tùy chọn có thể dán prompt khi bạn nhấn nút; file tải về được bạn upload lên website. Mỗi dịch vụ cần một bộ adapter phù hợp giấy phép/điều khoản, có thể cần xác nhận thủ công.
- **Chưa tạo ảnh hoặc video AI miễn phí tự động từ ComfyUI/Wan**; adapter local GPU sẽ ở bước tiếp theo. GPU RTX 3060 12 GB có thể thử Wan nhưng không cam kết chạy ổn định toàn phim.
- **Không tự tạo giọng Việt** trong gói này: bạn có thể dùng TTS hợp lệ hoặc tự ghi âm, rồi upload.
- **Render Free** không lưu bền vững file/SQLite sau khi restart/redeploy. Sao lưu ZIP sau mỗi lần làm việc. Bản miễn phí chỉ phù hợp thử với clip ngắn, không phù hợp upload video 8 phút lớn. Với các tính năng như lưu trữ bền vững, API/trang AI có thể phát sinh chi phí.

## A. Chạy backend V0.5 trên máy tính để kiểm thử

```powershell
cd AI_Film_Factory_V05_GitHub_Render_Ready
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Mở `http://127.0.0.1:8765`. Local mặc định không cần mật khẩu (chỉ truy cập trên chính máy đó). Để dùng Desktop Agent với backend cục bộ, trước khi mở server cũng phải đặt **cùng** `AI_FILM_AGENT_TOKEN` ở terminal server.

## B. Đưa V0.5 lên Render, không làm hỏng V0.4

1. Tải ZIP này và giải nén. Sao lưu dữ liệu hiện có từ website V0.4 bằng nút **Sao lưu phim ZIP** *trước khi redeploy*, vì Render Free là ổ đĩa tạm.
2. Upload mã nguồn V0.5 lên **branch mới** trên GitHub trước; chỉ chuyển Render sang branch mới khi muốn thử. Không cần đưa secret lên GitHub.
3. Render Environment: giữ `APP_MODE=production`, `APP_ACCESS_PASSWORD`, `APP_SESSION_SECRET`. Bổ sung `AI_FILM_AGENT_TOKEN` — bí mật ngẫu nhiên tối thiểu 32 ký tự, **khác mật khẩu đăng nhập**. Có thể tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(36))"`.
4. **Xóa `OPENAI_API_KEY` cũ khỏi Render Environment** vì V0.5 không dùng. Việc này do bạn thực hiện trên Render; mã nguồn không tự thay đổi Environment.
5. Deploy bản mới. Mở `/` sẽ là Hybrid Studio; `/studio` là trình chỉnh sửa shot/nodes được giữ lại.

**Lưu ý:** nếu dùng dịch vụ Render hiện tại, thay source/branch sẽ kích hoạt restart và **dữ liệu V0.4 có nguy cơ mất trên Render Free**. Hãy backup trước, hoặc dùng Render service mới để thử an toàn.

## C. Kết nối Ollama trên PC Windows

1. Cài [Ollama](https://ollama.com/) và Python 3.11+.
2. Trong PowerShell chạy `ollama pull qwen2.5:7b`. Có thể test bằng `ollama run qwen2.5:7b`.
3. Giải nén ZIP ở PC, `pip install -r requirements.txt`.
4. Mở `start_agent_windows.cmd` (hoặc `python desktop_agent/agent.py`). Nhập địa chỉ website HTTPS và **AI_FILM_AGENT_TOKEN** bằng cửa sổ dòng lệnh (ẩn). Giữ terminal này mở khi sản xuất.
5. Website báo **Desktop Agent đang kết nối**. Tạo/chọn dự án → lưu kịch bản → **Phân cảnh bằng Ollama** → chờ Agent tạo các shot → kiểm tra `/studio` → **Duyệt phân cảnh**.
6. Tab **Ảnh · Video · Giọng**: đưa ảnh/video/MP3/WAV vào từng shot (công cụ web AI bên ngoài vẫn làm thủ công ở bản này).
7. Tab **Đầu ra** → chọn 30/60/120 giây → **FFmpeg dựng video** → đợi hoàn tất → xem và tải MP4/SRT/ZIP về máy.

### Hướng sử dụng nguồn tài nguyên miễn phí

- AI Director bằng Ollama là miễn phí token, nhưng dùng CPU/GPU/điện của PC.
- FFmpeg và Python là phần mềm miễn phí.
- Chỉ sử dụng trang AI bên thứ ba phù hợp độ tuổi, quyền sử dụng và điều khoản; V0.5 không vượt CAPTCHA, credit, rate limit hay điều kiện thanh toán.
- Dùng clip **30 giây** để thử trước; phim 8 phút cần thời gian và nhiều video/âm thanh hơn.

## Tiện ích Chrome Tab Assistant (tùy chọn)

Mở Chrome → `chrome://extensions` → bật Developer mode → **Load unpacked** và chọn thư mục `browser_extension` trong gói ZIP. Khi đã mở một website AI được phép sử dụng, bấm biểu tượng Tab Assistant: tiện ích nhận diện tab đang mở, lấy prompt từ clipboard nếu bạn cho phép, rồi điền vào ô nhập sau khi bạn bấm nút. **Không tự nhấn gửi, không vượt CAPTCHA và không tự tải kết quả.** Các giao diện website thay đổi thường xuyên nên một số trang sẽ phải dán thủ công.

## Cấu trúc dự án

- `backend/main.py`: API V0.4 tương thích nhưng không có OpenAI Writer
- `backend/hybrid.py`: API tác vụ Hybrid, nhận và phục vụ file, bảo vệ token
- `backend/security.py`: gate mật khẩu và ghép nối Agent độc lập
- `desktop_agent/agent.py`: Ollama + pipeline FFmpeg trên Windows
- `browser_extension/`: tiện ích Chrome nhận diện tab và dán prompt theo thao tác người dùng
- `frontend/dist/hybrid.html`: giao diện Hybrid mới
- `frontend/dist/assets/hybrid.js`, `hybrid.css`: bản static dùng trên Render
- `frontend/src/hybrid.js`, `hybrid.css`: mã nguồn giao diện mới
- `frontend/dist/assets/studio-offline.js`: trình biên tập nâng cao legacy, đã bỏ OpenAI
- `tests/test_hybrid.py`: kiểm thử API V0.5 bằng Agent giả lập, không gửi request tới Ollama thật

**Không chứa API key, mật khẩu Render hoặc Agent Token. Không có lệnh tự đăng nhập hay tự tiêu credit AI.**
