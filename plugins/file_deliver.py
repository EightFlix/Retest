import asyncio
from datetime import datetime, timedelta

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import MessageNotModified

from info import IS_STREAM, PM_FILE_DELETE_TIME, PROTECT_CONTENT, ADMINS
from database.ia_filterdb import get_file_details
from database.users_chats_db import db
from utils import get_settings, get_size, get_shortlink, get_readable_time, temp

# ======================================================
# 🔐 CONFIG
# ======================================================

GRACE_PERIOD = timedelta(minutes=30)

if not hasattr(temp, "FILES"):
    temp.FILES = {}

# ======================================================
# 🧠 PREMIUM / ADMIN CHECK
# ======================================================

async def has_premium_or_grace(user_id):
    if user_id in ADMINS:
        return True

    plan = db.get_plan(user_id)
    if not plan or not plan.get("premium"):
        return False

    expire = plan.get("expire")
    if isinstance(expire, (int, float)):
        expire = datetime.utcfromtimestamp(expire)

    return expire and datetime.utcnow() <= expire + GRACE_PERIOD


# ======================================================
# ⏱️ COUNTDOWN (LIVE EDIT)
# ======================================================

async def countdown_task(uid, seconds):
    try:
        while seconds > 0:
            await asyncio.sleep(60)
            seconds -= 60

            data = temp.FILES.get(uid)
            if not data:
                return

            try:
                await data["notice"].edit(
                    f"⚠️ File will be deleted in {get_readable_time(seconds)}"
                )
            except MessageNotModified:
                pass
            except:
                return
    except asyncio.CancelledError:
        return


# ======================================================
# 📦 FILE BUTTON (GROUP)
# ======================================================

@Client.on_callback_query(filters.regex(r"^file#"))
async def file_button_handler(client: Client, query: CallbackQuery):
    _, file_id = query.data.split("#", 1)
    uid = query.from_user.id

    file = await get_file_details(file_id)
    if not file:
        return await query.answer("❌ File not found", show_alert=True)

    settings = await get_settings(query.message.chat.id)
    premium_ok = await has_premium_or_grace(uid)

    # FREE USER → SHORTLINK
    if settings.get("shortlink") and not premium_ok:
        link = await get_shortlink(
            settings.get("url"),
            settings.get("api"),
            f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}"
        )
        return await query.message.reply_text(
            f"<b>📁 File:</b> {file['file_name']}\n"
            f"<b>📦 Size:</b> {get_size(file['file_size'])}\n\n"
            "🔓 Unlock below:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Get File", url=link)],
                [InlineKeyboardButton("⚡ Upgrade Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("❌ Close", callback_data="close_data")]
            ])
        )

    await query.answer(
        url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}"
    )


# ======================================================
# 📩 /start FILE DELIVERY (PM)
# ======================================================

@Client.on_message(filters.command("start") & filters.private)
async def start_file_delivery(client, message):
    if len(message.command) < 2:
        return

    data = message.command[1]
    if not data.startswith("file_"):
        return

    try:
        _, grp_id, file_id = data.split("_", 2)
        grp_id = int(grp_id)
    except:
        return await message.reply("❌ Invalid link")

    uid = message.from_user.id

    file = await get_file_details(file_id)
    if not file:
        return await message.reply("❌ File not found")

    settings = await get_settings(grp_id)
    premium_ok = await has_premium_or_grace(uid)

    if settings.get("shortlink") and not premium_ok:
        return await message.reply(
            "🔒 Premium expired.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Renew Premium", callback_data="buy_premium")]
            ])
        )

    # ---------- SAFE CAPTION ----------
    caption_tpl = settings.get("caption") or "{file_name}\n\n{file_caption}"
    caption = caption_tpl.format(
        file_name=file.get("file_name", "File"),
        file_caption=file.get("caption", "")
    )

    buttons = []
    if IS_STREAM:
        buttons.append([
            InlineKeyboardButton("▶️ Watch / Download", callback_data=f"stream#{file_id}")
        ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])

    sent = await client.send_cached_media(
        chat_id=uid,
        file_id=file_id,
        caption=caption,
        protect_content=PROTECT_CONTENT,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    notice = await sent.reply(
        f"⚠️ File will be deleted in {get_readable_time(PM_FILE_DELETE_TIME)}"
    )

    # delete /start msg
    try:
        await message.delete()
    except:
        pass

    # cleanup old file if exists
    old = temp.FILES.pop(uid, None)
    if old:
        try:
            old["task"].cancel()
            await old["file"].delete()
            await old["notice"].delete()
        except:
            pass

    task = asyncio.create_task(countdown_task(uid, PM_FILE_DELETE_TIME))

    temp.FILES[uid] = {
        "owner": uid,
        "file_id": file_id,
        "file": sent,
        "notice": notice,
        "task": task
    }

    await asyncio.sleep(PM_FILE_DELETE_TIME)

    data = temp.FILES.pop(uid, None)
    if not data:
        return

    try:
        await data["file"].delete()
    except:
        pass

    try:
        await data["notice"].edit(
            "⌛ Time expired. File deleted.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Get Again", callback_data=f"file#{file_id}")]
            ])
        )
    except:
        pass
