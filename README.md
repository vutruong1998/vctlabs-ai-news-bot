# VCT Labs · Bot tin AI qua Telegram

Mỗi sáng 8:17 (giờ Việt Nam), bot đọc tin AI mới trong 24 giờ qua từ OpenAI, Google DeepMind, Hugging Face, TechCrunch, The Verge và Hacker News. Claude chọn tối đa 5 tin đáng chú ý nhất, tóm tắt bằng tiếng Việt và gợi ý một câu hook để làm Short, rồi gửi vào Telegram của bạn. Chạy miễn phí trên GitHub Actions, không cần bật máy.

## Cài đặt (khoảng 10 phút)

### 1. Tạo bot Telegram
1. Mở Telegram, tìm **@BotFather**, gửi lệnh `/newbot`.
2. Đặt tên bot (ví dụ `VCT Labs News`) và username (ví dụ `vctlabs_news_bot`).
3. BotFather gửi lại một **token** dạng `123456789:ABC...`. Giữ bí mật token này.
4. Mở bot vừa tạo và bấm **Start** (bot chỉ nhắn được cho người đã Start nó).

### 2. Lấy chat ID
- Nhắn cho **@userinfobot**, nó trả về `Id` của bạn, đó là chat ID.
- Muốn gửi vào nhóm: thêm bot vào nhóm, chat ID của nhóm là số âm (bắt đầu bằng `-100...`).

### 3. Đưa code lên GitHub
1. Tạo repo mới (có thể để **Private**).
2. Tải lên `ai_news_bot.py` và file workflow tại đúng đường dẫn `.github/workflows/ai-news.yml`.

### 4. Thêm secrets
Vào repo › **Settings › Secrets and variables › Actions › New repository secret**, thêm:

| Tên | Giá trị |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token từ BotFather |
| `TELEGRAM_CHAT_ID` | chat ID ở bước 2 |
| `ANTHROPIC_API_KEY` | (tuỳ chọn) API key từ console.anthropic.com, để có tóm tắt tiếng Việt và ý tưởng Short |

Không có `ANTHROPIC_API_KEY` thì bot vẫn chạy, chỉ gửi danh sách tiêu đề kèm link.

### 5. Chạy thử
Tab **Actions › VCT Labs AI news to Telegram › Run workflow**. Sau khoảng 1 phút, tin nhắn sẽ đến Telegram.

## Tuỳ chỉnh
- **Giờ gửi:** sửa dòng `cron` trong file workflow (giờ UTC = giờ Việt Nam trừ 7).
- **Nguồn tin:** sửa danh sách `FEEDS` trong `ai_news_bot.py`. Nguồn nào lỗi sẽ tự bỏ qua.
- **Chạy thử trên máy:** `DRY_RUN=1 python ai_news_bot.py` để in bản tin ra màn hình thay vì gửi.
