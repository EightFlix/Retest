import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS
from database.ia_filterdb import save_file
from utils import get_readable_time

LOCK = asyncio.Lock()
CANCEL = False

# user_id -> state data
INDEX_STATE = {}


# =====================================================
# /index COMMAND
# =====================================================
@Client.on_message(filters.command("index") & filters.private & filters.user(ADMINS))
async def start_index(bot, message):
    uid = message.from_user.id

    if LOCK.locked():
        return await message.reply("⏳ Previous indexing still running")

    INDEX_STATE[uid] = {"step": "WAIT_LINK"}
    await message.reply(
        "📤 **Send last channel message link**\n"
        "OR **forward last channel message**"
    )


# =====================================================
# STEP 1: RECEIVE LINK / FORWARD
# =====================================================
@Client.on_message(filters.private & filters.user(ADMINS))
async def index_flow(bot, message):
    uid = message.from_user.id
    state = INDEX_STATE.get(uid)

    if not state:
        return

    # ---------------- WAIT LINK ----------------
    if state["step"] == "WAIT_LINK":
        try:
            if message.text and message.text.startswith("https://t.me"):
                parts = message.text.split("/")
                last_msg_id = int(parts[-1])
                raw_chat = parts[-2]
                chat_id = int("-100" + raw_chat) if raw_chat.isdigit() else raw_chat

            elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
                last_msg_id = message.forward_from_message_id
                chat_id = message.forward_from_chat.id

            else:
                return await message.reply("❌ Send valid link or forward message")

            chat = await bot.get_chat(chat_id)
            if chat.type != enums.ChatType.CHANNEL:
                return await message.reply("❌ Only channels supported")

        except Exception as e:
            INDEX_STATE.pop(uid, None)
            return await message.reply(f"❌ Error: `{e}`")

        INDEX_STATE[uid] = {
            "step": "WAIT_SKIP",
            "chat_id": chat_id,
            "last_msg_id": last_msg_id,
            "title": chat.title
        }

        return await message.reply("⏩ Send skip message number (0 for none)")

    # ---------------- WAIT SKIP ----------------
    if state["step"] == "WAIT_SKIP":
        try:
            skip = int(message.text)
        except:
            return await message.reply("❌ Skip must be a number")

        chat_id = state["chat_id"]
        last_msg_id = state["last_msg_id"]
        title = state["title"]

        INDEX_STATE.pop(uid, None)

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ START", callback_data=f"idx#start#{chat_id}#{last_msg_id}#{skip}")],
            [InlineKeyboardButton("❌ CANCEL", callback_data="idx#close")]
        ])

        return await message.reply(
            f"📢 **Channel:** `{title}`\n"
            f"📊 **Last Message ID:** `{last_msg_id}`\n\n"
            f"Start indexing?",
            reply_markup=btn
        )


# =====================================================
# CALLBACK
# =====================================================
@Client.on_callback_query(filters.regex("^idx#"))
async def index_callback(bot, query):
    global CANCEL

    data = query.data.split("#")
    if data[1] == "close":
        return await query.message.edit("❌ Cancelled")

    _, _, chat_id, last_id, skip = data
    await query.message.edit("⚡ Indexing started...")

    async with LOCK:
        CANCEL = False
        await index_worker(
            bot,
            query.message,
            int(chat_id),
            int(last_id),
            int(skip)
        )


# =====================================================
# MAIN INDEX WORKER (PROVEN)
# =====================================================
async def index_worker(bot, status, chat_id, last_msg_id, skip):
    global CANCEL

    start = time.time()
    saved = dup = err = deleted = nomedia = 0
    current = skip

    try:
        async for msg in bot.iter_messages(chat_id, last_msg_id, skip):
            if CANCEL:
                break

            current += 1

            if current % 30 == 0:
                try:
                    btn = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🛑 STOP", callback_data="idx#cancel")]]
                    )
                    await status.edit(
                        f"📊 Processed: `{current}`\n"
                        f"✅ Saved: `{saved}` | ♻️ Dup: `{dup}` | ❌ Err: `{err}`",
                        reply_markup=btn
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except MessageNotModified:
                    pass

            if msg.empty:
                deleted += 1
                continue

            if not msg.media:
                nomedia += 1
                continue

            if msg.media not in (
                enums.MessageMediaType.VIDEO,
                enums.MessageMediaType.DOCUMENT
            ):
                nomedia += 1
                continue

            media = getattr(msg, msg.media.value, None)
            if not media:
                continue

            media.caption = msg.caption
            res = await save_file(media)

            if res == "suc":
                saved += 1
            elif res == "dup":
                dup += 1
            else:
                err += 1

    except Exception as e:
        return await status.edit(f"❌ Failed: `{e}`")

    time_taken = get_readable_time(time.time() - start)
    await status.edit(
        f"✅ **Index Completed**\n\n"
        f"⏱ Time: `{time_taken}`\n"
        f"📥 Saved: `{saved}`\n"
        f"♻️ Duplicate: `{dup}`\n"
        f"❌ Errors: `{err}`\n"
        f"🚫 Non-media: `{nomedia}`"
    )


# =====================================================
# STOP BUTTON
# =====================================================
@Client.on_callback_query(filters.regex("^idx#cancel"))
async def stop_index(bot, query):
    global CANCEL
    CANCEL = True
    await query.answer("Stopping...", show_alert=True)
