import os
import sys
import time
import asyncio
from datetime import datetime
from collections import defaultdict

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from hydrogram.errors import MessageNotModified, MessageIdInvalid, BadRequest

from info import ADMINS, LOG_CHANNEL
from database.users_chats_db import db
from database.ia_filterdb import db_count_documents, delete_files
from utils import get_size, get_readable_time, temp


# ======================================================
# 🧠 LIVE DASHBOARD CONFIG
# ======================================================

DASH_REFRESH = 45
DASH_CACHE = {}
DASH_LOCKS = defaultdict(asyncio.Lock)

# Index stats safe init
if not hasattr(temp, "INDEX_STATS"):
    temp.INDEX_STATS = {
        "running": False,
        "start": 0,
        "saved": 0
    }

# Bot start time (fallback)
if not hasattr(temp, "START_TIME"):
    temp.START_TIME = time.time()


# ======================================================
# 🛡 SAFE HELPERS
# ======================================================

async def safe_edit(msg, text, **kwargs):
    try:
        if msg.text == text:
            return True
        await msg.edit(text, **kwargs)
        return True
    except MessageNotModified:
        return True
    except (MessageIdInvalid, BadRequest):
        return False
    except Exception:
        return False


async def safe_send_log(bot, text):
    if not LOG_CHANNEL:
        return False
    try:
        await bot.send_message(LOG_CHANNEL, text)
        return True
    except Exception:
        return False


async def safe_answer(query, text="", alert=False):
    try:
        await query.answer(text, show_alert=alert)
    except Exception:
        pass


# ======================================================
# 📊 DASHBOARD BUILDER (FIXED)
# ======================================================

async def build_dashboard():
    stats = {
        "users": 0,
        "chats": 0,
        "files": 0,
        "premium": 0,
        "used_data": "0 B",
        "uptime": "N/A",
        "now": datetime.fromtimestamp(time.time()).strftime("%d %b %Y, %I:%M %p")
    }

    # Users
    try:
        stats["users"] = await db.total_users_count()
    except:
        pass

    # Groups
    try:
        stats["chats"] = await asyncio.to_thread(
            db.groups.count_documents, {}
        )
    except:
        pass

    # Files
    try:
        stats["files"] = await asyncio.to_thread(db_count_documents)
    except:
        pass

    # Premium
    try:
        stats["premium"] = await asyncio.to_thread(
            db.premium.count_documents, {"plan.premium": True}
        )
    except:
        pass

    # ✅ DB SIZE FIX (REAL FIX)
    try:
        info = await asyncio.to_thread(db.users.database.command, "dbstats")
        stats["used_data"] = get_size(info.get("dataSize", 0))
    except:
        stats["used_data"] = "0 B"

    # Uptime
    try:
        stats["uptime"] = get_readable_time(time.time() - temp.START_TIME)
    except:
        pass

    # Index speed
    idx_text = "❌ Not running"
    try:
        idx = temp.INDEX_STATS
        if idx.get("running"):
            dur = max(1, time.time() - idx.get("start", time.time()))
            speed = idx.get("saved", 0) / dur
            idx_text = f"🚀 {speed:.2f} files/sec"
    except:
        pass

    return (
        "📊 <b>LIVE ADMIN DASHBOARD</b>\n\n"
        f"👤 <b>Users</b>        : <code>{stats['users']}</code>\n"
        f"👥 <b>Groups</b>       : <code>{stats['chats']}</code>\n"
        f"📦 <b>Indexed Files</b>: <code>{stats['files']}</code>\n"
        f"💎 <b>Premium Users</b>: <code>{stats['premium']}</code>\n\n"
        f"⚡ <b>Index Speed</b>  : <code>{idx_text}</code>\n"
        f"🗃 <b>DB Size</b>      : <code>{stats['used_data']}</code>\n\n"
        f"⏱ <b>Uptime</b>       : <code>{stats['uptime']}</code>\n"
        f"🔄 <b>Updated</b>      : <code>{stats['now']}</code>"
    )


# ======================================================
# 🎛 BUTTONS
# ======================================================

def dashboard_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="dash_refresh"),
            InlineKeyboardButton("🗑 Delete", callback_data="dash_delete")
        ],
        [
            InlineKeyboardButton("🔄 Restart", callback_data="dash_restart"),
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ]
    ])


# ======================================================
# 🚀 OPEN DASHBOARD
# ======================================================

@Client.on_message(filters.command(["admin", "dashboard"]) & filters.user(ADMINS))
async def open_dashboard(bot, message):
    msg = await message.reply("⏳ Loading dashboard...")
    text = await build_dashboard()
    await safe_edit(msg, text, reply_markup=dashboard_buttons())


# ======================================================
# 🔁 CALLBACKS
# ======================================================

@Client.on_callback_query(filters.regex("^dash_"))
async def dash_callbacks(bot, query: CallbackQuery):

    if query.from_user.id not in ADMINS:
        return await safe_answer(query, "Not allowed", True)

    action = query.data

    if action == "dash_refresh":
        async with DASH_LOCKS[query.from_user.id]:
            text = await build_dashboard()
            await safe_edit(query.message, text, reply_markup=dashboard_buttons())
            await safe_answer(query, "Updated")

    elif action == "dash_delete":
        await safe_edit(
            query.message,
            "🗑 <b>Delete Files</b>\n\n"
            "Use:\n<code>/delete keyword</code>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back", callback_data="dash_refresh")]]
            )
        )

    elif action == "dash_restart":
        await safe_answer(query, "Restarting...", True)
        try:
            os.execl(sys.executable, sys.executable, "bot.py")
        except:
            await safe_edit(query.message, "❌ Restart failed")


# ======================================================
# 🗑 DELETE FILES
# ======================================================

@Client.on_message(filters.command("delete") & filters.user(ADMINS))
async def delete_cmd(_, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /delete keyword")

    key = message.text.split(" ", 1)[1].strip()
    count = await asyncio.to_thread(delete_files, key)
    await message.reply(f"✅ Deleted {count} files for `{key}`")
