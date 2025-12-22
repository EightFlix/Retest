import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, ListenerTimeout
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, INDEX_LOG_CHANNEL
from database.ia_filterdb import save_file
from utils import temp, get_readable_time

lock = asyncio.Lock()

# ======================================================
# 🚀 START INDEX COMMAND
# ======================================================
@Client.on_message(filters.command("index") & filters.private & filters.user(ADMINS))
async def index_start_cmd(bot, message):

    if lock.locked():
        return await message.reply("⚠️ Indexing already running.")

    ask = await message.reply(
        "📌 Send **channel post link** OR **forward last channel message**"
    )

    try:
        src = await bot.listen(message.chat.id, timeout=120)
    except ListenerTimeout:
        return await ask.edit("⏰ Timeout. Run /index again.")

    await ask.delete()

    # ---------------- PARSE SOURCE ----------------
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
        return await message.reply("❌ Invalid channel message.")

    ask_skip = await message.reply("🔢 Messages to skip? (`0` recommended)")
    try:
        skip_msg = await bot.listen(message.chat.id, timeout=60)
        skip = int(skip_msg.text)
    except:
        return await ask_skip.edit("❌ Invalid number.")

    await ask_skip.delete()

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Start", callback_data=f"idx#start#{chat_id}#{last_msg_id}#{skip}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="idx#cancel")]
    ])

    await message.reply(
        f"📺 **Channel:** `{chat_id}`\n"
        f"📩 **Last Msg ID:** `{last_msg_id}`\n"
        f"⏭️ **Skip:** `{skip}`",
        reply_markup=btn
    )

# ======================================================
# 🎛 CALLBACK
# ======================================================
@Client.on_callback_query(filters.regex("^idx"))
async def index_callback(bot, query):
    data = query.data.split("#")

    if data[1] == "cancel":
        temp.CANCEL = True
        return await query.message.edit("⛔ Indexing cancelled.")

    if data[1] == "start":
        await query.message.edit("🚀 Indexing started...")
        await run_indexing(
            bot,
            query.message,
            int(data[2]),
            int(data[3]),
            int(data[4])
        )

# ======================================================
# ⚙️ CORE INDEX (HYDROGRAM)
# ======================================================
async def run_indexing(bot, msg, chat_id, last_msg_id, skip):

    start = time.time()
    total = dup = err = 0
    count = 0

    async with lock:
        try:
            async for message in bot.get_chat_history(
                chat_id,
                limit=last_msg_id
            ):
                count += 1

                if count <= skip:
                    continue

                if temp.CANCEL:
                    temp.CANCEL = False
                    break

                if not message.media:
                    continue

                media = message.video or message.document
                if not media:
                    continue

                media.caption = message.caption
                res = await save_file(media)

                if res == "suc":
                    total += 1
                elif res == "dup":
                    dup += 1
                else:
                    err += 1

                if count % 40 == 0:
                    try:
                        await msg.edit(
                            f"📦 **Indexing**\n\n"
                            f"📁 Saved: `{total}`\n"
                            f"♻️ Dupes: `{dup}`\n"
                            f"❌ Errors: `{err}`\n"
                            f"⏱️ Time: `{get_readable_time(time.time()-start)}`",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("⛔ STOP", callback_data="idx#cancel")]
                            ])
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)

                if count % 120 == 0:
                    await asyncio.sleep(1)

        finally:
            await msg.edit(
                f"✅ **Indexing Completed**\n\n"
                f"📁 Saved: `{total}`\n"
                f"♻️ Dupes: `{dup}`\n"
                f"❌ Errors: `{err}`\n"
                f"⏱️ Time: `{get_readable_time(time.time()-start)}`"
            )

            try:
                await bot.send_message(
                    INDEX_LOG_CHANNEL,
                    f"📊 **Index Summary**\n"
                    f"📁 Saved: `{total}`\n"
                    f"♻️ Dupes: `{dup}`\n"
                    f"❌ Errors: `{err}`"
                )
            except:
                pass
