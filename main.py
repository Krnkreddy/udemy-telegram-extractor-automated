import asyncio
import json
import os
import requests
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityUrl
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# ENVIRONMENT CONFIG
# ─────────────────────────────────────────────
API_ID = int(os.getenv("TG_API_ID", os.getenv("TELEGRAM_API_ID", "26972239")))
API_HASH = os.getenv("TG_API_HASH", os.getenv("TELEGRAM_API_HASH", "fa03ac53e4eacbf1c845e55bf7de09df"))
SESSION_STRING = os.getenv("TELETHON_STRING_SESSION", "")
GROUP = os.getenv("GROUP_USERNAME", "@getstudyfevers")

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
BOT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# FILE PATHS
# ─────────────────────────────────────────────
SEEN_FILE = Path("udemy_seen_ids.json")
OUTPUT_FILE = Path("udemy_links.txt")


# ─────────────────────────────────────────────
# SAFE JSON LOADER
# ─────────────────────────────────────────────
def load_seen_ids():
    """Safely load JSON or create new empty set if invalid."""
    if not SEEN_FILE.exists():
        SEEN_FILE.write_text("[]", encoding="utf-8")
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8").strip() or "[]")
        if isinstance(data, list):
            return set(map(int, data))
        return set()
    except Exception:
        SEEN_FILE.write_text("[]", encoding="utf-8")
        return set()


def save_seen_ids(ids):
    """Save IDs safely."""
    SEEN_FILE.write_text(json.dumps(sorted(list(ids))), encoding="utf-8")


# ─────────────────────────────────────────────
# TELEGRAM SCRAPER
# ─────────────────────────────────────────────
async def get_coursefolder_links_from_telegram():
    print("📩 Fetching messages from Telegram...")
    if SESSION_STRING:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    else:
        client = TelegramClient("session", API_ID, API_HASH)

    await client.start()

    seen = load_seen_ids()
    new_seen = set(seen)
    links = []

    async for msg in client.iter_messages(GROUP, limit=300):
        if msg.id in seen:
            continue
        new_seen.add(msg.id)
        text = msg.message or ""
        if "coursefolder.net" in text:
            for part in text.split():
                if "coursefolder.net" in part:
                    clean = part.strip(".,;()[]\"'")
                    links.append(clean)

        if msg.entities:
            for e in msg.entities:
                if isinstance(e, MessageEntityUrl):
                    url = text[e.offset:e.offset + e.length]
                    if "coursefolder.net" in url:
                        links.append(url.strip(".,;()[]\"'"))

    save_seen_ids(new_seen)
    await client.disconnect()
    print(f"✅ Found {len(links)} new CourseFolder links.")
    return list(set(links))


# ─────────────────────────────────────────────
# UDEMY LINK EXTRACTOR
# ─────────────────────────────────────────────
async def extract_udemy_links(coursefolder_links):
    udemy_links = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        for link in coursefolder_links:
            try:
                print(f"🌐 Visiting: {link}")
                await page.goto(link, timeout=60000)
                anchors = await page.query_selector_all("a[href*='udemy.com/course/']")
                for a in anchors:
                    href = await a.get_attribute("href")
                    if href and "udemy.com/course/" in href:
                        udemy_links.append(href)
                        print(f"🎓 Found: {href}")
            except Exception as e:
                print(f"⚠️ Error: {e}")

        await browser.close()

    return list(dict.fromkeys(udemy_links))  # remove duplicates


# ─────────────────────────────────────────────
# TELEGRAM BOT NOTIFICATION
# ─────────────────────────────────────────────
def send_bot_message(text):
    if not BOT_TOKEN or not BOT_CHAT_ID:
        print("⚠️ Missing bot credentials, skipping notification.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": BOT_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=20
        )
    except Exception as e:
        print(f"Bot send failed: {e}")


# ─────────────────────────────────────────────
# MAIN LOGIC
# ─────────────────────────────────────────────
async def main():
    coursefolder_links = await get_coursefolder_links_from_telegram()

    if not coursefolder_links:
        msg = "🚫 No new CourseFolder links found."
        print(msg)
        send_bot_message(msg)
        return

    udemy_links = await extract_udemy_links(coursefolder_links)

    if not udemy_links:
        msg = "⚠️ No Udemy links found."
        print(msg)
        send_bot_message(msg)
        return

    OUTPUT_FILE.write_text("\n".join(udemy_links), encoding="utf-8")
    msg = "🎯 Udemy Courses Found:\n\n" + "\n".join(udemy_links)
    send_bot_message(msg)
    print("✅ Task completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
