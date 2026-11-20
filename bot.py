import asyncio
import os
import io
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from database import init_db, add_user, is_user_authorized, save_message, save_record, update_outcome, get_user_history

load_dotenv()
init_db()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

ADMIN_USER_ID = 9101622037

user_sessions = {}

SYSTEM_PROMPT = """
You are MATT — McLink Assistant Troubleshooter for Technician.
Your role: Senior Photocopier Service Technician Assistant.

LANGUAGE RULES — STRICT:
- If the user speaks in ENGLISH → Respond in ENGLISH only.
- If the user speaks in TAGALOG → Respond in SIMPLE TAGLISH. Do NOT use deep or formal Tagalog. Keep it natural and easy to read. Example: "Check mo muna yung power cable baka kasi hindi nakasaksak properly."
- If unsure which language → Default to ENGLISH.

CORE INSTRUCTIONS:
1. When user sends a photo of test page or error display: Analyze it, then ASK for the MACHINE MODEL clearly. NEVER give troubleshooting steps without knowing the model first.
2. Once model is known — provide DETAILED step-by-step troubleshooting including:
   - Which part may be faulty
   - How to remove covers/screws — be specific
   - How to test if a part is working or faulty
   - Safety notes
3. If first solution doesn't work — provide 3 to 4 ALTERNATIVE methods, not just one
4. Be specific about part names, error codes, and blinking light patterns
5. At the end of each troubleshooting session ASK: "✅ Did this fix the machine? Reply with: YES + what worked / NO + what happened instead"
6. Remember conversation context so you can follow up correctly
7. Keep tone friendly, professional, and direct — like an experienced senior technician helping a colleague

IMPORTANT RULES:
- NEVER guess the machine model — always ask if unclear
- NEVER invent service procedures — if unsure, say: "I don't have the exact service steps for that model, please refer to the official service manual"
- Be thorough — technicians need complete repair information, not just basic advice
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name or "Technician"
    
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            f"👋 Hi there! I'm MATT — McLink Assistant Troubleshooter for Technician.\n\n"
            f"Hi {name}! It looks like your account hasn't been activated yet.\n"
            f"Please ask your administrator to grant you access.\n\n"
            f"Your Telegram ID: `{user_id}`",
            parse_mode='Markdown'
        )
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"📢 New access request:\nUser ID: `{user_id}`\nName: {name}\n\nAdd them to the database if approved.",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        f"👋 Hello {name}! I'm MATT — your McLink Assistant Troubleshooter.\n\n"
        f"I'm here to help you troubleshoot photocopier machines — step by step.\n\n"
        f"You can send me:\n"
        f"📸 A photo of a test page or error display\n"
        f"❓ Or describe your problem directly (e.g., 'Flashing red light on MP C3054')\n\n"
        f"How can I help you today?"
    )
    save_message(user_id, "/start", 1)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📖 How to use MATT:

1️⃣ Ask directly:
> "Flashing red light MP C3054"

2️⃣ Send a photo:
> Send a picture of the test page or error code
> I'll ask for the machine model first, then guide you step-by-step

3️⃣ If the first solution doesn't work:
> Just say "still not working" — I'll give you other options

4️⃣ After troubleshooting:
> Let me know if it worked! Your feedback helps other technicians too.
"""
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("⚠️ Your account is not active yet. Please wait for approval from your administrator.")
        return
    
    save_message(user_id, user_message, 1)
    
    if user_sessions.get(user_id, {}).get('awaiting_feedback'):
        await process_feedback(update, context, user_id, user_message)
        return
    
    history = get_user_history(user_id, 8)
    conversation_context = ""
    for msg, is_from_user, time in reversed(history):
        role = "Technician" if is_from_user else "MATT"
        conversation_context += f"{role}: {msg}\n"
    
    full_prompt = f"""{SYSTEM_PROMPT}

Previous conversation:
{conversation_context}

Technician: {user_message}
"""
    
    response = model.generate_content(full_prompt)
    bot_reply = response.text
    
    if "did this fix" in bot_reply.lower():
        user_sessions[user_id] = user_sessions.get(user_id, {})
        user_sessions[user_id]['awaiting_feedback'] = True
        user_sessions[user_id]['last_problem'] = user_message
        user_sessions[user_id]['last_solution'] = bot_reply
    
    save_message(user_id, bot_reply, 0)
    await update.message.reply_text(bot_reply)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_user_authorized(user_id):
        await update.message.reply_text("⚠️ Your account is not active yet. Please wait for approval from your administrator.")
        return
    
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    prompt = f"""{SYSTEM_PROMPT}
    
I have received an image — please examine it. If you can see an error code or test page pattern, acknowledge it and ASK CLEARLY: "What is the exact model number of this machine?" Do NOT provide troubleshooting steps until the model is confirmed.
"""
    
    response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": photo_bytes}])
    bot_reply = response.text
    
    save_message(user_id, "[Sent a photo]", 1)
    save_message(user_id, bot_reply, 0)
    
    await update.message.reply_text(bot_reply)

async def process_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, feedback_text):
    user_sessions[user_id]['awaiting_feedback'] = False
    
    is_fixed = any(word in feedback_text.lower() for word in ['yes', 'yep', 'fixed', 'working', 'it worked', 'oo', 'opo', 'naayos', 'ayos'])
    is_not_fixed = any(word in feedback_text.lower() for word in ['no', 'nope', 'not working', 'still same', 'hindi', 'hindi po', 'hindi naayos'])
    
    if is_fixed:
        outcome = "FIXED"
        notes = feedback_text
        reply = "🎉 Great news! I've recorded the solution — it will help other technicians too. You got this! Let me know if you need help with anything else. 😊"
    elif is_not_fixed:
        outcome = "NOT FIXED"
        notes = feedback_text
        reply = "✅ Noted. I'll prepare alternative solutions for you next time. Don't hesitate to reach out again — we'll get it sorted out!"
    else:
        outcome = "PARTIAL"
        notes = feedback_text
        reply = "✅ Thanks for the update — I've noted it down. Let me know how else I can help!"
    
    last_problem = user_sessions[user_id].get('last_problem', 'Unknown')
    last_solution = user_sessions[user_id].get('last_solution', 'Unknown')
    record_id = save_record(user_id, "Not specified", last_problem, last_solution, "completed")
    update_outcome(record_id, outcome, notes)
    
    save_message(user_id, f"[Feedback: {outcome}] {notes}", 1)
    await update.message.reply_text(reply)

import asyncio

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
    asyncio.run(main())


