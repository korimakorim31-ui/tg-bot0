"""
Quantum Alpha AI — Telegram Bot
================================

Pushes CEO-approved signals to a Telegram chat/channel, plus basic commands
for status checks and manual demo runs.

ENV VARS REQUIRED (set these in Railway's Variables tab, never commit them):
    TELEGRAM_BOT_TOKEN   - from @BotFather
    TELEGRAM_CHAT_ID     - the chat/channel/group to post signals into
    CHECK_INTERVAL_SEC   - optional, default 60 (matches spec's "run every 1 minute")

Deployment model: this runs as a Railway *worker* using long-polling
(Application.run_polling()). No public port/webhook needed.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Make the core CEO/signal modules importable regardless of run cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ceo_agent import CEOAgent, RiskLevel  # noqa: E402
from signal_output import calculate_risk_plan, format_signal  # noqa: E402
from example_run import strong_bullish_reports, weak_conflicting_reports  # noqa: E402
from ceo_agent import TradeSetup  # noqa: E402

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("quantum_alpha_bot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
CHECK_INTERVAL_SEC = int(os.environ.get("CHECK_INTERVAL_SEC", "60"))

if not BOT_TOKEN or not CHAT_ID:
    logger.error(
        "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. "
        "Set them in Railway's Variables tab (or a local .env for testing)."
    )
    sys.exit(1)

# Simple in-memory state so /latest has something to show.
_last_signal_text: str | None = None


# --------------------------------------------------------------------------
# Signal generation hook
# --------------------------------------------------------------------------
# THIS IS THE PLUG POINT. Right now it alternates between the two demo
# scenarios so you can see the bot work end-to-end. Replace this function's
# body with your real pipeline once the 10 live agents are wired to Bitget +
# your LLM: pull fresh candles/order book/etc, build 10 AgentReports, build a
# TradeSetup from current price action, then call ceo.evaluate() as below.

_demo_toggle = {"n": 0}


def generate_signal_text() -> str:
    ceo = CEOAgent()
    _demo_toggle["n"] += 1

    if _demo_toggle["n"] % 2 == 1:
        setup = TradeSetup(
            coin="BTCUSDT", exchange="Bitget",
            entry_low=64200, entry_high=64400, stop_loss=63500,
            take_profits=[66900, 68000, 69200, 70500],
            leverage=5, risk_pct=2,
        )
        reports = strong_bullish_reports()
        decision = ceo.evaluate(reports, setup, news_risk=RiskLevel.LOW)
        risk_plan = None
        if decision.approved:
            risk_plan = calculate_risk_plan(setup, decision.direction, 10_000, 0.90)
        return format_signal(decision, setup, risk_plan, probability_pct=96.0)
    else:
        setup = TradeSetup(
            coin="ETHUSDT", exchange="Bitget",
            entry_low=3400, entry_high=3420, stop_loss=3350,
            take_profits=[3480], leverage=10, risk_pct=2,
        )
        reports = weak_conflicting_reports()
        decision = ceo.evaluate(reports, setup, news_risk=RiskLevel.MEDIUM)
        return format_signal(decision, setup)


# --------------------------------------------------------------------------
# Telegram command handlers
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Quantum Alpha AI online.\n\n"
        "/status - check the bot is alive\n"
        "/demo - manually trigger a CEO evaluation\n"
        "/latest - show the last signal generated\n"
        f"Auto-checking every {CHECK_INTERVAL_SEC}s."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running.")


async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _last_signal_text
    text = generate_signal_text()
    _last_signal_text = text
    await update.message.reply_text(text)


async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(_last_signal_text or "No signal generated yet. Try /demo.")


# --------------------------------------------------------------------------
# Scheduled job — matches spec's "run every 1 minute, monitor continuously"
# --------------------------------------------------------------------------

async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    global _last_signal_text
    text = generate_signal_text()
    _last_signal_text = text

    # Only push APPROVED signals to the channel automatically.
    # Rejections are logged but not spammed to the chat, per spec ("quality
    # over quantity" — don't notify on every non-event).
    if "APPROVED" in text:
        await context.bot.send_message(chat_id=CHAT_ID, text=text)
        logger.info("Sent approved signal to chat %s", CHAT_ID)
    else:
        logger.info("No trade this cycle — not sent (rejections stay silent).")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(CommandHandler("latest", latest))

    app.job_queue.run_repeating(scheduled_check, interval=CHECK_INTERVAL_SEC, first=10)

    logger.info("Starting bot with polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
