import time
import asyncio
import logging
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, INDEX_LOG_CHANNEL
from database.ia_filterdb import save_file, detect_quality
from utils import temp, get_readable_time

logger = logging.getLogger(__name__)

# 🔐 GLOBAL LOCK (only one indexing at a time)
lock = asyncio.Lock()

# 🧠 SESSION STORE
index_sessions = {}


# ======================================================
# 🔍 VALIDATE CHANNEL ACCESS
# ======================================================
async def validate_channel_access(bot, chat_id):
    try:
        await bot.get_chat(chat_id)
        member = await bot.get_chat_member(chat_id, "me")
        if member.status not in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER
        ):
            return False, "Bot admin nahi hai"
        return True, None
    except UserNotParticipant:
        return False, "Bot channel me nahi hai"
    except Exception as e:
        return False, str(e)


# ======================================================
# 📨 STEP 1: FILE FORWARD DETECT
# ======================================================
@Client.on_message(
    filters.private
    & filters.forwarded
    & filters.user(ADMINS)
    & (filters.video | filters.document)
)
async def forward_detect(bot, message):

    fchat = message.forward_from_chat
    if not fchat or fchat.type != enums.ChatType.CHANNEL:
        return await message.reply("❌ Sirf **channel post** forward karo")

    chat_id = fchat.id
    last_msg_id = message.forward_from_message_id

    index_sessions[message.from_user.id] = {
        "chat_id": chat_id,
        "last_msg_id": last_msg_id,
        "state": "choice",
        "time": time.time()
    }

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ INDEX", callback_data="idx_index"),
            InlineKeyboardButton("⏭ SKIP", callback_data="idx_skip")
        ]
    ])

    await message.reply(
        "📥 **Channel Post Detected**\n\n"
        "Kya karna hai?",
        reply_markup=btn
    )


# ======================================================
# 🎛 STEP 2: INDEX / SKIP BUTTON
# ======================================================
@Client.on_callback_query(filters.regex("^idx_"))
async def index_choice(bot, query):
    uid = query.from_user.id

    if uid not in index_sessions:
        return await query.answer("Session expired", show_alert=True)

    session = index_sessions[uid]

    if query.data == "idx_index":
        await query.answer("Indexing started")
        await query.message.edit_text("🚀 Indexing started (skip = 0)")
        await run_indexing(
            bot,
            query.message,
            session["chat_id"],
            session["last_msg_id"],
            skip=0
        )
        index_sessions.pop(uid, None)

    elif query.data == "idx_skip":
        session["state"] = "waiting_skip"
        await query.message.edit_text(
            "🔢 **Kitne messages skip karne hain?**\n\n"
            "Number bhejo (30 sec)"
        )


# ======================================================
# 🔢 STEP 3: SKIP NUMBER INPUT
# ======================================================
@Client.on_message(filters.private & filters.text & filters.user(ADMINS))
async def skip_input(bot, message):
    uid = message.from_user.id
    if uid not in index_sessions:
        return

    session = index_sessions[uid]
    if session.get("state") != "waiting_skip":
        return

    try:
        skip = int(message.text)
        if skip < 0 or skip >= session["last_msg_id"]:
            raise ValueError
    except:
        return await message.reply("❌ Valid number bhejo")

    await message.reply(f"🚀 Indexing started (skip = {skip})")

    await run_indexing(
        bot,
        message,
        session["chat_id"],
        session["last_msg_id"],
        skip
    )

    index_sessions.pop(uid, None)


# ======================================================
# 🔄 MESSAGE ITERATOR
# ======================================================
async def iter_messages(bot, chat_id, last_msg_id, skip):
    current = skip
    while current < last_msg_id:
        if temp.CANCEL:
            break
        end = min(current + 200, last_msg_id)
        ids = list(range(current + 1, end + 1))
        try:
            msgs = await bot.get_messages(chat_id, ids)
            for m in msgs:
                if m and not m.empty:
                    yield m
        except FloodWait as e:
            await asyncio.sleep(e.value)
        current = end
        await asyncio.sleep(0.3)


# ======================================================
# ⚙️ CORE INDEX ENGINE
# ======================================================
async def run_indexing(bot, msg, chat_id, last_msg_id, skip):
    async with lock:
        ok, err = await validate_channel_access(bot, chat_id)
        if not ok:
            return await msg.edit_text(f"❌ {err}")

        start = time.time()
        scanned = saved = dup = skipped = errors = 0
        temp.CANCEL = False

        async for m in iter_messages(bot, chat_id, last_msg_id, skip):
            scanned += 1
            if not m.media:
                skipped += 1
                continue

            media = getattr(m, m.media.value, None)
            if not media:
                skipped += 1
                continue

            quality = detect_quality(
                getattr(media, "file_name", ""),
                m.caption or ""
            )

            try:
                status = await save_file(media, quality=quality)
                if status == "suc":
                    saved += 1
                elif status == "dup":
                    dup += 1
                else:
                    errors += 1
            except:
                errors += 1

            if scanned % 100 == 0:
                elapsed = time.time() - start
                await msg.edit_text(
                    f"📦 **Indexing...**\n\n"
                    f"Scanned: `{scanned}`\n"
                    f"Saved: `{saved}`\n"
                    f"Dup: `{dup}`\n"
                    f"Skipped: `{skipped}`\n"
                    f"Errors: `{errors}`\n"
                    f"⏱ {get_readable_time(elapsed)}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⛔ STOP", callback_data="idx_cancel")]
                    ])
                )

        total = time.time() - start
        await msg.edit_text(
            f"✅ **Indexing Complete**\n\n"
            f"Scanned: `{scanned}`\n"
            f"Saved: `{saved}`\n"
            f"Dup: `{dup}`\n"
            f"Skipped: `{skipped}`\n"
            f"Errors: `{errors}`\n"
            f"⏱ {get_readable_time(total)}"
        )

        if INDEX_LOG_CHANNEL:
            await bot.send_message(
                INDEX_LOG_CHANNEL,
                f"📊 Index Done\nChat: `{chat_id}`\nSaved: `{saved}`"
            )
