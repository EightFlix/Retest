from hydrogram.errors import UserNotParticipant, FloodWait
from info import LONG_IMDB_DESCRIPTION, ADMINS, IS_PREMIUM, TIME_ZONE
# from imdb import Cinemagoer  <-- इसे हटा दिया गया है
import asyncio
from hydrogram.types import InlineKeyboardButton
from hydrogram import enums
import re
from datetime import datetime
from database.users_chats_db import db
from shortzy import Shortzy
import requests, pytz

# imdb = Cinemagoer() <-- इसे भी हटा दिया गया है

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

async def is_subscribed(bot, query):
    btn = []
    if await is_premium(query.from_user.id, bot):
        return btn
    stg = db.get_bot_sttgs()
    if not stg or not stg.get('FORCE_SUB_CHANNELS'):
        return btn
    for id in stg.get('FORCE_SUB_CHANNELS').split(' '):
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(int(id), query.from_user.id)
        except UserNotParticipant:
            btn.append(
                [InlineKeyboardButton(f'Join : {chat.title}', url=chat.invite_link)]
            )
    if stg and stg.get('REQUEST_FORCE_SUB_CHANNELS') and not db.find_join_req(query.from_user.id):
        id = stg.get('REQUEST_FORCE_SUB_CHANNELS')
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(int(id), query.from_user.id)
        except UserNotParticipant:
            url = await bot.create_chat_invite_link(int(id), creates_join_request=True)
            btn.append(
                [InlineKeyboardButton(f'Request : {chat.title}', url=url.invite_link)]
            )
    return btn

def upload_image(file_path):
    with open(file_path, 'rb') as f:
        files = {'files[]': f}
        response = requests.post("https://uguu.se/upload", files=files)
    if response.status_code == 200:
        try:
            data = response.json()
            return data['files'][0]['url'].replace('\\/', '/')
        except Exception:
            return None
    return None

async def get_poster(query, bulk=False, id=False, file=None):
    """
    IMDb फंक्शन को डमी फंक्शन से बदल दिया गया है ताकि सर्च तेज हो 
    और डिपेंडेंसी एरर न आए।
    """
    return None

async def is_check_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

async def get_verify_status(user_id):
    verify = temp.VERIFICATIONS.get(user_id)
    if not verify:
        verify = await db.get_verify_status(user_id)
        temp.VERIFICATIONS[user_id] = verify
    return verify

async def update_verify_status(user_id, verify_token="", is_verified=False, link="", expire_time=0):
    current = await get_verify_status(user_id)
    current['verify_token'] = verify_token
    current['is_verified'] = is_verified
    current['link'] = link
    current['expire_time'] = expire_time
    temp.VERIFICATIONS[user_id] = current
    await db.update_verify_status(user_id, current)

async def is_premium(user_id, bot):
    if not IS_PREMIUM:
        return True
    if user_id in ADMINS:
        return True
    mp = db.get_plan(user_id)
    if mp['premium']:
        if mp['expire'] < datetime.now():
            await bot.send_message(user_id, f"Your premium {mp['plan']} plan is expired, use /plan to activate again")
            mp['expire'] = ''
            mp['plan'] = ''
            mp['premium'] = False
            db.update_plan(user_id, mp)
            return False
        return True
    return False

async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS.update({group_id: settings})
    return settings
    
async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current.update({key: value})
    temp.SETTINGS.update({group_id: current})
    await db.update_settings(group_id, current)

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units)-1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    return ', '.join(f'{elem}' for elem in k)
    
async def get_shortlink(url, api, link):
    shortzy = Shortzy(api_key=api, base_site=url)
    link = await shortzy.convert(link)
    return link

def get_readable_time(seconds):
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result

def get_wish():
    time_now = datetime.now(pytz.timezone(TIME_ZONE))
    now = time_now.strftime("%H")
    if now < "12":
        status = "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌞"
    elif now < "18":
        status = "ɢᴏᴏᴅ ᴀꜰᴛᴇʀɴᴏᴏɴ 🌗"
    else:
        status = "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘"
    return status

async def get_seconds(time_string):
    def extract_value_and_unit(ts):
        value = "".join(filter(str.isdigit, ts))
        unit = "".join(filter(str.isalpha, ts))
        return int(value) if value else 0, unit
    value, unit = extract_value_and_unit(time_string)
    multipliers = {'s': 1, 'min': 60, 'hour': 3600, 'day': 86400, 'month': 2592000, 'year': 31536000}
    return value * multipliers.get(unit, 0)
