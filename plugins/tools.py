import os
import aiohttp
import asyncio
import time

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from info import ADMINS
from utils import is_premium

# =========================
# GLOBAL STATE
# =========================
UPLOAD_QUEUE = asyncio.Lock()
UPLOAD_PANEL = {}   # user_id -> state

GOFILE_API = "https://store1.gofile.io/contents/uploadfile"

# =========================
# UI
# =========================

def panel_buttons(state):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🔒 Private {'✅' if state['private'] else '❌'}",
                callback_data="up#private"
            ),
            InlineKeyboardButton(
                f"🔁 Mirror {'✅' if state['mirror'] else '❌'}",
                callback_data="up#mirror"
            )
        ],
        [
            InlineKeyboardButton("🗑 Auto Delete 10m", callback_data="up#del#600"),
            InlineKeyboardButton("🗑 Auto Delete 30m", callback_data="up#del#1800")
        ],
        [
            InlineKeyboardButton("🚀 Start Upload", callback_data="up#start"),
            InlineKeyboardButton("❌ Cancel", callback_data="up#cancel")
        ]
    ])

# =========================
# STREAMING FILE WITH PROGRESS
# =========================

class ProgressFile:
    def __init__(self, path, status_msg):
        self.file = open(path, "rb")
        self.total = os.path.getsize(path)
        self.sent = 0
        self.start = time.time()
        self.status = status_msg
        self.last_edit = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = self.file.read(1024 * 256)  # 256KB
        if not chunk:
            self.file.close()
            raise StopAsyncIteration

        self.sent += len(chunk)
        await self._update_progress()
        return chunk

    async def _update_progress(self):
        now = time.time()
        if now - self.last_edit < 1:
            return

        percent = (self.sent / self.total) * 100
        speed = self.sent / (now - self.start + 1)
        eta = (self.total - self.sent) / (speed + 1)

        text = (
            "⚡ **Uploading…**\n\n"
            f"📊 Progress : `{percent:.1f}%`\n"
            f"🚀 Speed : `{speed/1024:.1f} KB/s`\n"
            f"⏳ ETA : `{int(eta)}s`"
        )

        try:
            await self.status.edit(text)
            self.last_edit = now
        except:
            pass

# =========================
# /upload COMMAND
# =========================

@Client.on_message(filters.command("upload") & filters.private)
async def upload_panel(bot, message):
    uid = message.from_user.id

    if uid not in ADMINS and not await is_premium(uid, bot):
        return await message.reply("❌ Upload is Premium only.")

    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply("❗ Reply to a file to upload")

    UPLOAD_PANEL[uid] = {
        "file": message.reply_to_message,
        "private": False,
        "mirror": False,
        "delete": 0
    }

    await message.reply(
        "📤 **Admin Upload Panel**\n\nConfigure options, then start upload.",
        reply_markup=panel_buttons(UPLOAD_PANEL[uid])
    )

# =========================
# CALLBACK
# =========================

@Client.on_callback_query(filters.regex("^up#"))
async def upload_panel_cb(bot, query: CallbackQuery):
    uid = query.from_user.id

    if uid not in UPLOAD_PANEL:
        return await query.answer("Session expired", show_alert=True)

    state = UPLOAD_PANEL[uid]
    data = query.data.split("#")

    if data[1] == "private":
        state["private"] = not state["private"]

    elif data[1] == "mirror":
        state["mirror"] = not state["mirror"]

    elif data[1] == "del":
        state["delete"] = int(data[2])

    elif data[1] == "cancel":
        UPLOAD_PANEL.pop(uid, None)
        return await query.message.edit("❌ Upload cancelled.")

    elif data[1] == "start":
        await query.message.edit("⏳ Preparing upload…")
        asyncio.create_task(start_upload(bot, query.message, uid))
        return

    await query.message.edit_reply_markup(panel_buttons(state))
    await query.answer()

# =========================
# UPLOAD WITH PROGRESS
# =========================

async def start_upload(bot, msg, uid):
    async with UPLOAD_QUEUE:
        state = UPLOAD_PANEL.get(uid)
        if not state:
            return await msg.edit("❌ Session expired.")

        media = state["file"]
        path = await media.download()

        status = await msg.edit("⚡ Starting upload…")

        try:
            progress_file = ProgressFile(path, status)

            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    progress_file,
                    filename=os.path.basename(path),
                    content_type="application/octet-stream"
                )

                async with session.post(GOFILE_API, data=data) as r:
                    res = await r.json()

            if res.get("status") != "ok":
                return await status.edit("❌ Upload failed.")

            link = res["data"]["downloadPage"]

            await status.edit(
                f"✅ **Upload Complete**\n\n<code>{link}</code>",
                disable_web_page_preview=True
            )

        except Exception as e:
            await status.edit(f"❌ Error: {e}")

        finally:
            try:
                os.remove(path)
            except:
                pass
            UPLOAD_PANEL.pop(uid, None)
