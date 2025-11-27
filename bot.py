# bot.py — updated to use the new OpenAI Python client (openai>=1.0.0)
import os
import logging
import asyncio
import traceback

# New client interface
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIG from environment ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")  # optional

# Basic checks
if not TELEGRAM_TOKEN:
    raise SystemExit("ERROR: TELEGRAM_TOKEN environment variable is missing.")

# Prepare OpenAI client if available
openai_client = None
if OPENAI_API_KEY and OpenAI:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized.")
    except Exception:
        openai_client = None
        logging.exception("Failed to initialize OpenAI client.")
else:
    if OPENAI_API_KEY and not OpenAI:
        logging.warning("OpenAI package not available in this environment.")
    else:
        logging.info("OPENAI_API_KEY not set; bot will run in fallback mode.")

# Persona
PERSONA = (
    "You are Kyo-chan, a bold, anime-style friendly assistant. "
    "Use confident energy, playful emojis, short lines, and call the user 'Senpai'."
)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Senpai"
    await update.message.reply_text(f"Konnichiwa {name}-senpai! 🌸 I'm Kyo-chan — your bold anime assistant!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a message and I'll reply! Use /start to begin.")

def _choose_model() -> str:
    # Use a broadly-available model; change if you have access to others
    return "gpt-3.5-turbo"

def _call_openai_sync(user_message: str) -> str | None:
    """
    Synchronous call using the new OpenAI client interface.
    This runs in a thread (so the event loop is not blocked).
    """
    if not openai_client:
        return None
    try:
        model = _choose_model()
        logger.info("Calling OpenAI chat completion with model %s", model)
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PERSONA},
                {"role": "user", "content": user_message},
            ],
            max_tokens=450,
            temperature=0.8,
        )
        # response.choices[0].message.content is the usual shape
        text = response.choices[0].message.content.strip()
        logger.info("OpenAI returned %d characters", len(text))
        return text
    except Exception:
        logger.exception("OpenAI call failed (see traceback)")
        return None

async def call_openai(user_message: str) -> str | None:
    return await asyncio.to_thread(_call_openai_sync, user_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Optional security: allow only your Telegram ID if ALLOWED_USER_ID is set
        if ALLOWED_USER_ID:
            try:
                allowed_id = int(ALLOWED_USER_ID)
                if update.effective_user and update.effective_user.id != allowed_id:
                    await update.message.reply_text("Sorry — this bot is private.")
                    return
            except ValueError:
                logger.warning("ALLOWED_USER_ID is not an integer: %s", ALLOWED_USER_ID)

        text = (update.message.text or "").strip()
        if not text:
            return

        # Try OpenAI
        ai_reply = await call_openai(text)
        if ai_reply:
            await update.message.reply_text(ai_reply)
            return

        # Fallback reply if AI unavailable
        fallback = f"Senpai! You said: «{text}» — I got it! ✨ (OpenAI unavailable or failed.)"
        await update.message.reply_text(fallback)
    except Exception:
        logger.error("Unhandled error in handle_message:\n%s", traceback.format_exc())
        try:
            await update.message.reply_text("Oops — something went wrong. Check logs.")
        except Exception:
            pass

def main():
    try:
        logger.info("Building Application (telegram bot)...")
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("Starting bot with run_polling()")
        app.run_polling()
    except Exception:
        logger.critical("Fatal error in main:\n%s", traceback.format_exc())
        raise

if __name__ == "__main__":
    main()
