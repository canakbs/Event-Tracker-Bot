# Event Tracking Bot

A **Python bot** that sends **Telegram notifications** about upcoming **technical events**. It runs **automatically on a schedule** using **GitHub Actions** — no server or manual intervention needed.

---

## ⚙️ How It Works

1. **GitHub Actions** triggers the workflow on a schedule (cron).
2. The **Python script** fetches the latest tech events from its data source.
3. The bot sends a formatted **Telegram message** with the event details.

---

## 🛠️ Tech Stack

* **Python** — bot logic and message formatting
* **Telegram Bot API** — sending notifications
* **GitHub Actions** — scheduled, serverless automation

---

## 🚀 Setup

1. Create a Telegram bot via **@BotFather** and get the **bot token**.
2. Get your **chat ID** (e.g. via @userinfobot).
3. Add both as **repository secrets**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Adjust the **cron schedule** in `.github/workflows/` if needed.
5. The workflow will run automatically and send event notifications to your Telegram.

---

## 📁 Project Structure

- `main.py` — main bot script (fetches events, formats and sends the Telegram message)
- `requirements.txt` — Python dependencies
- `.github/workflows/` — GitHub Actions workflow (scheduled trigger)
