# test.py (improved timeouts + retries to avoid "Future exception was never retrieved")
import asyncio, json, os, re, time
from urllib.parse import urlparse
from telethon import TelegramClient
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

api_id = 26972239
api_hash = "fa03ac53e4eacbf1c845e55bf7de09df"
group_username = "@getstudyfevers"

SEEN_IDS_FILE = "udemy_seen_ids.json"
OUTPUT_FILE = "udemy_links.txt"
URL_RE = re.compile(r"https?://[^\s\)\]\}\<\"']+", flags=re.IGNORECASE)

def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(ids):
    with open(SEEN_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f)

def clean_url(u: str) -> str:
    return u.strip().rstrip(').,">\'\n\r ')

def is_udemy(u: str) -> bool:
    try:
        return "udemy.com" in urlparse(u).netloc.lower()
    except:
        return False

def extract_enroll_url(text: str):
    if not text:
        return None
    lower = text.lower()
    idx = lower.find("enroll")
    if idx != -1:
        after = text[idx:]
        m = URL_RE.search(after)
        if m:
            return clean_url(m.group(0))
    m2 = re.search(r"enroll\s*now[:\s]+\n*\s*(https?://[^\s\)]+)", text, flags=re.IGNORECASE)
    if m2:
        return clean_url(m2.group(1))
    return None

async def safe_sleep(backoff_s):
    await asyncio.sleep(backoff_s)

async def resolve_single(page, src_url,
                         nav_timeout=20000,
                         click_wait=15000,
                         max_retries=3):
    """Resolve a single coursetonight url -> udemy anchor with retries/fallbacks."""
    # small helper to scan page anchors for udemy links
    async def scan_for_udemy(p):
        try:
            anchors = await p.query_selector_all("a[href]")
            for a in anchors:
                try:
                    h = await a.get_attribute("href")
                    if h and is_udemy(h):
                        return clean_url(h)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            # open / navigate (try full load then DOMContent fallback)
            try:
                await page.goto(src_url, timeout=nav_timeout, wait_until="networkidle")
            except Exception:
                try:
                    await page.goto(src_url, timeout=nav_timeout, wait_until="domcontentloaded")
                except Exception as e:
                    last_exc = e
                    # navigation failed this attempt -> retry after backoff
                    await safe_sleep(0.5 * attempt)
                    continue

            # immediate checks
            if is_udemy(page.url):
                return clean_url(page.url)

            found = await scan_for_udemy(page)
            if found:
                return found

            # attempt clicking known button texts (with robust fallbacks)
            button_texts = [
                "Get Free Coupon","Get Coupon","Claim Coupon","Grab Coupon","Get Free Course",
                "Enroll Now","Get Free","Get It Free","Claim Now","Get Coupon Code","Enroll"
            ]
            for txt in button_texts:
                try:
                    loc = page.get_by_text(txt, exact=False)
                    if await loc.count() == 0:
                        continue
                    # Try expect_page first (new tab). If it times out, fallback to context.wait_for_event.
                    try:
                        with page.context.expect_page(timeout=click_wait) as new_page_info:
                            await loc.first.click(timeout=click_wait)
                        new_page = new_page_info.value
                        # Wait a bit for load; some pages redirect slowly.
                        try:
                            await new_page.wait_for_load_state("networkidle", timeout=nav_timeout)
                        except Exception:
                            pass
                        # scan new page
                        if is_udemy(new_page.url):
                            return clean_url(new_page.url)
                        f2 = await scan_for_udemy(new_page)
                        if f2:
                            return f2
                    except PWTimeoutError:
                        # fallback: maybe page changed same tab or JS redirect; click and wait
                        try:
                            await loc.first.click(timeout=click_wait)
                        except Exception:
                            pass
                        try:
                            await page.wait_for_load_state("networkidle", timeout=nav_timeout)
                        except Exception:
                            pass
                        f3 = await scan_for_udemy(page)
                        if f3:
                            return f3
                        # final fallback: wait for any new page event that may appear after a delay
                        try:
                            new_page = await page.context.wait_for_event("page", timeout=click_wait)
                            try:
                                await new_page.wait_for_load_state("networkidle", timeout=nav_timeout)
                            except Exception:
                                pass
                            if is_udemy(new_page.url):
                                return clean_url(new_page.url)
                            f4 = await scan_for_udemy(new_page)
                            if f4:
                                return f4
                        except PWTimeoutError:
                            pass
                    except Exception:
                        # ignore and continue scanning other buttons
                        continue
                except Exception:
                    continue

            # last-ditch: scan meta refresh or scripts for udemy links
            try:
                content = await page.content()
                m = re.search(r"https?://www\.udemy\.com[^\s'\"<>]+", content)
                if m:
                    return clean_url(m.group(0))
            except Exception:
                pass

            # nothing found this attempt -> backoff & retry
            await safe_sleep(0.8 * attempt)
        except Exception as e:
            last_exc = e
            await safe_sleep(0.8 * attempt)
            continue

    # after retries
    if last_exc:
        print(f"❌ Could not resolve Udemy for {src_url} (last error: {repr(last_exc)})")
    else:
        print(f"❌ Could not resolve Udemy for {src_url}")
    return None

async def resolve_enroll_urls(enroll_urls, headless=True):
    results = []
    if not enroll_urls:
        return results
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = await browser.new_context()
        for src in enroll_urls:
            page = await context.new_page()
            print(f"🔎 Resolving: {src}")
            try:
                ud = await resolve_single(page, src,
                                          nav_timeout=20000,
                                          click_wait=15000,
                                          max_retries=3)
                if ud:
                    print(f"✅ Found Udemy anchor: {ud}")
                    results.append(ud)
                else:
                    print(f"❌ Could not resolve Udemy for {src}")
            except Exception as e:
                print(f"❗ Error resolving {src}: {e}")
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
        try:
            await context.close()
        except Exception:
            pass
        await browser.close()
    # dedupe preserve order
    out = []
    for u in results:
        if u not in out:
            out.append(u)
    return out

async def main(limit=800, headless=True):
    print("📥 Connecting to Telegram and resolving Enroll Now links...")
    client = TelegramClient("session_name", api_id, api_hash)
    await client.start()
    seen = load_seen_ids()
    new_seen = set()
    enrolls = []

    async for msg in client.iter_messages(group_username, limit=limit):
        if msg.id in seen:
            continue
        new_seen.add(msg.id)
        text = getattr(msg, "raw_text", None) or getattr(msg, "message", "") or ""
        if not text:
            continue
        enroll = extract_enroll_url(text)
        if enroll:
            print(f"➡ Enroll extracted (msg {msg.id}): {enroll}")
            enrolls.append(enroll)

    save_seen_ids(seen.union(new_seen))
    await client.disconnect()

    if not enrolls:
        print("🚫 No Enroll Now links found.")
        return

    # dedupe enrolls
    seen_local = set()
    enrolls = [u for u in enrolls if not (u in seen_local or seen_local.add(u))]

    udemy_links = await resolve_enroll_urls(enrolls, headless=headless)

    if not udemy_links:
        print("🚫 No Udemy links extracted.")
        return

    print("\n🎯 Final Udemy links:")
    for u in udemy_links:
        print(u)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for u in udemy_links:
            f.write(u + "\n")
    print(f"\n💾 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main(limit=500, headless=True))





'''
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
