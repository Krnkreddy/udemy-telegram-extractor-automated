# 📚 Udemy Telegram Course Extractor (Automated)

Automates extraction of free Udemy course links from Telegram groups, scraping coursefolder.net pages, and sending results via Telegram bot.

---

## ⚙️ Project Status

> **Currently On Hold** ⏸️
> The project is paused but will be resumed later. Contributions and improvements are welcome.

---

## 📂 Folder Structure

```
udemy-telegram-extractor-automated/
│
├── .github/workflows/daily.yml   # GitHub Actions workflow
├── main.py                       # Main automation script
├── requirements.txt              # Python dependencies
├── udemy_seen_ids.json           # Seen Telegram message IDs
└── udemy_links.txt               # Extracted Udemy course links
```

---

## 📝 How It Works

1. Connects to a Telegram group/channel using **Telethon**.
2. Scans messages for `coursefolder.net` links.
3. Visits each link using **Playwright** and extracts Udemy course URLs.
4. Sends the extracted links to a Telegram bot.
5. Keeps track of previously seen Telegram messages to avoid duplicates.

---

## ⚠️ Errors & Troubleshooting

For all common errors, such as JSON issues, CAPTCHA, or Telegram connection problems, please refer to the **Errors section** in this repository.

---

## 🌐 Contributions

* Open to all **developers and contributors**.
* Feel free to fork, submit pull requests, or suggest improvements.
* If adding new features, please maintain compatibility with **GitHub Actions workflow**.

---

## 📅 GitHub Actions

* Daily run of the script via `daily.yml`.
* Automatically extracts new courses and sends notifications to Telegram.
* Ensures `udemy_seen_ids.json` exists and remains valid.

---

## 🛠️ Tech Stack

* **Python** 3.11
* **Telethon** — Telegram client
* **Playwright** — Browser automation
* **Requests** — Telegram bot notifications
* **GitHub Actions** — Daily scheduled execution

---

## Contact

**K Ranga Nitheesh Kumar Reddy**

* Email: [k.r.nitheeshkumarreddy@gmail.com](mailto:k.r.nitheeshkumarreddy@gmail.com)
* LinkedIn: [linkedin.com/in/KrnkReddy](https://www.linkedin.com/in/krnkreddy/)
* GitHub: [github.com/Krnkreddy](https://github.com/Krnkreddy)

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
