# Quantum Alpha AI — Telegram Bot (Railway Deployment)

## What this deploys

A long-running worker (no public port needed) that:
- Responds to `/start`, `/status`, `/demo`, `/latest` in Telegram
- Runs a check every `CHECK_INTERVAL_SEC` (default 60s) via the CEO gate
- Auto-posts to your chat **only** when a signal is APPROVED (rejections stay silent, per the "quality over quantity" rule)

Right now `generate_signal_text()` in `telegram_bot/bot.py` alternates between two demo scenarios (one approve, one reject) so you can see it work end-to-end. Swap that function's body for your real 10-agent pipeline once it's built — everything downstream (CEO gate, formatting, Telegram push) already works.

## 1. Create the bot with BotFather

1. Open Telegram, message **@BotFather**
2. `/newbot` → follow the prompts → copy the token it gives you (`TELEGRAM_BOT_TOKEN`)
3. Add the bot to the channel/group you want signals posted to, and give it permission to post
4. Get the chat ID:
   - For a private chat with the bot: message it once, then visit
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and read `"chat":{"id": ...}`
   - For a channel: use the channel's `@username`, or add [@userinfobot](https://t.me/userinfobot) temporarily to get the numeric ID (channel IDs start with `-100`)

## 2. Push this code to GitHub

Railway deploys from a GitHub repo (or the Railway CLI). Create a repo containing:

```
quantum_alpha/
├── ceo_agent.py
├── signal_output.py
├── example_run.py
├── requirements.txt
├── Procfile
├── railway.json
├── runtime.txt
├── .env.example
└── telegram_bot/
    ├── bot.py
    └── requirements.txt
```

```bash
cd quantum_alpha
git init
git add .
git commit -m "Quantum Alpha AI CEO gate + Telegram bot"
git branch -M main
git remote add origin https://github.com/<you>/quantum-alpha-ai.git
git push -u origin main
```

**Do not commit a `.env` file with real values.** `.env.example` is the template; real secrets go in Railway's dashboard (step 4).

## 3. Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repo. Railway will detect `requirements.txt` via Nixpacks and `railway.json` for the start command.
3. Under the service, confirm it deploys as a **worker** (not exposed to the web) — it doesn't need a public domain since it uses polling, not webhooks.

## 4. Set environment variables

In Railway → your service → **Variables** tab, add:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | the chat/channel ID from step 1 |
| `CHECK_INTERVAL_SEC` | `60` (or whatever cadence you want) |

Railway redeploys automatically when you save variables.

## 5. Verify

- Check the **Deploy Logs** for `Starting bot with polling...`
- Message your bot `/start` and `/status` in Telegram
- Message `/demo` to force an evaluation right now
- Within `CHECK_INTERVAL_SEC`, watch the configured chat for an auto-posted signal (it'll show up on the "strong bullish" demo cycle)

## Local testing before deploying

```bash
cd quantum_alpha
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real values
python telegram_bot/bot.py
```

## Notes / next steps

- **This bot doesn't talk to Bitget or NVIDIA NIM yet** — it's wired to the CEO decision logic with demo data. Once the 10 live agents are built, point `generate_signal_text()` at them instead of the demo functions.
- If you want it to also **place orders** (not just notify), that's a separate, higher-stakes piece — build and test in paper-trading mode first.
- Railway's free tier sleeps/limits differently than paid — check your plan if you want this running 24/7 unattended.
