# bot.py
import os
import logging
import asyncio
import openai

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIG (from Render environment variables) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")  # optional: your numeric Telegram id as string

# --- Basic checks ---
if not TELEGRAM_TOKEN:
    raise SystemExit("Missing TELEGRAM_TOKEN environment variable.")
if not OPENAI_API_KEY:
    # We allow running without OpenAI (bot will echo), but warn
    print("Warning: OPENAI_API_KEY not found. Bot will run in fallback mode.")
else:
    openai.api_key = OPENAI_API_KEY

# --- Persona ---
PERSONA = (
    "You are Kyo-chan, a bold, anime-style friendly assistant. "
    "Use confident energy, playful emojis, short lines, and call the user 'Senpai'."
)

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name if user else "Senpai"
    await update.message.reply_text(f"Konnichiwa {name}-senpai! 🌸 I'm Kyo-chan — your bold anime assistant!")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any message and I'll reply in bold + anime-style! Try: Hello Kyo-chan!")

async def _call_openai_chat(user_message: str) -> str:
    """Call OpenAI in a thread so we don't block the event loop."""
    if not OPENAI_API_KEY:
        return None

    def sync_call():
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PERSONA},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=450,
                temperature=0.8,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("OpenAI call failed")
            return None

    return await asyncio.to_thread(sync_call)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security: allow only your Telegram account if ALLOWED_USER_ID is set
    if ALLOWED_USER_ID:
        try:
            allowed_id = int(ALLOWED_USER_ID)
            if update.effective_user and update.effective_user.id != allowed_id:
                await update.message.reply_text("Sorry — this bot is private.")
                return
        except ValueError:
            # ignore invalid env var
            pass

    user_text = update.message.text.strip()
    if not user_text:
        return

    # Try OpenAI
    ai_reply = await _call_openai_chat(user_text)
    if ai_reply:
        await update.message.reply_text(ai_reply)
        return

    # Fallback (if no OpenAI key or failure)
    fallback = f"Senpai! You said: «{user_text}» — I got it! ✨ (Tip: add OPENAI_API_KEY for smarter replies.)"
    await update.message.reply_text(fallback)

# --- Main: build app and run polling (blocking) ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is starting with run_polling() ...")
    # run_polling() is the simple, recommended way to run the bot reliably
    app.run_polling()

if __name__ == "__main__":
    main()
