# Udemy Telegram Extractor Automated

This project automatically:
1. Reads Telegram messages from a group/channel.
2. Extracts Coursefolder links.
3. Visits each link to extract Udemy course URLs.
4. Sends the daily list to your Telegram chat using a bot.

## Setup
1. Add secrets under **Settings → Secrets → Actions**:
   - `TG_API_ID`
   - `TG_API_HASH`
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `TELETHON_STRING_SESSION`
2. The workflow runs automatically every day at 08:30 AM IST (03:00 UTC).
3. You can also manually trigger it under the **Actions** tab.

## Run locally
```bash
pip install -r requirements.txt
playwright install chromium
python main.py