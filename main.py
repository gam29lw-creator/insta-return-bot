
import asyncio
import json
import os
import time
import aiohttp

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "accounts.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(accounts, f)

accounts = load_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في InstaReturn Monitor 📡\n\n"
        "/add username - إضافة حساب\n"
        "/list - الحسابات المراقبة\n"
        "/remove username - حذف حساب"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "اكتب: /add username"
        )

    username = context.args[0].replace("@", "").lower()
    key = f"{update.effective_chat.id}:{username}"

    accounts[key] = {
        "username": username,
        "chat_id": update.effective_chat.id,
        "started": time.time(),
        "notified": False
    }

    save_data()

    await update.message.reply_text(
        f"تمت إضافة @{username} للمراقبة 📡\n"
        "بدأ حساب الوقت."
    )

async def listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = [
        item for item in accounts.values()
        if item["chat_id"] == chat_id
    ]

    if not items:
        return await update.message.reply_text(
            "ماكو حسابات تحت المراقبة."
        )

    message = "الحسابات المراقبة:\n\n"

    for item in items:
        elapsed = int(time.time() - item["started"])
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        message += (
            f"@{item['username']}\n"
            f"TAT: {hours}h {minutes}m {seconds}s\n\n"
        )

    await update.message.reply_text(message)

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "اكتب: /remove username"
        )

    username = context.args[0].replace("@", "").lower()
    key = f"{update.effective_chat.id}:{username}"

    if key in accounts:
        del accounts[key]
        save_data()
        await update.message.reply_text("تم حذف الحساب.")
    else:
        await update.message.reply_text("الحساب غير موجود.")

async def monitor(app):
    while True:
        async with aiohttp.ClientSession() as session:
            for key, item in list(accounts.items()):
                if item["notified"]:
                    continue

                username = item["username"]
                url = f"https://www.instagram.com/{username}/"

                try:
                    async with session.get(
                        url,
                        timeout=15,
                        headers={
                            "User-Agent": "Mozilla/5.0"
                        }
                    ) as response:
                        page = await response.text()

                        # فحص أولي فقط، وليس إثباتاً للتنشيط
                        active = (
                            response.status == 200
                            and f'"{username}"' in page.lower()
                            and "sorry, this page isn't available" not in page.lower()
                        )

                        if active:
                            elapsed = int(time.time() - item["started"])
                            h = elapsed // 3600
                            m = (elapsed % 3600) // 60
                            s = elapsed % 60

                            await app.bot.send_message(
                                chat_id=item["chat_id"],
                                text=(
                                    f"You can use @{username} again\n"
                                    f"TAT: {h}h {m}m {s}s\n"
                                    f"By: InstaReturn Bot"
                                )
                            )

                            item["notified"] = True
                            save_data()

                except Exception:
                    pass

        await asyncio.sleep(300)

async def post_init(app):
    app.create_task(monitor(app))

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", listing))
    app.add_handler(CommandHandler("remove", remove))

    app.run_polling()

if __name__ == "__main__":
    main()
