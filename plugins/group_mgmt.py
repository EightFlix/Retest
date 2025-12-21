import re
import asyncio
from datetime import datetime, timedelta
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, LOG_CHANNEL, script
from database.users_chats_db import db
from utils import get_settings

# =========================
# CONFIG (Phase-1)
# =========================
LINK_DELETE_TIME = 300        # 5 minutes
MAX_WARNS = 3
AUTO_MUTE_TIME = 600          # 10 minutes

LINK_REGEX = re.compile(
    r"(https?://|t\.me/|telegram\.me/|bit\.ly|tinyurl)",
    re.IGNORECASE
)

# =========================
# HELPERS
# =========================

def ist_time():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")

async def log_action(client, text):
    try:
        await client.send_message(LOG_CHANNEL, text)
    except:
        pass

async def warn_user(user_id, chat_id):
    data = db.get_warn(user_id, chat_id) or {"count": 0}
    data["count"] += 1
    db.set_warn(user_id, chat_id, data)
    return data["count"]

async def reset_warn(user_id, chat_id):
    db.clear_warn(user_id, chat_id)

# =========================
# AUTO-DELETE LINKS (ADMIN INCLUDED)
# =========================

@Client.on_message(filters.group & filters.text)
async def auto_delete_links(client, message):
    if not message.text:
        return

    settings = await db.get_settings(message.chat.id)
    if not settings.get("auto_delete", True):
        return

    if LINK_REGEX.search(message.text):
        await asyncio.sleep(LINK_DELETE_TIME)
        try:
            await message.delete()
        except:
            pass

# =========================
# ANTI-LINK + WARN + MUTE
# =========================

@Client.on_message(filters.group & filters.text)
async def anti_link_handler(client, message):
    if not message.from_user:
        return

    settings = await db.get_settings(message.chat.id)
    if not settings.get("anti_link", True):
        return

    if LINK_REGEX.search(message.text):
        try:
            await message.delete()
        except:
            pass

        warns = await warn_user(message.from_user.id, message.chat.id)

        if warns >= MAX_WARNS:
            until = datetime.utcnow() + timedelta(seconds=AUTO_MUTE_TIME)
            try:
                await client.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=enums.ChatPermissions(),
                    until_date=until
                )
            except:
                pass

            await reset_warn(message.from_user.id, message.chat.id)

            await log_action(
                client,
                f"🔇 **Auto Mute Triggered**\n\n"
                f"👤 User: {message.from_user.mention}\n"
                f"🏷 Group: {message.chat.title}\n"
                f"⏱ Duration: 10 minutes\n"
                f"🕒 {ist_time()}"
            )
        else:
            try:
                await client.send_message(
                    message.from_user.id,
                    f"⚠️ **Warning {warns}/{MAX_WARNS}**\n\n"
                    "Links are not allowed in this group."
                )
            except:
                pass

            await log_action(
                client,
                f"⚠️ **Link Violation**\n\n"
                f"👤 User: {message.from_user.mention}\n"
                f"🏷 Group: {message.chat.title}\n"
                f"📊 Warns: {warns}/{MAX_WARNS}\n"
                f"🕒 {ist_time()}"
            )

# =========================
# SETTINGS MENU (ROSE STYLE)
# =========================

@Client.on_message(filters.command("settings") & filters.group)
async def settings_entry(client, message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    member = await client.get_chat_member(message.chat.id, user_id)

    if member.status not in (
        enums.ChatMemberStatus.ADMINISTRATOR,
        enums.ChatMemberStatus.OWNER
    ) and user_id not in ADMINS:
        return await message.reply("❌ Admins only.")

    await message.reply(
        "⚙️ **Group Settings**\n\nManage from PM 👇",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔐 Manage in PM",
                    url=f"https://t.me/{client.me.username}?start=connect_{message.chat.id}"
                )
            ]
        ])
    )

@Client.on_message(filters.command("connect") & filters.private)
async def settings_pm(client, message):
    if len(message.command) < 2:
        return await message.reply("Run /settings in group first.")

    chat_id = int(message.command[1])
    settings = await db.get_settings(chat_id)

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🧹 Auto Delete",
                callback_data=f"gs#auto_delete#{settings.get('auto_delete', True)}#{chat_id}"
            ),
            InlineKeyboardButton(
                "✅ ON" if settings.get("auto_delete", True) else "❌ OFF",
                callback_data=f"gs#auto_delete#{settings.get('auto_delete', True)}#{chat_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Anti Link",
                callback_data=f"gs#anti_link#{settings.get('anti_link', True)}#{chat_id}"
            ),
            InlineKeyboardButton(
                "✅ ON" if settings.get("anti_link", True) else "❌ OFF",
                callback_data=f"gs#anti_link#{settings.get('anti_link', True)}#{chat_id}"
            )
        ]
    ])

    await message.reply("⚙️ **Moderation Settings**", reply_markup=buttons)

@Client.on_callback_query(filters.regex("^gs#"))
async def toggle_settings(client, query):
    _, field, current, chat_id = query.data.split("#")
    chat_id = int(chat_id)
    new = current != "True"

    settings = await db.get_settings(chat_id)
    settings[field] = new
    await db.update_settings(chat_id, settings)

    await query.answer("✅ Updated")
