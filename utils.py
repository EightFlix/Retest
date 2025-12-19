from hydrogram.errors import UserNotParticipant, FloodWait
from info import LONG_IMDB_DESCRIPTION, ADMINS, IS_PREMIUM, TIME_ZONE
import asyncio
from hydrogram.types import InlineKeyboardButton
from hydrogram import enums
import re
from datetime import datetime
from database.users_chats_db import db
from shortzy import Shortzy
import requests, pytz

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

# --- Verification & Subscriber Status ---

async def is_subscribed(bot, query):
    btn = []
    if await is_premium(query.from_user.id, bot):
        return btn
    stg = db.get_bot_sttgs()
    if not stg or not stg.get('FORCE_SUB_CHANNELS'):
        return btn
    for id in stg.get('FORCE_SUB_CHANNELS').split(' '):
        try:
            chat = await bot.get_chat(int(id))
            await bot.get_chat_member(int(id), query.from_user.id)
        except UserNotParticipant:
            btn.append([InlineKeyboardButton(f'Join : {chat.title}', url=chat.invite_link)])
        except: pass
    return btn

async def get_verify_status(user_id):
    """ inline.py के लिए ज़रूरी फंक्शन """
    verify = temp.VERIFICATIONS.get(user_id)
    if not verify:
        verify = await db.get_verify_status(user_id)
        temp.VERIFICATIONS[user_id] = verify
    return verify

async def update_verify_status(user_id, verify_token="", is_verified=False, link="", expire_time=0):
    current = await get_verify_status(user_id)
    current.update({
        'verify_token': verify_token,
        'is_verified': is_verified,
        'link': link,
        'expire_time': expire_time
    })
    temp.VERIFICATIONS[user_id] = current
    await db.update_verify_status(user_id, current)

# --- Premium Status ---

async def is_premium(user_id, bot):
    if not IS_PREMIUM or user_id in ADMINS:
        return True
    mp = db.get_plan(user_id)
    if mp['premium']:
        if mp['expire'] < datetime.now():
            await bot.send_message(user_id, "Your premium plan is expired.")
            mp.update({'expire': '', 'plan': '', 'premium': False})
            db.update_plan(user_id, mp)
            return False
        return True
    return False

# --- Broadcast Features ---

async def broadcast_messages(user_id, message, pin):
    try:
        m = await message.copy(chat_id=user_id)
        if pin: await m.pin(both_sides=True)
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, pin)
    except:
        await db.delete_user(int(user_id))
        return "Error"

# --- Utility Functions ---

async def get_poster(query, bulk=False, id=False, file=None):
    return None # IMDb disabled for speed

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units)-1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

async def get_shortlink(url, api, link):
    shortzy = Shortzy(api_key=api, base_site=url)
    return await shortzy.convert(link)

def get_readable_time(seconds):
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for n, s in periods:
        if seconds >= s:
            v, seconds = divmod(seconds, s)
            result += f'{int(v)}{n}'
    return result or "0s"

async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = settings
    return settings
