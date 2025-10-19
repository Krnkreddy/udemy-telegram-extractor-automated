import asyncio
import json
import os
import re
from telethon import TelegramClient
from datetime import datetime

# Telegram credentials (use GitHub Secrets)
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE")
CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL", "freecourses")

SEEN_FILE = "udemy_seen_ids.json"


# ---------- Safe JSON Utilities ----------
def load_seen_ids():
    """Load seen message IDs, handle missing or empty file."""
    if not os.path.exists(SEEN_FILE):
        print("📄 No seen file found — creating new one.")
        save_seen_ids(set())
        return set()
    try:
        with open(SEEN_FILE, "r") as f:
            data = f.read().strip()
            if not data:
                print("⚠️ Seen file empty — resetting.")
                return set()
            return set(json.loads(data))
    except json.JSONDecodeError:
        print("❌ Corrupted seen file — resetting.")
        save_seen_ids(set())
        return set()


def save_seen_ids(ids):
    """Save message IDs safely."""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f, indent=2)


# ---------- Extract Links ----------
def extract_coursefolder_links(text):
    return re.findall(r"https?://(?:www\.)?coursefolder\.net[^\s]+", text)


# ---------- Telegram Scraper ----------
async def get_coursefolder_links_from_telegram():
    print("📥 Connecting to Telegram...")
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start(phone=PHONE_NUMBER)

    seen_ids = load_seen_ids()
    new_seen = set(seen_ids)
    coursefolder_links = []

    async for msg in client.iter_messages(CHANNEL_USERNAME, limit=50):
        if msg.id not in seen_ids and msg.message:
            links = extract_coursefolder_links(msg.message)
            if links:
                coursefolder_links.extend(links)
                new_seen.add(msg.id)

    save_seen_ids(new_seen)
    await client.disconnect()
    print(f"✅ Found {len(coursefolder_links)} new coursefolder links.")
    return coursefolder_links


# ---------- Extract Udemy Links ----------
async def extract_udemy_links(coursefolder_links):
    import aiohttp
    udemy_links = []

    async with aiohttp.ClientSession() as session:
        for link in coursefolder_links:
            try:
                async with session.get(link, timeout=10) as resp:
                    html = await resp.text()
                    matches = re.findall(r"https?://(?:www\.)?udemy\.com/course/[^\s\"'>]+", html)
                    udemy_links.extend(matches)
            except Exception as e:
                print(f"⚠️ Error fetching {link}: {e}")

    print(f"🎯 Extracted {len(udemy_links)} Udemy course links.")
    return udemy_links


# ---------- Email/Output ----------
def save_to_file(links):
    if not links:
        print("📭 No new links found today.")
        return
    filename = f"udemy_links_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(links))
    print(f"📝 Saved extracted links to {filename}")


# ---------- Main ----------
async def main():
    coursefolder_links = await get_coursefolder_links_from_telegram()
    if not coursefolder_links:
        print("No new Coursefolder links found.")
        return
    udemy_links = await extract_udemy_links(coursefolder_links)
    save_to_file(udemy_links)


if __name__ == "__main__":
    asyncio.run(main())
