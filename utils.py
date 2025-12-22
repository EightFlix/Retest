import asyncio
import pytz
import qrcode
import time
import random
from io import BytesIO
from datetime import datetime, timedelta

from hydrogram.errors import UserNotParticipant, FloodWait
from hydrogram.types import InlineKeyboardButton

from info import ADMINS, IS_PREMIUM, TIME_ZONE
from database.users_chats_db import db
from shortzy import Shortzy


# =========================
# OPTIONAL SHORTLINK
# =========================
try:
    from info import SHORTLINK_API, SHORTLINK_URL
except ImportError:
    SHORTLINK_API = None
    SHORTLINK_URL = None


# ======================================================
# 🧠 GLOBAL RUNTIME STATE (Koyeb Optimized)
# ======================================================

class temp(object):
    START_TIME = 0
    BOT = None

    ME = None
    U_NAME = None
    B_NAME = None

    SETTINGS = {}
    VERIFICATIONS = {}

    FILES = {}          # msg_id -> delivery data
    PREMIUM = {}        # RAM premium cache
    KEYWORDS = {}       # learned keywords (RAM)

    LANG_USER = {}      # user_id -> hi/en
    LANG_GROUP = {}     # group_id -> hi/en

    INDEX_STATS = {
        "running": False,
        "start": 0,
        "scanned": 0,
        "saved": 0,
        "dup": 0,
        "err": 0
    }
    
    # Koyeb optimization flags
    _cleanup_running = False
    _watcher_running = False
    _reminder_running = False


# ======================================================
# 👑 PREMIUM CONFIG (Koyeb Optimized)
# ======================================================

GRACE_PERIOD = timedelta(minutes=20)
PREMIUM_CACHE_TTL = 600  # 10 min cache (increased for Koyeb)


# ======================================================
# ⚡ ULTRA FAST PREMIUM CHECK
# ======================================================

async def is_premium(user_id, bot=None) -> bool:
    """Koyeb optimized premium check with extended cache"""
    if not IS_PREMIUM or user_id in ADMINS:
        return True

    now_ts = time.time()
    cached = temp.PREMIUM.get(user_id)

    if cached and now_ts - cached["checked_at"] < PREMIUM_CACHE_TTL:
        expire = cached["expire"]
        return bool(expire and datetime.utcnow() <= expire + GRACE_PERIOD)

    try:
        plan = db.get_plan(user_id)
    except Exception as e:
        print(f"[KOYEB] DB error in is_premium: {e}")
        return False

    if not plan or not plan.get("premium"):
        temp.PREMIUM[user_id] = {"expire": None, "checked_at": now_ts}
        return False

    expire = plan.get("expire")
    if isinstance(expire, (int, float)):
        expire = datetime.utcfromtimestamp(expire)

    if datetime.utcnow() > expire + GRACE_PERIOD:
        try:
            plan.update({
                "premium": False,
                "expire": "",
                "plan": "",
                "last_reminder": "expired"
            })
            db.update_plan(user_id, plan)
        except Exception as e:
            print(f"[KOYEB] DB error updating expired plan: {e}")
        
        temp.PREMIUM[user_id] = {"expire": None, "checked_at": now_ts}
        return False

    temp.PREMIUM[user_id] = {"expire": expire, "checked_at": now_ts}
    return True


# ======================================================
# 🛡 PREMIUM WATCHER (Koyeb Optimized)
# ======================================================

async def check_premium(bot):
    """Koyeb optimized premium watcher with error handling"""
    if temp._watcher_running:
        return
    
    temp._watcher_running = True
    
    while True:
        try:
            now = datetime.utcnow()
            users = db.get_premium_users()
            
            for u in users:
                try:
                    uid = u["id"]
                    if uid in ADMINS:
                        continue

                    plan = u.get("plan", {})
                    expire = plan.get("expire")
                    if not expire:
                        continue

                    if isinstance(expire, (int, float)):
                        expire = datetime.utcfromtimestamp(expire)

                    if now > expire + GRACE_PERIOD:
                        plan.update({"premium": False, "expire": "", "plan": ""})
                        db.update_plan(uid, plan)
                        temp.PREMIUM.pop(uid, None)
                
                except Exception as e:
                    print(f"[KOYEB] Error checking user {uid}: {e}")
                    continue
                    
                # Small delay to prevent CPU spike on Koyeb
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"[KOYEB] Premium watcher error: {e}")
        
        # Longer sleep for Koyeb (30 min)
        await asyncio.sleep(1800)


# ======================================================
# 🔔 PREMIUM EXPIRY REMINDER (Koyeb Optimized)
# ======================================================

REMINDER_STEPS = [
    ("1d", timedelta(days=1)),
    ("6h", timedelta(hours=6)),
    ("1h", timedelta(hours=1))
]

async def premium_expiry_reminder(bot):
    """Koyeb optimized reminder with batch processing"""
    if temp._reminder_running:
        return
    
    temp._reminder_running = True
    
    while True:
        try:
            now = datetime.utcnow()
            users = db.get_premium_users()
            
            for user in users:
                try:
                    uid = user["id"]
                    if uid in ADMINS:
                        continue

                    plan = user.get("plan", {})
                    expire = plan.get("expire")
                    last = plan.get("last_reminder")

                    if not expire:
                        continue

                    if isinstance(expire, (int, float)):
                        expire = datetime.utcfromtimestamp(expire)

                    for tag, delta in REMINDER_STEPS:
                        if last == tag:
                            continue
                        if expire - delta <= now < expire:
                            try:
                                await bot.send_message(
                                    uid,
                                    "⏰ **Premium Expiry Alert**\n\n"
                                    f"Your premium will expire in **{tag}**.\n"
                                    "Renew now to avoid interruption."
                                )
                                plan["last_reminder"] = tag
                                db.update_plan(uid, plan)
                            except FloodWait as e:
                                await asyncio.sleep(e.value)
                            except Exception as e:
                                print(f"[KOYEB] Reminder send error: {e}")
                            break
                    
                    # Prevent CPU spike
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    print(f"[KOYEB] Error processing reminder for {uid}: {e}")
                    continue
                    
        except Exception as e:
            print(f"[KOYEB] Reminder error: {e}")
        
        # 30 min sleep
        await asyncio.sleep(1800)


# ======================================================
# ✅ VERIFY SYSTEM (Koyeb Optimized)
# ======================================================

async def get_verify_status(user_id: int):
    """Get verification status with error handling"""
    try:
        if user_id not in temp.VERIFICATIONS:
            temp.VERIFICATIONS[user_id] = await db.get_verify_status(user_id)
        return temp.VERIFICATIONS[user_id]
    except Exception as e:
        print(f"[KOYEB] Verify status error: {e}")
        return {}


async def update_verify_status(user_id: int, **kwargs):
    """Update verification status with error handling"""
    try:
        verify = await get_verify_status(user_id)
        verify.update(kwargs)
        temp.VERIFICATIONS[user_id] = verify
        await db.update_verify_status(user_id, verify)
    except Exception as e:
        print(f"[KOYEB] Update verify error: {e}")


# ======================================================
# 🧠 SEARCH LEARNING + SUGGESTIONS (Koyeb Optimized)
# ======================================================

def learn_keywords(text: str):
    """Lightweight keyword learning with memory limit"""
    try:
        # Limit keywords to prevent memory issues on Koyeb
        if len(temp.KEYWORDS) > 10000:
            # Keep only top 5000 most frequent
            sorted_kw = sorted(temp.KEYWORDS.items(), key=lambda x: x[1], reverse=True)
            temp.KEYWORDS = dict(sorted_kw[:5000])
        
        for w in text.lower().split():
            if len(w) >= 3 and len(w) <= 50:  # Limit word length
                temp.KEYWORDS[w] = temp.KEYWORDS.get(w, 0) + 1
    except Exception as e:
        print(f"[KOYEB] Keyword learn error: {e}")


def fast_similarity(a: str, b: str) -> int:
    """Fast similarity check"""
    try:
        if a == b:
            return 100
        a_set, b_set = set(a.split()), set(b.split())
        common = a_set & b_set
        if not common:
            return 0
        score = int((len(common) / max(len(a_set), len(b_set))) * 100)
        return min(score, 100)
    except:
        return 0


def suggest_query(query: str):
    """Suggest similar query"""
    try:
        best, score = None, 0
        query_lower = query.lower()
        
        # Limit search iterations on Koyeb
        checked = 0
        for k in temp.KEYWORDS:
            if checked > 500:  # Limit iterations
                break
            s = fast_similarity(query_lower, k)
            if s > score:
                best, score = k, s
            checked += 1
            
        return best if score >= 60 else None
    except Exception as e:
        print(f"[KOYEB] Suggest query error: {e}")
        return None


# ======================================================
# 🌍 LANGUAGE SYSTEM
# ======================================================

def set_user_lang(user_id, lang):
    """Set user language"""
    temp.LANG_USER[user_id] = lang


def set_group_lang(group_id, lang):
    """Set group language"""
    temp.LANG_GROUP[group_id] = lang


def get_lang(user_id=None, group_id=None, default="en"):
    """Get language preference"""
    if user_id and user_id in temp.LANG_USER:
        return temp.LANG_USER[user_id]
    if group_id and group_id in temp.LANG_GROUP:
        return temp.LANG_GROUP[group_id]
    return default


# ======================================================
# 🎉 FESTIVAL + GREETING
# ======================================================

FESTIVALS = {
    (3, 25): "holi",
    (11, 1): "diwali",
    (4, 10): "eid"
}

FESTIVAL_MSG = {
    "holi": {"en": "🎨 Happy Holi", "hi": "🎨 होली मुबारक"},
    "diwali": {"en": "🪔 Happy Diwali", "hi": "🪔 दीपावली मुबारक"},
    "eid": {"en": "🌙 Eid Mubarak", "hi": "🌙 ईद मुबारक"}
}

EMOJI_DAY = ["🌞", "✨", "🌤"]
EMOJI_NIGHT = ["🌙", "⭐", "😴"]


def detect_festival():
    """Detect current festival"""
    try:
        now = datetime.now(pytz.timezone(TIME_ZONE))
        return FESTIVALS.get((now.month, now.day))
    except:
        return None


def get_wish(user_name=None, lang="en", premium=False):
    """Get greeting message"""
    try:
        fest = detect_festival()
        if fest:
            return FESTIVAL_MSG[fest].get(lang, FESTIVAL_MSG[fest]["en"])

        hour = datetime.now(pytz.timezone(TIME_ZONE)).hour
        emoji = random.choice(EMOJI_DAY if hour < 18 else EMOJI_NIGHT)
        if premium:
            emoji = "👑 " + emoji

        name = f", {user_name}" if user_name else ""
        if hour < 12:
            return f"{emoji} {'सुप्रभात' if lang=='hi' else 'Good Morning'}{name}"
        if hour < 18:
            return f"{emoji} {'नमस्ते' if lang=='hi' else 'Good Afternoon'}{name}"
        return f"{emoji} {'शुभ रात्रि' if lang=='hi' else 'Good Evening'}{name}"
    except Exception as e:
        print(f"[KOYEB] Wish error: {e}")
        return "Hello!"


# ======================================================
# 🔁 FILE MEMORY CLEANER (Koyeb Optimized)
# ======================================================

async def cleanup_files_memory():
    """Koyeb optimized memory cleanup"""
    if temp._cleanup_running:
        return
    
    temp._cleanup_running = True
    
    while True:
        try:
            now = int(time.time())
            expired_keys = []
            
            # Collect expired keys
            for k, v in temp.FILES.items():
                if v.get("expire", 0) <= now:
                    expired_keys.append(k)
            
            # Remove in batch
            for k in expired_keys:
                temp.FILES.pop(k, None)
            
            # Also cleanup old cache entries
            if len(temp.PREMIUM) > 1000:
                old_keys = list(temp.PREMIUM.keys())[:500]
                for k in old_keys:
                    temp.PREMIUM.pop(k, None)
                    
        except Exception as e:
            print(f"[KOYEB] Cleanup error: {e}")
        
        await asyncio.sleep(120)  # 2 min


# ======================================================
# 📢 BROADCAST HELPERS (Koyeb Optimized)
# ======================================================

async def broadcast_messages(user_id, message, pin=False):
    """Broadcast to user with flood protection"""
    try:
        msg = await message.copy(chat_id=user_id)
        if pin:
            await msg.pin(both_sides=True)
        return "Success"
    except FloodWait as e:
        if e.value > 300:  # More than 5 min
            return "Error"
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, pin)
    except Exception as e:
        print(f"[KOYEB] Broadcast error for {user_id}: {e}")
        try:
            await db.delete_user(int(user_id))
        except:
            pass
        return "Error"


async def groups_broadcast_messages(chat_id, message, pin=False):
    """Broadcast to group with flood protection"""
    try:
        msg = await message.copy(chat_id=chat_id)
        if pin:
            await msg.pin()
        return "Success"
    except FloodWait as e:
        if e.value > 300:
            return "Error"
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(chat_id, message, pin)
    except Exception as e:
        print(f"[KOYEB] Group broadcast error for {chat_id}: {e}")
        try:
            await db.delete_chat(chat_id)
        except:
            pass
        return "Error"


# ======================================================
# 🔔 FORCE SUB CHECK (Koyeb Optimized)
# ======================================================

async def is_subscribed(bot, query):
    """Check subscription with error handling"""
    buttons = []

    try:
        if await is_premium(query.from_user.id, bot):
            return buttons
    except Exception as e:
        print(f"[KOYEB] Premium check error in is_subscribed: {e}")

    try:
        stg = db.get_bot_sttgs()
        if not stg or not stg.get("FORCE_SUB_CHANNELS"):
            return buttons

        channels = stg["FORCE_SUB_CHANNELS"].split()
        
        for cid in channels:
            try:
                chat = await bot.get_chat(int(cid))
                await bot.get_chat_member(int(cid), query.from_user.id)
            except UserNotParticipant:
                invite = getattr(chat, 'invite_link', None)
                if invite:
                    buttons.append(
                        [InlineKeyboardButton(f"📢 Join {chat.title}", url=invite)]
                    )
            except Exception as e:
                print(f"[KOYEB] Force sub check error for {cid}: {e}")
                continue
    except Exception as e:
        print(f"[KOYEB] is_subscribed error: {e}")

    return buttons


# ======================================================
# 🔳 QR CODE (Koyeb Optimized)
# ======================================================

async def generate_qr_code(data: str):
    """Generate QR code with error handling"""
    try:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        bio.name = "qr.png"
        img.save(bio, "PNG")
        bio.seek(0)
        return bio
    except Exception as e:
        print(f"[KOYEB] QR generation error: {e}")
        return None


# ======================================================
# 📦 SHORTLINK (Koyeb Optimized)
# ======================================================

async def get_shortlink(url, api, link):
    """Get shortlink with timeout and error handling"""
    if not api or not url:
        return link
    
    try:
        # Add timeout for Koyeb
        return await asyncio.wait_for(
            Shortzy(api_key=api, base_site=url).convert(link),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        print(f"[KOYEB] Shortlink timeout")
        return link
    except Exception as e:
        print(f"[KOYEB] Shortlink error: {e}")
        return link


# ======================================================
# 🧰 SMALL UTILITIES
# ======================================================

def get_size(size):
    """Convert bytes to human readable format"""
    try:
        size = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"
    except:
        return "0 B"


def get_readable_time(seconds):
    """Convert seconds to readable time"""
    try:
        periods = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
        out = ""
        for name, sec in periods:
            if seconds >= sec:
                val, seconds = divmod(seconds, sec)
                out += f"{int(val)}{name} "
        return out.strip() or "0s"
    except:
        return "0s"


async def get_settings(group_id):
    """Get group settings with caching"""
    try:
        if group_id not in temp.SETTINGS:
            temp.SETTINGS[group_id] = await db.get_settings(group_id)
        return temp.SETTINGS[group_id]
    except Exception as e:
        print(f"[KOYEB] Settings error: {e}")
        return {}
