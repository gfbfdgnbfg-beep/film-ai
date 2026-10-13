# Triển khai AI Film Factory V0.5 Hybrid trên GitHub + Render

## Quan trọng: bảo toàn V0.4 hiện có

Website Render Free dùng ổ đĩa tạm. **Trước khi đẩy V0.5**, hãy mở V0.4 → chọn từng phim → `Sao lưu phim ZIP`. Mỗi lần deploy lại có thể làm mất SQLite, ảnh, phim đã upload. Để thử an toàn, tạo service Render **mới** hoặc dùng GitHub branch **mới** mà Render V0.4 chưa theo dõi.

## A. Đẩy mã nguồn

1. Giải nén file `AI_Film_Factory_V05_GitHub_Render_Ready.zip`.
2. Tạo nhánh mới trên repository `film-ai` ví dụ `v0.5-hybrid` rồi upload **toàn bộ nội dung thư mục giải nén** (không upload file ZIP vào root).
3. Đừng đưa mật khẩu, API token hay file `.env` lên GitHub. `.env.example` chỉ là ví dụ, không chứa token thật.
4. Trên Render, dùng nhánh V0.5 và tệp `render.yaml`. Có thể tạo service mới thay vì sửa service đang chạy để bảo vệ V0.4.

## B. Render Environment

| Tên biến | Giá trị |
|---|---|
| `APP_MODE` | `production` |
| `APP_ACCESS_PASSWORD` | mật khẩu đăng nhập website dài tối thiểu 12 ký tự |
| `APP_SESSION_SECRET` | chuỗi random tối thiểu 32 ký tự |
| `AI_FILM_AGENT_TOKEN` | chuỗi random tối thiểu 32 ký tự, **khác** với các mật khẩu trên |
| `AI_FILM_DATA` | `/app/runtime_data` |

Tạo một token bằng Python: `python -c "import secrets; print(secrets.token_urlsafe(36))"`. Không gửi token vào chat.

**Không dùng `OPENAI_API_KEY`**. Nếu còn khóa cũ trong Render, bạn nên xóa biến đó trong mục Environment. Ứng dụng V0.5 không gọi API OpenAI.

## C. Chạy Agent trên Windows

1. Cài Python 3.11+ và Ollama.
2. `ollama pull qwen2.5:7b` (cần tải mô hình một lần, tốn dung lượng ổ cứng).
3. Trong thư mục đã giải nén, chạy `pip install -r requirements.txt`.
4. Double-click `start_agent_windows.cmd`.
5. Nhập URL Render V0.5 và `AI_FILM_AGENT_TOKEN` (nhập ẩn) khi được yêu cầu.
6. Giữ PC và Agent bật, website sẽ hiện **Desktop Agent đang kết nối**.

Agent **chủ động kết nối ra HTTPS**. Không mở port 11434 của Ollama ra Internet. Không đặt `AI_FILM_AGENT_TOKEN` trong mã nguồn hoặc GitHub.

## D. Kiểm thử đầu ra

1. Nhập kịch bản hoàn chỉnh do bạn viết → tạo phim.
2. AI Director → Ollama phân cảnh → kiểm tra shot bằng trang `/studio` → duyệt.
3. Asset Manager → import hình/video/giọng Việt cho mỗi shot; hoặc dùng thẻ mô phỏng để thử FFmpeg nếu chưa có asset.
4. Đầu ra → chọn 30 giây → dựng video → chờ Agent upload MP4/SRT về website.
5. Xem phim, tải MP4, SRT và ZIP ngay sau khi hoàn thành.

## Lưu ý kỹ thuật

- V0.5 không cung cấp adapter tự động cho website tạo video hay TTS. Chrome extension tùy chọn chỉ dán prompt theo lệnh người dùng. Cần kiểm tra điều khoản, độ tuổi và quyền sử dụng của từng nền tảng.
- Render Free không phù hợp cho lưu trữ dài hạn và có thể giới hạn dung lượng tải lên. Chỉ nên thử clip ngắn, backup thường xuyên.
- Muốn kiểm tra API tự động mà không gọi Ollama thật: `python tests/test_hybrid.py`.
- Có thể chạy website ở máy cục bộ: `uvicorn backend.main:app --host 127.0.0.1 --port 8765`.
