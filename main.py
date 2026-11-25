
import os
import re
import asyncio
import aiohttp

BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SUPABASE_API = f"{SUPABASE_URL}/rest/v1"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

async def request(session, method, url, **kwargs):
    headers = kwargs.pop("headers", {})

    if url.startswith(SUPABASE_API):
        headers = {**HEADERS, **headers}

    async with session.request(
        method,
        url,
        headers=headers or None,
        **kwargs
    ) as response:
        data = await response.json(content_type=None)

        if response.status >= 400:
            raise RuntimeError(
                f"HTTP {response.status}: {data}"
            )

        return data


async def send_message(session, chat_id, message):
    await request(
        session,
        "POST",
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message
        }
    )


async def get_offset(session):
    rows = await request(
        session,
        "GET",
        f"{SUPABASE_API}/bot_state",
        params={
            "id": "eq.1",
            "select": "telegram_offset"
        }
    )

    if not rows:
        raise RuntimeError("bot_state row 1 is missing")

    return int(rows[0]["telegram_offset"])


async def save_offset(session, offset):
    await request(
        session,
        "PATCH",
        f"{SUPABASE_API}/bot_state",
        params={"id": "eq.1"},
        json={"telegram_offset": offset},
        headers={"Prefer": "return=minimal"}
    )


async def handle_message(session, message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        return

    parts = text.split()
    command = parts[0].split("@")[0].lower()

    if command in ("/start", "/help"):
        await send_message(
            session,
            chat_id,
            "أهلاً بيك في InstaReturn Monitor\n\n"
            "الأوامر المتاحة:\n"
            "/add username - إضافة حساب\n"
            "/list - عرض الحسابات\n"
            "/remove username - حذف حساب\n"
            "/help - المساعدة"
        )
        return

    if command == "/add":
        if len(parts) != 2:
            await send_message(
                session,
                chat_id,
                "اكتب الأمر هكذا:\n/add username"
            )
            return

        username = parts[1].lstrip("@").lower()

        if not re.fullmatch(r"[a-zA-Z0-9._]{1,30}", username):
            await send_message(
                session,
                chat_id,
                "اسم المستخدم غير صالح."
            )
            return

        existing = await request(
            session,
            "GET",
            f"{SUPABASE_API}/monitored_accounts",
            params={
                "username": f"eq.{username}",
                "chat_id": f"eq.{chat_id}",
                "select": "id"
            }
        )

        if existing:
            await send_message(
                session,
                chat_id,
                f"الحساب @{username} مضاف مسبقاً."
            )
            return

        await request(
            session,
            "POST",
            f"{SUPABASE_API}/monitored_accounts",
            json={
                "username": username,
                "chat_id": chat_id
            },
            headers={"Prefer": "return=minimal"}
        )

        await send_message(
            session,
            chat_id,
            f"تمت إضافة @{username} إلى قائمة المتابعة."
        )
        return

    if command == "/list":
        accounts = await request(
            session,
            "GET",
            f"{SUPABASE_API}/monitored_accounts",
            params={
                "chat_id": f"eq.{chat_id}",
                "select": "username,status,started_at",
                "order": "created_at.desc"
            }
        )

        if not accounts:
            await send_message(
                session,
                chat_id,
                "ما عندك حسابات مضافة حالياً."
            )
            return

        lines = ["الحسابات المضافة:"]

        for account in accounts:
            lines.append(
                f"@{account['username']} — {account['status']}"
            )

        await send_message(
            session,
            chat_id,
            "\n".join(lines)
        )
        return

    if command == "/remove":
        if len(parts) != 2:
            await send_message(
                session,
                chat_id,
                "اكتب الأمر هكذا:\n/remove username"
            )
            return

        username = parts[1].lstrip("@").lower()

        if not re.fullmatch(r"[a-zA-Z0-9._]{1,30}", username):
            await send_message(
                session,
                chat_id,
                "اسم المستخدم غير صالح."
            )
            return

        await request(
            session,
            "DELETE",
            f"{SUPABASE_API}/monitored_accounts",
            params={
                "username": f"eq.{username}",
                "chat_id": f"eq.{chat_id}"
            }
        )

        await send_message(
            session,
            chat_id,
            f"تم حذف @{username} من قائمتك."
        )
        return

    await send_message(
        session,
        chat_id,
        "الأمر غير معروف. أرسل /help لعرض الأوامر."
    )


async def main():
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        offset = await get_offset(session)

        result = await request(
            session,
            "GET",
            f"{TELEGRAM_API}/getUpdates",
            params={
                "offset": offset,
                "timeout": 0
            }
        )

        if not result.get("ok"):
            raise RuntimeError("Telegram API returned an error")

        updates = result.get("result", [])

        for update in updates:
            message = update.get("message")

            if message:
                await handle_message(session, message)

            offset = max(
                offset,
                update["update_id"] + 1
            )

        if updates:
            await save_offset(session, offset)


if __name__ == "__main__":
    asyncio.run(main())
