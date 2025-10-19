# main.py
import asyncio
import json
import os
from pathlib import Path
from typing import Set, List

from playwright.async_api import async_playwright
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityUrl
import requests

# ---------- Config (from env / fallback) ----------
TG_API_ID = int(os.getenv("TG_API_ID", os.getenv("TELEGRAM_API_ID", "26972239")))
TG_API_HASH = os.getenv("TG_API_HASH", os.getenv("TELEGRAM_API_HASH", "fa03ac53e4eacbf1c845e55bf7de09df"))
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "@getstudyfevers")  # channel/group to read
TELETHON_STRING_SESSION = os.getenv("TELETHON_STRING_SESSION")  # preferred (GitHub Actions)
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
BOT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = Path("udemy_seen_ids.json")
UDemy_OUT_FILE = Path("udemy_links.txt")

# ---------- Safe seen IDs handling ----------
def load_seen_ids() -> Set[int]:
    """Load seen IDs safely. If file missing/empty/corrupt, return empty set and rewrite file."""
    try:
        if not SEEN_FILE.exists():
            SEEN_FILE.write_text("[]", encoding="utf-8")
            return set()
        data = SEEN_FILE.read_text(encoding="utf-8").strip()
        if not data:
            # empty file -> treat as empty list
            SEEN_FILE.write_text("[]", encoding="utf-8")
            return set()
        loaded = json.loads(data)
        if isinstance(loaded, list):
            return set(int(x) for x in loaded)
        # if file contains an unexpected structure, reset
        SEEN_FILE.write_text("[]", encoding="utf-8")
        return set()
    except (json.JSONDecodeError, ValueError):
        print("⚠️ udemy_seen_ids.json corrupt or invalid JSON — resetting file.")
        try:
            SEEN_FILE.write_text("[]", encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Failed to reset seen file: {e}")
        return set()
    except Exception as e:
        print(f"⚠️ Unexpected error loading seen IDs: {e}")
        return set()

def save_seen_ids(seen_ids: Set[int]) -> None:
    """Write seen IDs atomically."""
    try:
        tmp = SEEN_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(list(seen_ids)), indent=2), encoding="utf-8")
        tmp.replace(SEEN_FILE)
    except Exception as e:
        print(f"⚠️ Failed to save seen IDs: {e}")

# ---------- Udemy extractor (Playwright) ----------
async def extract_udemy_links_from_coursefolder(playwright, coursefolder_links: List[str]) -> List[str]:
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    udemy_links = []

    for link in coursefolder_links:
        print(f"🌐 Visiting: {link}")
        try:
            await page.goto(link, timeout=0)
            # detect potential captcha redirect
            if "captcha" in page.url.lower():
                print(f"🤖 CAPTCHA detected — skipping {link}")
                continue

            # look for udemy course anchor
            try:
                await page.wait_for_selector("a[href^='https://www.udemy.com/course/']", timeout=10000)
                anchor = await page.query_selector("a[href^='https://www.udemy.com/course/']")
                if anchor:
                    udemy_url = await anchor.get_attribute("href")
                    if udemy_url:
                        udemy_links.append(udemy_url)
                        print(f"✅ Found Udemy: {udemy_url}")
            except Exception:
                print(f"🔎 No udemy link found on {link}")
                # continue to next link
        except Exception as e:
            print(f"❗ Error visiting {link}: {e}")

    await browser.close()
    # dedupe preserves order
    seen = set()
    deduped = []
    for u in udemy_links:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped

# ---------- Telegram scraper (Telethon) ----------
async def get_coursefolder_links_from_telegram() -> List[str]:
    print("📥 Connecting to Telegram...")
    # choose client session
    if TELETHON_STRING_SESSION:
        client = TelegramClient(StringSession(TELETHON_STRING_SESSION), TG_API_ID, TG_API_HASH)
    else:
        client = TelegramClient("session_name", TG_API_ID, TG_API_HASH)

    await client.start()
    seen_ids = load_seen_ids()
    new_ids = set(seen_ids)  # we'll union at end
    course_links = []

    try:
        async for msg in client.iter_messages(GROUP_USERNAME, limit=500):
            # only consider text messages with entities
            if not msg:
                continue
            mid = int(msg.id)
            if mid in seen_ids:
                continue
            # mark seen (we'll save later)
            new_ids.add(mid)
            # parse URL entities
            if msg.entities:
                for ent in msg.entities:
                    if isinstance(ent, MessageEntityUrl):
                        try:
                            url_text = msg.message[ent.offset : ent.offset + ent.length]
                        except Exception:
                            # fallback to using msg.entities raw URL if any
                            url_text = None
                        if not url_text:
                            continue
                        if "coursefolder.net" in url_text:
                            print(f"✅ Found coursefolder link: {url_text}")
                            course_links.append(url_text)
            # also try to extract plain URLs in case no MessageEntityUrl is present
            # (Telethon may not always mark entities for forwarded/simple messages)
            if msg.message and "coursefolder.net" in msg.message:
                # quick extract by splitting
                parts = [p for p in msg.message.split() if "coursefolder.net" in p]
                for p in parts:
                    # simple cleanup of trailing punctuation
                    p_clean = p.strip(".,;()[]<>\"'")
                    if p_clean not in course_links:
                        course_links.append(p_clean)
    except Exception as e:
        print(f"❗ Error iterating messages: {e}")
    finally:
        await client.disconnect()

    # persist seen IDs
    save_seen_ids(new_ids)
    print(f"🔁 Collected {len(course_links)} coursefolder links (new).")
    return course_links

# ---------- Telegram bot notifier ----------
def send_telegram_message(text: str) -> None:
    if not BOT_TOKEN or not BOT_CHAT_ID:
        print("⚠️ BOT_TOKEN or BOT_CHAT_ID missing — skipping send.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": BOT_CHAT_ID, "text": text, "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        print("✅ Sent message via Telegram bot.")
    except Exception as e:
        print(f"❌ Failed to send telegram message: {e}")

# ---------- Main flow ----------
async def main():
    coursefolder_links = await get_coursefolder_links_from_telegram()
    if not coursefolder_links:
        msg = "🚫 No new coursefolder links found today."
        print(msg)
        send_telegram_message(msg)
        return

    async with async_playwright() as playwright:
        udemy_links = await extract_udemy_links_from_coursefolder(playwright, coursefolder_links)

    if not udemy_links:
        msg = "⚠️ No Udemy links extracted today."
        print(msg)
        send_telegram_message(msg)
        return

    # save to udemy_links.txt (overwrite) and also prepare message
    try:
        UDemy_OUT_FILE.write_text("\n".join(udemy_links), encoding="utf-8")
        print(f"📝 Saved {len(udemy_links)} links to {UDemy_OUT_FILE}")
    except Exception as e:
        print(f"⚠️ Could not write output file: {e}")

    # Format message (shorten if too long)
    message = "🎓 Today's Udemy Courses:\n\n" + "\n".join(udemy_links)
    if len(message) > 4000:
        # split into chunks
        parts = []
        cur = ""
        for line in message.splitlines(True):
            if len(cur) + len(line) > 3500:
                parts.append(cur)
                cur = line
            else:
                cur += line
        if cur:
            parts.append(cur)
        for p in parts:
            send_telegram_message(p)
    else:
        send_telegram_message(message)

if __name__ == "__main__":
    asyncio.run(main())
