"""
JARVIS v1 — Telegram Bot
Keys loaded from environment variables — never hardcoded
"""

import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from groq import Groq

# CONFIG — loaded from environment
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")
MEMORY_FILE    = "jarvis_memory.json"
YOUR_NAME      = "Vidcrew"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

groq_client = Groq(api_key=GROQ_API_KEY)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"bullets": [], "last_updated": ""}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def memory_to_text(memory):
    if not memory["bullets"]:
        return "No memory yet."
    return "\n".join(f"- {b}" for b in memory["bullets"])

def update_memory(memory, summary):
    try:
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "Extract 1-3 key facts from this conversation. Short bullet points only. No dashes."},
                {"role": "user", "content": summary}
            ],
            max_tokens=200
        )
        facts = [f.strip() for f in response.choices[0].message.content.strip().split("\n") if f.strip()]
        memory["bullets"].extend(facts)
        if len(memory["bullets"]) > 30:
            memory["bullets"] = memory["bullets"][-30:]
        memory["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_memory(memory)
    except Exception as e:
        logger.error(f"Memory update failed: {e}")

def build_system_prompt(memory):
    return f"""You are Jarvis, personal AI for {YOUR_NAME}.
Be direct, honest, like a trusted friend. No filler.
{YOUR_NAME} is an 18yo solo developer in India. Runs Vidcrew agency. Building you.
Memory: {memory_to_text(memory)}
Today: {datetime.now().strftime("%B %d, %Y")}. Keep replies short — mobile chat."""

def get_history(context):
    if "history" not in context.user_data:
        context.user_data["history"] = []
    return context.user_data["history"]

def add_to_history(context, role, content):
    history = get_history(context)
    history.append({"role": role, "content": content})
    if len(history) > 20:
        context.user_data["history"] = history[-20:]

def ask_groq(user_message, context):
    memory = load_memory()
    messages = [{"role": "system", "content": build_system_prompt(memory)}]
    messages.extend(get_history(context))
    messages.append({"role": "user", "content": user_message})
    response = groq_client.chat.completions.create(model="llama3-70b-8192", messages=messages, max_tokens=800, temperature=0.7)
    reply = response.choices[0].message.content.strip()
    add_to_history(context, "user", user_message)
    add_to_history(context, "assistant", reply)
    return reply, memory

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Jarvis online. What do you need, {YOUR_NAME}?")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if not user_message: return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        reply, memory = ask_groq(user_message, context)
        await update.message.reply_text(reply)
        history = get_history(context)
        if len(history) % 10 == 0 and len(history) > 0:
            summary = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-10:])
            update_memory(memory, summary)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("Something went wrong. Try again.")

async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("Conversation cleared. Memory intact.")

async def memory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = load_memory()
    await update.message.reply_text(f"Memory:\n\n{memory_to_text(memory)}\n\nUpdated: {memory.get('last_updated','never')}")

async def forget_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_memory({"bullets": [], "last_updated": ""})
    await update.message.reply_text("Memory wiped.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("memory", memory_handler))
    app.add_handler(CommandHandler("forget", forget_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("Jarvis v1 online.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
