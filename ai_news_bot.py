"""VCT Labs — AI news to Telegram.

Đọc tin AI mới trong N giờ qua từ các RSS feed, (tuỳ chọn) dùng Claude tóm tắt
bằng tiếng Việt + gợi ý ý tưởng Short, rồi gửi qua bot Telegram.

Biến môi trường:
  TELEGRAM_BOT_TOKEN   (bắt buộc) token bot lấy từ @BotFather
  TELEGRAM_CHAT_ID     (bắt buộc) chat id của bạn hoặc của nhóm/kênh
  ANTHROPIC_API_KEY    (tuỳ chọn) có thì tóm tắt bằng Claude, không có thì gửi danh sách tiêu đề
  LOOKBACK_HOURS       (tuỳ chọn) mặc định 24
  CLAUDE_MODEL         (tuỳ chọn) mặc định claude-haiku-5-5
  DRY_RUN=1            (tuỳ chọn) in ra màn hình thay vì gửi Telegram
"""
import email.utils
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# Thêm / bớt nguồn tuỳ ý. Nguồn nào lỗi sẽ được bỏ qua.
FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Hacker News (AI, 100+ điểm)": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini&points=100",
}

UA = "Mozilla/5.0 (VCT Labs AI news bot)"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url, data=None, headers=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as ex:  # in nội dung lỗi để dễ sửa (không chứa token)
        detail = ex.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {ex.code}: {detail}") from None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)  # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def clean(text, limit=400, strip_tags=True):
    text = html.unescape(text or "")
    if strip_tags:
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_feed(source, raw):
    root = ET.fromstring(raw)
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append({
            "source": source,
            "title": clean(it.findtext("title"), 200, strip_tags=False),
            "link": (it.findtext("link") or "").strip(),
            "summary": clean(it.findtext("description")),
            "date": parse_date(it.findtext("pubDate")),
        })
    for e in root.iter(ATOM + "entry"):  # Atom
        link = ""
        for l in e.findall(ATOM + "link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        items.append({
            "source": source,
            "title": clean(e.findtext(ATOM + "title"), 200, strip_tags=False),
            "link": link,
            "summary": clean(e.findtext(ATOM + "summary") or e.findtext(ATOM + "content")),
            "date": parse_date(e.findtext(ATOM + "published") or e.findtext(ATOM + "updated")),
        })
    return items


def collect(hours):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen, out = set(), []
    for source, url in FEEDS.items():
        try:
            items = parse_feed(source, fetch(url))
        except Exception as ex:  # một nguồn lỗi không làm hỏng cả bản tin
            print(f"[bỏ qua] {source}: {ex}", file=sys.stderr)
            continue
        for it in items:
            if not it["title"] or not it["link"] or not it["date"] or it["date"] < since:
                continue
            key = it["link"].split("?")[0].rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def summarize_with_claude(items, api_key, model):
    listing = "\n".join(
        f"[{i}] ({it['source']}) {it['title']} — {it['summary'][:250]}" for i, it in enumerate(items[:40])
    )
    prompt = (
        "Bạn là biên tập viên của VCT Labs, kênh YouTube Shorts tiếng Việt về AI tool, model và công nghệ mới.\n"
        "Dưới đây là các tin trong 24 giờ qua. Hãy chọn tối đa 5 tin đáng chú ý nhất về AI model hoặc AI tool MỚI "
        "(bỏ qua tin chính trị, gọi vốn thuần tuý, bài ý kiến). Trả về JSON đúng dạng:\n"
        '{"items":[{"id":<số trong ngoặc vuông>,"tom_tat":"1-2 câu tiếng Việt, dễ hiểu","y_tuong_short":"1 câu hook cho video Short"}]}\n'
        "Chỉ trả về JSON, không thêm chữ nào khác.\n\n" + listing
    )
    body = json.dumps({"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]}).encode()
    headers = {"Authorization": f"Bearer {api_key}", "x-api-key": api_key,
               "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if os.environ.get("ANTHROPIC_WORKSPACE_ID"):
        headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
    raw = fetch("https://api.anthropic.com/v1/messages", data=body, timeout=90, headers=headers)
    text = "".join(b.get("text", "") for b in json.loads(raw).get("content", []))
    m = re.search(r"\{.*\}", text, re.S)
    picks = json.loads(m.group(0))["items"] if m else []
    result = []
    for p in picks:
        i = p.get("id")
        if isinstance(i, int) and 0 <= i < len(items):
            result.append({**items[i], "tom_tat": p.get("tom_tat", ""), "y_tuong": p.get("y_tuong_short", "")})
    return result


def build_messages(items, summarized):
    today = datetime.now(timezone(timedelta(hours=7))).strftime("%d/%m/%Y")
    head = f"🧪 <b>VCT Labs · Tin AI mới {today}</b>\n"
    blocks = []
    if not items:
        blocks.append("Hôm nay chưa có tin AI mới đáng chú ý từ các nguồn đã theo dõi.")
    elif summarized:
        for n, it in enumerate(summarized, 1):
            b = f"<b>{n}. {html.escape(it['title'])}</b>\n<i>{html.escape(it['source'])}</i>\n"
            if it["tom_tat"]:
                b += f"{html.escape(it['tom_tat'])}\n"
            if it["y_tuong"]:
                b += f"🎬 Ý tưởng Short: {html.escape(it['y_tuong'])}\n"
            b += f'<a href="{html.escape(it["link"], quote=True)}">Đọc thêm</a>'
            blocks.append(b)
    else:
        for n, it in enumerate(items[:10], 1):
            blocks.append(f'{n}. <a href="{html.escape(it["link"], quote=True)}">{html.escape(it["title"])}</a>'
                          f" <i>({html.escape(it['source'])})</i>")
    # Telegram giới hạn 4096 ký tự / tin nhắn → chia nhỏ
    msgs, cur = [], head
    for b in blocks:
        if len(cur) + len(b) + 2 > 3900:
            msgs.append(cur)
            cur = ""
        cur += "\n" + b + "\n"
    msgs.append(cur)
    return msgs


def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    res = json.loads(fetch(f"https://api.telegram.org/bot{token}/sendMessage", data=data))
    if not res.get("ok"):
        raise RuntimeError(f"Telegram lỗi: {res}")


def main():
    hours = int(os.environ.get("LOOKBACK_HOURS", "24"))
    dry = os.environ.get("DRY_RUN") == "1"
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not dry and not (token and chat):
        sys.exit("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID")
    items = collect(hours)
    print(f"Tìm thấy {len(items)} tin trong {hours} giờ qua", file=sys.stderr)
    summarized = []
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and items:
        try:
            summarized = summarize_with_claude(items, key, os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5"))
        except Exception as ex:
            print(f"[Claude lỗi, gửi danh sách thường] {ex}", file=sys.stderr)
    for m in build_messages(items, summarized):
        if dry:
            print(m, "\n" + "-" * 40)
        else:
            send_telegram(token, chat, m)
    print("Xong", file=sys.stderr)


if __name__ == "__main__":
    main()
