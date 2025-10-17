# Udemy Telegram Extractor Automated

This project automatically:
1. Reads Telegram messages from a group/channel.
2. Extracts Coursefolder links.
3. Visits each link to extract Udemy course URLs.
4. Sends the daily list to your Telegram chat using a bot.

## Setup

1. Add secrets under **Settings → Secrets → Actions**:
   - `TG_API_ID` — Your Telegram API ID
   - `TG_API_HASH` — Your Telegram API hash
   - `TELEGRAM_TOKEN` — Your BotFather bot token
   - `TELEGRAM_CHAT_ID` — Chat ID to receive messages
   - `TELETHON_STRING_SESSION` — Your Telethon string session (generated locally)

2. The workflow runs automatically every day at 08:30 AM IST (03:00 UTC).

3. You can manually trigger the workflow from the **Actions** tab if needed.

## Run Locally

```bash
pip install -r requirements.txt
playwright install chromium
python main.py