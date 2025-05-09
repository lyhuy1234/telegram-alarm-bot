import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

# Replace with your actual bot token
BOT_TOKEN = "8199451491:AAEqrV3aj_6JbdYEf5Sbl8lVbso_T4JPN9I"

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store alarms: {chat_id: [(time_str, job)]}
alarms = {}
# Store opted-in users: {chat_id: set(user_ids)}
listeners = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /set HH:MM to set alarm, /stop HH:MM to stop, /listen to receive alarms, /mute to stop receiving.")

async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /set HH:MM")
        return
    time_str = context.args[0]
    try:
        target_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        alarm_datetime = datetime.combine(now.date(), target_time)
        if alarm_datetime < now:
            alarm_datetime += timedelta(days=1)
        delay = (alarm_datetime - now).total_seconds()

        job = asyncio.create_task(schedule_alarm(context, chat_id, time_str, delay))
        alarms.setdefault(chat_id, []).append((time_str, job))

        await update.message.reply_text(f"Alarm set for {time_str}")
    except ValueError:
        await update.message.reply_text("Invalid time format. Use HH:MM")

async def schedule_alarm(context: ContextTypes.DEFAULT_TYPE, chat_id, time_str, delay):
    await asyncio.sleep(delay)
    user_ids = listeners.get(chat_id, set())
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, f"⏰ Alarm for {time_str}!")
        except Exception as e:
            logger.warning(f"Failed to send to {uid}: {e}")

async def stop_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /stop HH:MM")
        return
    time_str = context.args[0]
    if chat_id in alarms:
        for t, job in alarms[chat_id]:
            if t == time_str:
                job.cancel()
        alarms[chat_id] = [pair for pair in alarms[chat_id] if pair[0] != time_str]
        await update.message.reply_text(f"Alarm for {time_str} stopped.")
    else:
        await update.message.reply_text("No alarms found.")

async def listen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    listeners.setdefault(chat_id, set()).add(user_id)
    await update.message.reply_text("You will now receive alarms in this group.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id in listeners:
        listeners[chat_id].discard(user_id)
    await update.message.reply_text("You will no longer receive alarms in this group.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_alarm))
    app.add_handler(CommandHandler("stop", stop_alarm))
    app.add_handler(CommandHandler("listen", listen))
    app.add_handler(CommandHandler("mute", mute))

    print("Bot running...")
    app.run_polling()import logging
import asyncio
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Global storage
alarms = {}  # chat_id: [(datetime, set(user_ids))]
subscribed_users = {}  # chat_id: set(user_ids)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Alarm Bot!\n"
        "Use /set HH:MM to set alarm.\n"
        "Use /listen to receive alarms.\n"
        "Use /mute to stop receiving alarms.\n"
        "Use /stop to cancel all alarms in this group."
    )

# Set alarm
async def set_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        if len(context.args) != 1 or ":" not in context.args[0]:
            raise ValueError

        now = datetime.now()
        hour, minute = map(int, context.args[0].split(":"))
        alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if alarm_time <= now:
            alarm_time += timedelta(days=1)

        if chat_id not in alarms:
            alarms[chat_id] = []

        user_id = update.effective_user.id
        alarms[chat_id].append((alarm_time, set(subscribed_users.get(chat_id, set()))))
        await update.message.reply_text(f"Alarm set for {alarm_time.strftime('%H:%M')}.")

        asyncio.create_task(schedule_alarm(chat_id, alarm_time, context))

    except:
        await update.message.reply_text("Usage: /set HH:MM (24-hour format)")

# Listen (subscribe)
async def listen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in subscribed_users:
        subscribed_users[chat_id] = set()

    subscribed_users[chat_id].add(user_id)
    await update.message.reply_text("You're now subscribed to alarms in this group.")

# Mute (unsubscribe)
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id in subscribed_users and user_id in subscribed_users[chat_id]:
        subscribed_users[chat_id].remove(user_id)
        await update.message.reply_text("You won't receive alarms now.")
    else:
        await update.message.reply_text("You're not subscribed.")

# Stop all alarms
async def stop_alarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    alarms.pop(chat_id, None)
    await update.message.reply_text("All alarms stopped for this group.")

# Alarm trigger
async def schedule_alarm(chat_id, alarm_time, context):
    now = datetime.now()
    delay = (alarm_time - now).total_seconds()
    await asyncio.sleep(delay)

    user_ids = subscribed_users.get(chat_id, set())
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text="⏰ Alarm Time! Wake up!")
        except:
            pass

    await context.bot.send_message(chat_id=chat_id, text="⏰ Group Alarm Time!")

# Main function
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_alarm))
    app.add_handler(CommandHandler("listen", listen))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("stop", stop_alarm))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
