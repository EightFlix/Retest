import time
import asyncio
from collections import deque
from pymongo import MongoClient

from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, DATA_DATABASE_URL, DATABASE_NAME
from database.ia_filterdb import save_file
from utils import get_readable_time

# =========================
# GLOBAL STATE
# =========================
INDEX_STATE = {}
INDEX_QUEUE = deque()
ACTIVE_CHANNEL = None
CANCEL = False
QUEUE_LOCK = asyncio.Lock()

# =========================
# RESUME DB (SAFE)
# =========================
mongo = MongoClient(DATA_DATABASE_URL)
db = mongo[DATABASE_NAME]
resume_col = db["index_resume"]

def get_resume_id(chat_id):
    d = resume_col.find_one({"_id": chat_id})
    return d["last_id"] if d else None

def set_resume_id(chat_id, msg_id):
    resume_col.update_one(
        {"_id": chat_id},
        {"$set": {"last_id": msg_id}},
        upsert=True
    )

# =========================
# /index COMMAND
# =========================
@Client.on_message(filters.command("index") & filters.private & filters.user(ADMINS))
async def start_index(bot, message):
    uid = message.from_user.id
    INDEX_STATE[uid] = {"step": "WAIT_SOURCE"}
    await message.reply(
        "📤 Send **last channel message link**\n"
        "OR **forward last channel message**"
    )

# =========================
# STATE HANDLER
# =========================
@Client.on_message(filters.private & filters.user(ADMINS))
async def index_flow(bot, message):
    uid = message.from_user.id
    state = INDEX_STATE.get(uid)
    if not state:
        return

    # ---- STEP 1: SOURCE ----
    if state["step"] == "WAIT_SOURCE":
        try:
            if message.text and message.text.startswith("https://t.me"):
                parts = message.text.split("/")
                last_msg_id = int(parts[-1])
                raw = parts[-2]
                chat_id = int("-100" + raw) if raw.isdigit() else raw

            elif message.forward_from_chat and message.forward_from_chat.type == enums.ChatType.CHANNEL:
                last_msg_id = message.forward_from_message_id
                chat_id = message.forward_from_chat.id
            else:
                return await message.reply("❌ Invalid link or forward")

            chat = await bot.get_chat(chat_id)
            if chat.type != enums.ChatType.CHANNEL:
                raise Exception("Not a channel")

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

    # ---- STEP 2: SKIP ----
    if state["step"] == "WAIT_SKIP":
        try:
            skip = int(message.text)
        except:
            return await message.reply("❌ Skip must be number")

        job = {
            "chat_id": state["chat_id"],
            "last_msg_id": state["last_msg_id"],
            "skip": skip,
            "title": state["title"],
            "reply_to": message
        }
        INDEX_STATE.pop(uid, None)

        INDEX_QUEUE.append(job)
        await message.reply(
            f"📥 Added to queue\n"
            f"📢 `{job['title']}`\n"
            f"⏳ Position: `{len(INDEX_QUEUE)}`"
        )

        await process_queue(bot)

# =========================
# QUEUE PROCESSOR
# =========================
async def process_queue(bot):
    global ACTIVE_CHANNEL, CANCEL

    async with QUEUE_LOCK:
        if ACTIVE_CHANNEL is not None:
            return
        if not INDEX_QUEUE:
            return

        job = INDEX_QUEUE.popleft()
        ACTIVE_CHANNEL = job["chat_id"]
        CANCEL = False

    status = await job["reply_to"].reply(
        f"⚡ **Indexing Started**\n📢 `{job['title']}`"
    )

    await index_worker(
        bot,
        status,
        job["chat_id"],
        job["last_msg_id"],
        job["skip"]
    )

    ACTIVE_CHANNEL = None
    await process_queue(bot)

# =========================
# MAIN INDEX WORKER (RESUME + ETA)
# =========================
async def index_worker(bot, status, chat_id, last_msg_id, skip):
    global CANCEL

    start_time = time.time()
    saved = dup = err = nomedia = 0
    processed = 0

    resume_from = get_resume_id(chat_id)
    if resume_from and resume_from < last_msg_id:
        current_id = resume_from
    else:
        current_id = last_msg_id - skip

    try:
        while current_id > 0:
            if CANCEL:
                break

            try:
                msg = await bot.get_messages(chat_id, current_id)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except:
                current_id -= 1
                continue

            processed += 1

            # ---- STATUS + ETA ----
            if processed % 50 == 0:
                elapsed = time.time() - start_time
                speed = processed / elapsed if elapsed > 0 else 0
                remaining = current_id
                eta = remaining / speed if speed > 0 else 0

                try:
                    btn = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🛑 STOP", callback_data="idx#cancel")]]
                    )
                    await status.edit(
                        f"📊 Scanned: `{processed}`\n"
                        f"✅ `{saved}` | ♻️ `{dup}` | ❌ `{err}`\n"
                        f"⚡ Speed: `{speed:.2f}/s`\n"
                        f"⏳ ETA: `{get_readable_time(eta)}`",
                        reply_markup=btn
                    )
                except MessageNotModified:
                    pass

            if not msg or not msg.media:
                nomedia += 1
                current_id -= 1
                continue

            media = getattr(msg, msg.media.value, None)
            if not media:
                nomedia += 1
                current_id -= 1
                continue

            media.caption = msg.caption
            res = await save_file(media)

            if res == "suc":
                saved += 1
                set_resume_id(chat_id, current_id)
            elif res == "dup":
                dup += 1
            else:
                err += 1

            current_id -= 1

    except Exception as e:
        await status.edit(f"❌ Failed: `{e}`")
        return

    total_time = get_readable_time(time.time() - start_time)
    await status.edit(
        f"✅ **Index Completed**\n\n"
        f"📥 Saved: `{saved}`\n"
        f"♻️ Duplicate: `{dup}`\n"
        f"❌ Errors: `{err}`\n"
        f"🚫 Non-media: `{nomedia}`\n"
        f"⏱ Time: `{total_time}`"
    )

# =========================
# STOP
# =========================
@Client.on_callback_query(filters.regex("^idx#cancel"))
async def stop_index(bot, query):
    global CANCEL
    CANCEL = True
    await query.answer("Stopping current job…", show_alert=True)
