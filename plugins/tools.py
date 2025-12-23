import os
import aiohttp
import asyncio
import time
from typing import Optional, Dict

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from info import ADMINS
from utils import is_premium

# =========================
# CONFIG (KOYEB SAFE)
# =========================
MAX_CONCURRENT_UPLOADS = 1
CHUNK_SIZE = 128 * 1024
PROGRESS_UPDATE_INTERVAL = 2
SESSION_TIMEOUT = 300
MAX_FILE_SIZE = 100 * 1024 * 1024

GOFILE_API = "https://api.gofile.io/uploadFile"  # ✅ FIXED

# =========================
# GLOBAL STATE
# =========================
UPLOAD_QUEUE = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
UPLOAD_PANEL: Dict[int, Dict] = {}
ACTIVE_UPLOADS: Dict[int, bool] = {}

# =========================
# CLEANUP TASK
# =========================
async def cleanup_sessions():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired = [
            uid for uid, s in UPLOAD_PANEL.items()
            if now - s.get("created", now) > SESSION_TIMEOUT
        ]
        for uid in expired:
            UPLOAD_PANEL.pop(uid, None)
            ACTIVE_UPLOADS.pop(uid, None)

asyncio.create_task(cleanup_sessions())

# =========================
# UI
# =========================
def panel_buttons(state: Dict):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"🔒 Private {'✅' if state.get('private') else '❌'}",
            callback_data="up#private"
        )],
        [
            InlineKeyboardButton("🗑 10 Min", callback_data="up#del#600"),
            InlineKeyboardButton("🗑 30 Min", callback_data="up#del#1800")
        ],
        [
            InlineKeyboardButton("🚀 Upload", callback_data="up#start"),
            InlineKeyboardButton("❌ Cancel", callback_data="up#cancel")
        ]
    ])

# =========================
# PROGRESS TRACKER
# =========================
class ProgressTracker:
    def __init__(self, total, msg):
        self.total = total
        self.sent = 0
        self.start = time.time()
        self.msg = msg
        self.last = 0

    async def update(self, size):
        self.sent += size
        now = time.time()
        if now - self.last < PROGRESS_UPDATE_INTERVAL:
            return

        elapsed = now - self.start
        if elapsed < 1:
            return

        percent = (self.sent / self.total) * 100
        speed = (self.sent / elapsed) / 1024
        eta = int((self.total - self.sent) / (speed * 1024 + 1))

        text = (
            "⚡ **Uploading...**\n\n"
            f"📊 `{percent:.1f}%`\n"
            f"🚀 `{speed:.1f} KB/s`\n"
            f"⏳ `{eta}s remaining`"
        )

        try:
            await self.msg.edit(text)
            self.last = now
        except:
            pass

# =========================
# /upload COMMAND
# =========================
@Client.on_message(filters.command("upload") & filters.private)
async def upload_panel(bot, message):
    uid = message.from_user.id

    if ACTIVE_UPLOADS.get(uid):
        return await message.reply("⚠️ Upload already running")

    if uid not in ADMINS and not await is_premium(uid, bot):
        return await message.reply("❌ Premium only")

    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply("❗ Reply to a file")

    media = message.reply_to_message
    file = media.document or media.video or media.audio
    size = getattr(file, "file_size", 0)

    if size > MAX_FILE_SIZE:
        return await message.reply("❌ File too large")

    UPLOAD_PANEL[uid] = {
        "file": media,
        "private": False,
        "delete": 0,
        "created": time.time()
    }

    await message.reply(
        f"📤 **Upload Panel**\n\n📁 `{size / 1024 / 1024:.1f} MB`",
        reply_markup=panel_buttons(UPLOAD_PANEL[uid])
    )

# =========================
# CALLBACKS
# =========================
@Client.on_callback_query(filters.regex("^up#"))
async def upload_cb(bot, query: CallbackQuery):
    uid = query.from_user.id
    state = UPLOAD_PANEL.get(uid)
    if not state:
        return await query.answer("Session expired", True)

    action = query.data.split("#")[1]

    if action == "private":
        state["private"] = not state["private"]
        await query.message.edit_reply_markup(panel_buttons(state))
        return await query.answer()

    if action == "del":
        state["delete"] = int(query.data.split("#")[2])
        return await query.answer("Auto delete set")

    if action == "cancel":
        UPLOAD_PANEL.pop(uid, None)
        return await query.message.edit("❌ Cancelled")

    if action == "start":
        if ACTIVE_UPLOADS.get(uid):
            return await query.answer("Already uploading", True)

        await query.message.edit("⏳ Preparing upload...")
        asyncio.create_task(start_upload(bot, query.message, uid))

# =========================
# MAIN UPLOAD LOGIC (FIXED)
# =========================
async def start_upload(bot, msg, uid):
    async with UPLOAD_QUEUE:
        state = UPLOAD_PANEL.get(uid)
        if not state:
            return

        ACTIVE_UPLOADS[uid] = True
        file_path = None

        try:
            media = state["file"]
            await msg.edit("📥 Downloading...")

            file_path = await media.download()
            if not file_path or not os.path.exists(file_path):
                return await msg.edit("❌ Download failed")

            size = os.path.getsize(file_path)
            tracker = ProgressTracker(size, msg)

            await msg.edit("⚡ Uploading...")

            async with aiohttp.ClientSession() as session:
                with open(file_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        "file",
                        f,
                        filename=os.path.basename(file_path),
                        content_type="application/octet-stream"
                    )

                    async with session.post(GOFILE_API, data=data) as r:
                        if r.status != 200:
                            return await msg.edit(f"❌ Upload failed ({r.status})")
                        res = await r.json()

            if res.get("status") != "ok":
                return await msg.edit("❌ Upload rejected")

            link = res["data"]["downloadPage"]
            await msg.edit(
                f"✅ **Upload Complete**\n\n🔗 <code>{link}</code>",
                disable_web_page_preview=True
            )

        except Exception as e:
            await msg.edit(f"❌ Error: {str(e)[:80]}")

        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            UPLOAD_PANEL.pop(uid, None)
            ACTIVE_UPLOADS.pop(uid, None)

# =========================
# CANCEL
# =========================
@Client.on_message(filters.command("cancel_upload") & filters.private)
async def cancel_upload(_, message):
    uid = message.from_user.id
    UPLOAD_PANEL.pop(uid, None)
    ACTIVE_UPLOADS.pop(uid, None)
    await message.reply("✅ Upload cancelled")
