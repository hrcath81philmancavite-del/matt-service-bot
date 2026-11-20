import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)
from google import genai

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Configure NEW Gen AI SDK
client = genai.Client(api_key=GEMINI_API_KEY)

user_sessions = {}

SYSTEM_PROMPT = """
You are MATT — McLink Assistant for Technician Troubleshooting.
You are an expert on photocopier and printer repair, specifically Ricoh, Xerox, Canon, HP models.

RULES:
1. Speak in Taglish — friendly, direct, easy to understand.
2. When a technician sends a test page photo — ask first: "Anong model ng machine ito?"
3. When describing steps — be thorough: include disassembly, part testing, replacement, reassembly.
4. Use clear numbered steps. Be professional but not too technical — you are talking to experienced technicians.
5. If unsure — be honest: "Hindi ako 100% sure dito, pero ito ang common na solusyon..."
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"last_problem": None, "last_model": None}
    await update.message.reply_text(
        "👋 Hello! Ako si **MATT** — McLink Assistant for Technician Troubleshooting.\n\n"
        "Send mo lang:\n"
        "📸 Picture ng test page o problema\n"
        "💬 O kaya itanong mo — hal. 'Blinking red light ang power button ng MPC3054'\n\n"
        "Handang tumulong sa troubleshooting! 😊"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Paano gamitin si MATT:\n\n"
        "1️⃣ Send ng picture ng test page o error code\n"
        "2️⃣ Sabihin kung anong model ng machine\n"
        "3️⃣ Hintayin ang step-by-step na solusyon\n\n"
        "Kung may kulang — magtanong ka lang ulit! 😊"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    session = user_sessions.get(user_id, {})
    context_prompt = f"""
    {SYSTEM_PROMPT}
    
    Previous issue: {session.get('last_problem', 'None')}
    Machine model: {session.get('last_model', 'Not specified')}
    Technician: {user_message}
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=context_prompt
    )
    reply = response.text

    user_sessions[user_id] = {
        "last_problem": user_message,
        "last_model": session.get("last_model", "Not specified")
    }

    await update.message.reply_text(reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Nakuha ko ang litrato! Salamat po.\n\n"
        "**Anong model ng machine ito?** Para mas accurate ang maibigay kong troubleshooting steps. 😊"
    )

async def main():
    print("🔄 Starting MATT — McLink Assistant Troubleshooter...")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ MATT is online and ready!")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
