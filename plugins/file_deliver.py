import asyncio
import time
from datetime import datetime, timedelta

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.enums import ChatType

from info import IS_STREAM, PM_FILE_DELETE_TIME, PROTECT_CONTENT, ADMINS
from database.ia_filterdb import get_file_details
from database.users_chats_db import db
from utils import get_settings, get_size, get_shortlink, temp


# ======================================================
# CONFIG
# ======================================================

GRACE_PERIOD = timedelta(minutes=30)
RESEND_EXPIRE_TIME = 60   # seconds
ANTI_SPAM_DELAY = 1.5    # seconds (IMPORTANT)


# ======================================================
# PREMIUM / GRACE CHECK
# ======================================================

async def has_premium_or_grace(user_id: int) -> bool:
    if user_id in ADMINS:
        return True

    plan = db.get_plan(user_id)
    if not plan or not plan.get("premium"):
        return False

    expire = plan.get("expire")
    if isinstance(expire, (int, float)):
        expire = datetime.utcfromtimestamp(expire)

    return bool(expire and datetime.utcnow() <= expire + GRACE_PERIOD)


# ======================================================
# GROUP FILE BUTTON
# ======================================================

@Client.on_callback_query(filters.regex(r"^file#"))
async def file_button_handler(client: Client, query: CallbackQuery):
    _, file_id = query.data.split("#", 1)

    file = await get_file_details(file_id)
    if not file:
        return await query.answer("❌ File not found", show_alert=True)

    settings = await get_settings(query.message.chat.id)
    uid = query.from_user.id

    # FREE → SHORTLINK
    if settings.get("shortlink") and not await has_premium_or_grace(uid):
        link = await get_shortlink(
            settings.get("url"),
            settings.get("api"),
            f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}"
        )
        return await query.message.reply_text(
            f"<b>📁 {file['file_name']}</b>\n"
            f"📦 <b>Size:</b> {get_size(file['file_size'])}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Get File", url=link)],
                [InlineKeyboardButton("❌ Close", callback_data="close_data")]
            ])
        )

    # PREMIUM → PM
    await query.answer(
        url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}"
    )


# ======================================================
# /START FILE DELIVERY (ANTI SPAM)
# ======================================================

@Client.on_message(
    filters.private
    & filters.command("start")
    & filters.regex(r"file_")
    & filters.incoming
)
async def start_file_delivery(client: Client, message):
    uid = message.from_user.id

    # 🔥 HARD ANTI-SPAM (MOST IMPORTANT FIX)
    now = time.time()
    last = temp.VERIFICATIONS.get(uid)

    if last and now - last < ANTI_SPAM_DELAY:
        try:
            await message.delete()
        except:
            pass
        return

    temp.VERIFICATIONS[uid] = now

    try:
        _, grp_id, file_id = message.text.split("_", 2)
        grp_id = int(grp_id)
    except:
        try:
            await message.delete()
        except:
            pass
        return

    # 🔥 shield = bot never freezes
    await asyncio.shield(
        deliver_file(client, uid, grp_id, file_id)
    )

    # always delete /start
    try:
        await message.delete()
    except:
        pass


# ======================================================
# CORE DELIVERY
# ======================================================

async def deliver_file(client, uid, grp_id, file_id):
    file = await get_file_details(file_id)
    if not file:
        return

    settings = await get_settings(grp_id)
    if settings.get("shortlink") and not await has_premium_or_grace(uid):
        return

    # ==================================================
    # ONE FILE AT A TIME PER USER
    # ==================================================
    for k, v in list(temp.FILES.items()):
        if v.get("owner") == uid:
            try:
                await v["file"].delete()
            except:
                pass
            temp.FILES.pop(k, None)

    # ==================================================
    # CLEAN CAPTION (NO DUPLICATE)
    # ==================================================
    file_name = file.get("file_name", "").strip()
    file_cap = (file.get("caption") or "").strip()

    if file_cap == file_name or not file_cap:
        caption = file_name
    else:
        caption = f"{file_name}\n\n{file_cap}"

    # ==================================================
    # BUTTONS
    # ==================================================
    buttons = []
    if IS_STREAM:
        buttons.append([
            InlineKeyboardButton("▶️ Watch / Download", callback_data=f"stream#{file_id}")
        ])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])

    markup = InlineKeyboardMarkup(buttons)

    sent = await client.send_cached_media(
        chat_id=uid,
        file_id=file_id,
        caption=caption,
        protect_content=PROTECT_CONTENT,
        reply_markup=markup
    )

    temp.FILES[sent.id] = {
        "owner": uid,
        "file": sent,
        "expire": int(time.time()) + PM_FILE_DELETE_TIME
    }

    # ==================================================
    # SILENT AUTO DELETE (NO CAPTION EDIT)
    # ==================================================
    await asyncio.sleep(PM_FILE_DELETE_TIME)

    data = temp.FILES.pop(sent.id, None)
    if not data:
        return

    try:
        await sent.delete()
    except:
        pass

    resend = await client.send_message(
        uid,
        "⌛ <b>File expired</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Resend File", callback_data=f"resend#{file_id}")]
        ])
    )

    await asyncio.sleep(RESEND_EXPIRE_TIME)
    try:
        await resend.delete()
    except:
        pass


# ======================================================
# RESEND HANDLER
# ======================================================

@Client.on_callback_query(filters.regex(r"^resend#"))
async def resend_handler(client, query: CallbackQuery):
    file_id = query.data.split("#", 1)[1]
    uid = query.from_user.id

    await query.answer()
    try:
        await query.message.delete()
    except:
        pass

    await asyncio.shield(
        deliver_file(client, uid, 0, file_id)
    )
