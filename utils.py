from hydrogram.errors import UserNotParticipant, FloodWait
from hydrogram.types import InlineKeyboardButton
from info import (
    LONG_IMDB_DESCRIPTION,
    ADMINS,
    IS_PREMIUM,
    TIME_ZONE,
    SHORTLINK_API,
    SHORTLINK_URL
)

import asyncio
import pytz
import qrcode
from io import BytesIO
from datetime import datetime, timedelta

from database.users_chats_db import db
from shortzy import Shortzy


# ======================================================
# 🧠 TEMP CACHE
# ======================================================

class temp(object):
    START_TIME = 0
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    CANCEL = False
    U_NAME = None
    B_NAME = None
    SETTINGS = {}
    VERIFICATIONS = {}
    FILES = {}
    USERS_CANCEL = False
    GROUPS_CANCEL = False
    BOT = None
    PREMIUM = {}


# ======================================================
# 🔐 PREMIUM CONFIG
# ======================================================

GRACE_PERIOD = timedelta(minutes=20)  # hidden grace


# ======================================================
# 🔳 QR CODE GENERATOR
# ======================================================

async def generate_qr_code(data: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio


# ======================================================
# 🔔 FORCE SUB CHECK
# ======================================================

async def is_subscribed(bot, query):
    buttons = []

    if await is_premium(query.from_user.id, bot):
        return buttons

    stg = db.get_bot_sttgs()
    if not stg or not stg.get("FORCE_SUB_CHANNELS"):
        return buttons

    for cid in stg["FORCE_SUB_CHANNELS"].split():
        try:
            chat = await bot.get_chat(int(cid))
            await bot.get_chat_member(int(cid), query.from_user.id)
        except UserNotParticipant:
            buttons.append(
                [InlineKeyboardButton(f"Join : {chat.title}", url=chat.invite_link)]
            )
        except:
            pass

    return buttons


# ======================================================
# ✅ VERIFY STATUS
# ======================================================

async def get_verify_status(user_id):
    verify = temp.VERIFICATIONS.get(user_id)
    if not verify:
        verify = await db.get_verify_status(user_id)
        temp.VERIFICATIONS[user_id] = verify
    return verify


async def update_verify_status(user_id, **kwargs):
    current = await get_verify_status(user_id)
    current.update(kwargs)
    temp.VERIFICATIONS[user_id] = current
    await db.update_verify_status(user_id, current)


# ======================================================
# 👑 PREMIUM CHECK (SINGLE SOURCE OF TRUTH)
# ======================================================

async def is_premium(user_id, bot=None) -> bool:
    # Admin & global switch
    if not IS_PREMIUM or user_id in ADMINS:
        return True

    mp = db.get_plan(user_id)
    if not mp or not mp.get("premium"):
        return False

    expire = mp.get("expire")
    if not expire:
        return False

    if isinstance(expire, (int, float)):
        expire = datetime.utcfromtimestamp(expire)

    now = datetime.utcnow()

    # ⏳ Hidden grace period
    if now <= expire + GRACE_PERIOD:
        return True

    # ❌ Hard expired → silent cleanup
    mp.update({
        "premium": False,
        "plan": "",
        "expire": "",
        "last_reminder": "expired"
    })
    db.update_plan(user_id, mp)
    return False


# ======================================================
# 🔁 LIGHT PREMIUM GUARDIAN
# ======================================================

async def check_premium(bot):
    """
    Lightweight safety loop.
    UI & reminders handled in bot.py
    """
    while True:
        try:
            users = db.get_premium_users()
            now = datetime.utcnow()

            for u in users:
                uid = u["id"]
                if uid in ADMINS:
                    continue

                mp = u.get("status", {})
                expire = mp.get("expire")
                if not expire:
                    continue

                if isinstance(expire, (int, float)):
                    expire = datetime.utcfromtimestamp(expire)

                if now > expire + GRACE_PERIOD:
                    mp.update({
                        "premium": False,
                        "plan": "",
                        "expire": ""
                    })
                    db.update_plan(uid, mp)

        except:
            pass

        await asyncio.sleep(1800)  # every 30 minutes


# ======================================================
# 📢 BROADCAST
# ======================================================

async def broadcast_messages(user_id, message, pin):
    try:
        m = await message.copy(chat_id=user_id)
        if pin:
            await m.pin(both_sides=True)
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, pin)
    except:
        await db.delete_user(int(user_id))
        return "Error"


async def groups_broadcast_messages(chat_id, message, pin):
    try:
        m = await message.copy(chat_id=chat_id)
        if pin:
            try:
                await m.pin()
            except:
                pass
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(chat_id, message, pin)
    except:
        await db.delete_chat(chat_id)
        return "Error"


# ======================================================
# 🧰 UTILITIES
# ======================================================

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    size = float(size)
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


async def get_shortlink(url, api, link):
    shortzy = Shortzy(api_key=api, base_site=url)
    return await shortzy.convert(link)


def get_readable_time(seconds):
    periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
    result = ""
    for name, sec in periods:
        if seconds >= sec:
            val, seconds = divmod(seconds, sec)
            result += f"{int(val)}{name}"
    return result or "0s"


async def get_settings(group_id):
    stg = temp.SETTINGS.get(group_id)
    if not stg:
        stg = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = stg
    return stg


def get_wish():
    hour = datetime.now(pytz.timezone(TIME_ZONE)).hour
    if hour < 12:
        return "Good Morning 🌞"
    if hour < 18:
        return "Good Afternoon 🌗"
    return "Good Evening 🌘"
