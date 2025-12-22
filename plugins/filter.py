import asyncio
import hashlib
from math import ceil
from time import time
from collections import defaultdict

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS, UPI_ID, UPI_NAME
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import (
    get_size,
    is_premium,
    temp,
    learn_keywords,
    suggest_query,
    get_lang
)

RESULTS_PER_PAGE = 10
RESULT_EXPIRE_TIME = 300     # 5 minutes
EXPIRE_DELETE_DELAY = 60     # delete expired message after 1 min
RATE_LIMIT = 5               # searches per minute
RATE_LIMIT_WINDOW = 60       # seconds

# Rate limiting storage
user_search_times = defaultdict(list)

# Callback data storage (to avoid 64-byte limit)
if not hasattr(temp, 'callback_data'):
    temp.callback_data = {}


# =====================================================
# 🛡️ RATE LIMITER
# =====================================================
def is_rate_limited(user_id):
    """Check if user has exceeded search rate limit"""
    now = time()
    # Clean old timestamps
    user_search_times[user_id] = [
        t for t in user_search_times[user_id] 
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(user_search_times[user_id]) >= RATE_LIMIT:
        return True
    
    user_search_times[user_id].append(now)
    return False


# =====================================================
# 🔑 CALLBACK KEY GENERATOR
# =====================================================
def make_callback_key(search, offset, source_chat_id, owner):
    """Generate short callback key and store full data"""
    # Create unique hash
    data_str = f"{search}:{offset}:{source_chat_id}:{owner}:{time()}"
    key = hashlib.md5(data_str.encode()).hexdigest()[:12]
    
    # Store full data
    temp.callback_data[key] = {
        'search': search,
        'offset': offset,
        'source_chat_id': source_chat_id,
        'owner': owner,
        'created_at': time()
    }
    
    # Clean old keys (older than 10 minutes)
    current_time = time()
    temp.callback_data = {
        k: v for k, v in temp.callback_data.items()
        if current_time - v.get('created_at', 0) < 600
    }
    
    return key


# =====================================================
# 🔓 CALLBACK KEY RETRIEVER
# =====================================================
def get_callback_data(key):
    """Retrieve stored callback data"""
    return temp.callback_data.get(key)


# =====================================================
# 🧹 INPUT SANITIZER
# =====================================================
def sanitize_search(text):
    """Sanitize search input"""
    # Remove excessive whitespace
    text = " ".join(text.split())
    
    # Remove potentially problematic characters
    forbidden = ['<', '>', '&', '"', "'"]
    for char in forbidden:
        text = text.replace(char, '')
    
    return text.strip()


# =====================================================
# 📩 MESSAGE HANDLER
# =====================================================
@Client.on_message(filters.text & filters.incoming & (filters.group | filters.private))
async def filter_handler(client, message):
    try:
        # Ignore commands
        if message.text.startswith("/"):
            return

        user_id = message.from_user.id
        raw_search = message.text.strip().lower()

        # Minimum length check
        if len(raw_search) < 2:
            return

        # ==============================
        # 🛡️ RATE LIMIT CHECK (Skip for Admins & Premium)
        # ==============================
        if user_id not in ADMINS:
            # Check if user is premium
            try:
                user_is_premium = await is_premium(user_id, client)
            except:
                user_is_premium = False
            
            # Apply rate limit only for non-premium users
            if not user_is_premium:
                if is_rate_limited(user_id):
                    lang = get_lang(
                        user_id=user_id,
                        group_id=message.chat.id if message.chat.type != enums.ChatType.PRIVATE else None
                    )
                    text = (
                        "⚠️ <b>Too many searches!</b>\n\n"
                        "Please wait a moment before searching again.\n\n"
                        "💡 <b>Tip:</b> Premium users get unlimited searches!"
                        if lang == "en"
                        else
                        "⚠️ <b>बहुत सारी खोजें!</b>\n\n"
                        "कृपया दोबारा खोजने से पहले थोड़ा इंतज़ार करें।\n\n"
                        "💡 <b>टिप:</b> प्रीमियम यूज़र्स को अनलिमिटेड खोज मिलती है!"
                    )
                    return await message.reply_text(text, quote=True)

        # 🔥 auto-learn keywords (RAM only, ultra fast)
        try:
            learn_keywords(raw_search)
        except Exception as e:
            print(f"Keyword learning error: {e}")

        # ==============================
        # 🌍 LANGUAGE DETECT
        # ==============================
        lang = get_lang(
            user_id=user_id,
            group_id=message.chat.id if message.chat.type != enums.ChatType.PRIVATE else None
        )

        # ==============================
        # 🚫 GROUP SEARCH (STRICT)
        # ==============================
        if message.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            stg = await db.get_settings(message.chat.id)
            if not stg or stg.get("search") is False:
                return

            chat_id = message.chat.id
            source_chat_id = message.chat.id
            source_chat_title = message.chat.title

        # ==============================
        # 📩 PM SEARCH (PREMIUM ONLY)
        # ==============================
        else:
            chat_id = user_id
            source_chat_id = 0
            source_chat_title = ""

            if user_id not in ADMINS:
                if not await is_premium(user_id, client):
                    text = (
                        "🔒 <b>Premium Required</b>\n\n"
                        "This feature is for premium users only.\n"
                        "Upgrade now to unlock unlimited search."
                        if lang == "en"
                        else
                        "🔒 <b>प्रीमियम आवश्यक है</b>\n\n"
                        "यह सुविधा केवल प्रीमियम यूज़र्स के लिए है।\n"
                        "अनलिमिटेड सर्च के लिए अभी अपग्रेड करें।"
                    )

                    btn = InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton(
                                "💳 Renew via UPI",
                                url=f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&cu=INR"
                            )
                        ]]
                    )
                    return await client.send_message(chat_id, text, reply_markup=btn)

        # 🧹 Sanitize and normalize search
        search = sanitize_search(raw_search)
        
        if not search:
            return

        await send_results(
            client=client,
            chat_id=chat_id,
            owner=user_id,
            search=search,
            offset=0,
            source_chat_id=source_chat_id,
            source_chat_title=source_chat_title,
            lang=lang
        )
    
    except Exception as e:
        print(f"Filter handler error: {e}")
        try:
            await message.reply_text(
                "❌ An error occurred. Please try again.",
                quote=True
            )
        except:
            pass


# =====================================================
# 🔎 SEND / EDIT RESULTS
# =====================================================
async def send_results(
    client,
    chat_id,
    owner,
    search,
    offset,
    source_chat_id,
    source_chat_title,
    lang,
    message=None,
    tried_fallback=False
):
    try:
        files, next_offset, total = await get_search_results(
            search,
            offset=offset,
            max_results=RESULTS_PER_PAGE
        )

        # ==============================
        # 🧠 SMART FALLBACK (AI-LIKE)
        # ==============================
        if not files and not tried_fallback:
            try:
                alt = suggest_query(search)
                if alt and alt != search:
                    return await send_results(
                        client,
                        chat_id,
                        owner,
                        alt,
                        0,
                        source_chat_id,
                        source_chat_title,
                        lang,
                        message,
                        True
                    )
            except Exception as e:
                print(f"Fallback suggestion error: {e}")

        if not files:
            text = (
                f"❌ <b>No results found for:</b>\n<code>{search}</code>"
                if lang == "en"
                else
                f"❌ <b>कोई रिज़ल्ट नहीं मिला:</b>\n<code>{search}</code>"
            )
            if message:
                return await message.edit_text(text, parse_mode=enums.ParseMode.HTML)
            return await client.send_message(chat_id, text, parse_mode=enums.ParseMode.HTML)

        # ==============================
        # 📄 PAGE INFO
        # ==============================
        page = (offset // RESULTS_PER_PAGE) + 1
        total_pages = ceil(total / RESULTS_PER_PAGE)

        try:
            is_premium_user = await is_premium(owner, client)
            crown = "👑 " if is_premium_user else ""
        except:
            crown = ""

        text = (
            f"{crown}🔎 <b>Search :</b> <code>{search}</code>\n"
            f"🎬 <b>Total Files :</b> <code>{total}</code>\n"
            f"📄 <b>Page :</b> <code>{page} / {total_pages}</code>\n\n"
            if lang == "en"
            else
            f"{crown}🔎 <b>खोज :</b> <code>{search}</code>\n"
            f"🎬 <b>कुल फ़ाइलें :</b> <code>{total}</code>\n"
            f"📄 <b>पेज :</b> <code>{page} / {total_pages}</code>\n\n"
        )

        # -------- FILE LIST --------
        for f in files:
            try:
                size = get_size(f.get("file_size", 0))
                file_id = f.get('_id', '')
                file_name = f.get('file_name', 'Unknown')
                
                link = f"https://t.me/{temp.U_NAME}?start=file_{source_chat_id}_{file_id}"
                text += f"📁 <a href='{link}'>[{size}] {file_name}</a>\n\n"
            except Exception as e:
                print(f"File list error: {e}")
                continue

        if source_chat_title:
            text += (
                f"<b>Powered By :</b> {source_chat_title}"
                if lang == "en"
                else
                f"<b>प्रस्तुतकर्ता :</b> {source_chat_title}"
            )

        # -------- PAGINATION --------
        nav = []

        if offset > 0:
            callback_key = make_callback_key(search, offset - RESULTS_PER_PAGE, source_chat_id, owner)
            nav.append(
                InlineKeyboardButton(
                    "◀️ Prev" if lang == "en" else "◀️ पिछला",
                    callback_data=f"page#{callback_key}"
                )
            )

        if next_offset:
            callback_key = make_callback_key(search, offset + RESULTS_PER_PAGE, source_chat_id, owner)
            nav.append(
                InlineKeyboardButton(
                    "Next ▶️" if lang == "en" else "अगला ▶️",
                    callback_data=f"page#{callback_key}"
                )
            )

        markup = InlineKeyboardMarkup([nav]) if nav else None

        if message:
            await message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            msg = await client.send_message(
                chat_id,
                text,
                reply_markup=markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
            asyncio.create_task(auto_expire(msg))
    
    except Exception as e:
        print(f"Send results error: {e}")
        error_text = (
            "❌ An error occurred while fetching results."
            if lang == "en"
            else
            "❌ रिज़ल्ट लाते समय एरर आया।"
        )
        try:
            if message:
                await message.edit_text(error_text)
            else:
                await client.send_message(chat_id, error_text)
        except:
            pass


# =====================================================
# 🔁 PAGINATION CALLBACK (OWNER ONLY)
# =====================================================
@Client.on_callback_query(filters.regex("^page#"))
async def pagination_handler(client, query):
    try:
        _, callback_key = query.data.split("#", 1)
        
        # Retrieve stored data
        callback_data = get_callback_data(callback_key)
        
        if not callback_data:
            return await query.answer(
                "⌛ This result has expired. Please search again.",
                show_alert=True
            )
        
        search = callback_data['search']
        offset = callback_data['offset']
        source_chat_id = callback_data['source_chat_id']
        owner = callback_data['owner']

        # Owner verification
        if query.from_user.id != owner and query.from_user.id not in ADMINS:
            return await query.answer("❌ Not your result", show_alert=True)

        lang = get_lang(query.from_user.id, query.message.chat.id)

        # Get source chat title
        source_chat_title = ""
        if source_chat_id:
            try:
                chat = await client.get_chat(source_chat_id)
                source_chat_title = chat.title
            except Exception as e:
                print(f"Get chat error: {e}")

        await query.answer()

        await send_results(
            client,
            query.message.chat.id,
            owner,
            search,
            offset,
            source_chat_id,
            source_chat_title,
            lang,
            query.message
        )
    
    except Exception as e:
        print(f"Pagination handler error: {e}")
        try:
            await query.answer("❌ An error occurred", show_alert=True)
        except:
            pass


# =====================================================
# ⏱ AUTO EXPIRE (HARD DELETE)
# =====================================================
async def auto_expire(message):
    try:
        await asyncio.sleep(RESULT_EXPIRE_TIME)

        try:
            await message.edit_reply_markup(None)
            await message.edit_text("⌛ <i>This result has expired.</i>")
        except Exception as e:
            print(f"Expire edit error: {e}")
            return

        await asyncio.sleep(EXPIRE_DELETE_DELAY)
        
        try:
            await message.delete()
        except Exception as e:
            print(f"Expire delete error: {e}")
    
    except Exception as e:
        print(f"Auto expire error: {e}")
