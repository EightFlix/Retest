import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, INDEX_LOG_CHANNEL
from database.ia_filterdb import save_file
from utils import temp, get_readable_time

# ======================================================
# 🔒 SINGLE INDEX LOCK
# ======================================================
lock = asyncio.Lock()

# ======================================================
# 🎥 VIDEO QUALITY DETECTOR
# ======================================================
def detect_video_quality(text: str) -> str:
    if not text:
        return "unknown"
    t = text.lower()
    if "2160" in t or "4k" in t:
        return "2160p"
    if "1080" in t:
        return "1080p"
    if "720" in t:
        return "720p"
    if "480" in t:
        return "480p"
    return "unknown"

# ======================================================
# 🚀 START INDEX COMMAND
# ======================================================
@Client.on_message(filters.command("index") & filters.private & filters.user(ADMINS))
async def index_start_cmd(bot, message):
    if lock.locked():
        return await message.reply("⚠️ Indexing already running. Please wait.")

    ask = await message.reply(
        "📌 Send **last message link** or **forward last message**\n"
        "from the channel you want to index."
    )

    try:
        src = await bot.listen(message.chat.id, message.from_user.id, 300)
    except:
        return await ask.edit("⏰ Timeout. Run /index again.")

    await ask.delete()

    # ---------- Parse source ----------
    if src.text and src.text.startswith("https://t.me"):
        try:
            parts = src.text.rstrip("/").split("/")
            last_msg_id = int(parts[-1])
            chat_id = parts[-2]
            if chat_id.isnumeric():
                chat_id = int("-100" + chat_id)
        except:
            return await message.reply("❌ Invalid link.")
    elif src.forward_from_chat and src.forward_from_chat.type == enums.ChatType.CHANNEL:
        chat_id = src.forward_from_chat.id
        last_msg_id = src.forward_from_message_id
    else:
        return await message.reply("❌ Not a valid channel message or link.")

    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f"❌ Cannot access channel: `{e}`")

    ask_skip = await message.reply("🔢 How many messages to skip? (example: `0`)")
    try:
        skip_msg = await bot.listen(message.chat.id, message.from_user.id, 120)
        skip = int(skip_msg.text)
    except:
        return await ask_skip.edit("❌ Invalid number. Cancelled.")

    await ask_skip.delete()

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Start Indexing", callback_data=f"idx#yes#{chat_id}#{last_msg_id}#{skip}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
    ])

    await message.reply(
        f"📺 **Channel:** {chat.title}\n"
        f"📩 **Last Msg ID:** `{last_msg_id}`\n"
        f"⏭️ **Skip:** `{skip}`\n\n"
        "Proceed?",
        reply_markup=btn
    )

# ======================================================
# 🎛 CALLBACK HANDLER
# ======================================================
@Client.on_callback_query(filters.regex("^idx"))
async def index_callback(bot, query):
    data = query.data.split("#")

    if data[1] == "yes":
        await query.message.edit("🚀 Indexing started...")
        await run_indexing(
            bot,
            query.message,
            int(data[2]),
            int(data[3]),
            int(data[4])
        )

    elif data[1] == "cancel":
        temp.CANCEL = True
        await query.answer("⛔ Stopping indexing…", show_alert=True)

# ======================================================
# ⚙️ CORE INDEX LOGIC
# ======================================================
async def run_indexing(bot, msg, chat_id, last_msg_id, skip):
    start = time.time()
    total = dup = err = 0
    current = skip

    async with lock:
        try:
            async for message in bot.iter_messages(chat_id, last_msg_id, skip):
                if temp.CANCEL:
                    temp.CANCEL = False
                    break

                current += 1

                # ❌ No media
                if message.empty or not message.media:
                    continue

                # ================= MEDIA FILTER =================

                # 🎬 VIDEO (MAIN)
                if message.media == enums.MessageMediaType.VIDEO:
                    media = message.video
                    src_text = f"{media.file_name or ''} {message.caption or ''}"
                    media.quality = detect_video_quality(src_text)

                # 📄 DOCUMENT → only PDF / PHP
                elif message.media == enums.MessageMediaType.DOCUMENT:
                    media = message.document
                    if not media or not media.file_name:
                        continue
                    name = media.file_name.lower()
                    if not (name.endswith(".pdf") or name.endswith(".php")):
                        continue

                # ❌ EVERYTHING ELSE
                else:
                    continue

                media.caption = message.caption
                res = await save_file(media)

                if res == "suc":
                    total += 1
                elif res == "dup":
                    dup += 1
                else:
                    err += 1

                # ================= PROGRESS UI =================
                if current % 40 == 0:
                    percent = min(100, int((current / last_msg_id) * 100))
                    filled = int(percent / 5)
                    bar = "█" * filled + "░" * (20 - filled)

                    try:
                        await msg.edit_text(
                            f"📦 **Indexing Files**\n\n"
                            f"`{bar}` **{percent}%**\n\n"
                            f"📂 Saved     : `{total}`\n"
                            f"♻️ Duplicate : `{dup}`\n"
                            f"❌ Errors    : `{err}`\n"
                            f"⏱️ Time     : `{get_readable_time(time.time()-start)}`",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("⛔ STOP", callback_data="idx#cancel#0#0#0")]
                            ])
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)

                # Anti-spam safety
                if current % 120 == 0:
                    await asyncio.sleep(1)

        except Exception as e:
            await msg.reply(f"❌ Indexing error: `{e}`")

        finally:
            await msg.edit(
                f"✅ **Indexing Completed**\n\n"
                f"📁 Saved     : `{total}`\n"
                f"♻️ Duplicate : `{dup}`\n"
                f"❌ Errors    : `{err}`\n"
                f"⏱️ Time     : `{get_readable_time(time.time()-start)}`"
            )

            # ================= INDEX SUMMARY LOG =================
            try:
                await bot.send_message(
                    INDEX_LOG_CHANNEL,
                    f"📊 **Index Summary**\n\n"
                    f"📺 Channel : `{chat_id}`\n"
                    f"📁 Saved   : `{total}`\n"
                    f"♻️ Duplicate : `{dup}`\n"
                    f"❌ Errors  : `{err}`\n"
                    f"⏱️ Time    : `{get_readable_time(time.time()-start)}`"
                )
            except:
                pass
