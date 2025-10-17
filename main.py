import asyncio
import json
import os
from playwright.async_api import async_playwright
from telethon import TelegramClient
from telethon.tl.types import MessageEntityUrl
import requests

# === TELEGRAM SETTINGS ===
api_id = int(os.getenv("TG_API_ID", "26972239"))  # From environment
api_hash = os.getenv("TG_API_HASH", "fa03ac53e4eacbf1c845e55bf7de09df")
group_username = '@getstudyfevers'  # Target Telegram group/channel
notify_token = os.getenv("TELEGRAM_TOKEN")        # Bot token for sending output
notify_chat_id = os.getenv("TELEGRAM_CHAT_ID")    # Chat ID to receive output

# === SEEN IDS FILE ===
SEEN_IDS_FILE = "udemy_seen_ids.json"

def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE): 
        with open(SEEN_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_ids(seen_ids):
    with open(SEEN_IDS_FILE, 'w') as f:
        json.dump(list(seen_ids), f)

# === UDEMY LINK EXTRACTOR ===
async def extract_udemy_links_from_coursefolder(playwright, coursefolder_links):
    browser = await playwright.chromium.launch(headless=True)   
    context = await browser.new_context()
    page = await context.new_page()

    udemy_links = []

    for link in coursefolder_links:
        print(f"🌐 Visiting: {link}")
        try:
            await page.goto(link, timeout=0)
            if "captcha" in page.url.lower():
                print(f"🤖 CAPTCHA detected. Skipping: {link}")
                continue
            await page.wait_for_selector("a[href^='https://www.udemy.com/course/']", timeout=10000)
            anchor = await page.query_selector("a[href^='https://www.udemy.com/course/']")
            udemy_url = await anchor.get_attribute('href')
            if udemy_url:
                print(f"✅ Udemy URL found: {udemy_url}")
                udemy_links.append(udemy_url)
        except Exception as e:
            print(f"❗ Error visiting {link}: {e}")

    await browser.close()
    return udemy_links

# === TELEGRAM SCRAPER ===
async def get_coursefolder_links_from_telegram():
    print("📥 Connecting to Telegram...")
    client = TelegramClient('session_name', api_id, api_hash)
    await client.start()

    seen_ids = load_seen_ids()
    new_seen_ids = set()
    course_links = []

    async for msg in client.iter_messages(group_username, limit=500):
        if msg.id in seen_ids:
            continue

        new_seen_ids.add(msg.id)

        if msg.entities:
            for entity in msg.entities:
                if isinstance(entity, MessageEntityUrl):
                    url = msg.message[entity.offset:entity.offset + entity.length]
                    if "coursefolder.net" in url:
                        print(f"✅ Found course URL: {url}")
                        course_links.append(url)

    await client.disconnect()
    save_seen_ids(seen_ids.union(new_seen_ids))
    return course_links

# === TELEGRAM BOT SENDER ===
def send_telegram_message(text: str):
    if not notify_token or not notify_chat_id:
        print("⚠️ Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID — skipping send.")
        return
    url = f"https://api.telegram.org/bot{notify_token}/sendMessage"
    data = {"chat_id": notify_chat_id, "text": text, "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=data)
        r.raise_for_status()
        print("✅ Sent message via Telegram.")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")

# === MAIN ===
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

        print("\n🎯 Final Udemy Course Links:")
        message = "\n".join(udemy_links)
        print(message)

        # Save to file for reference
        with open("udemy_links.txt", "w", encoding="utf-8") as f:
            for url in udemy_links:
                f.write(url + "\n")

        # Send message via Telegram bot
        send_telegram_message(f"🎓 **Today's Udemy Courses** 🎓\n\n{message}")

if __name__ == "__main__":
    asyncio.run(main())
