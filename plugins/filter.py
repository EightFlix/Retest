import re
import math
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, MAX_BTN, script, LANGUAGES, QUALITY
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_settings, get_size, is_premium, get_shortlink, temp

@Client.on_message(filters.text & filters.incoming & (filters.group | filters.private))
async def filter_handler(client, message):
    if message.text.startswith("/"):
        return
    
    user_id = message.from_user.id
    is_prm = await is_premium(user_id, client)
    
    # --- AttributeError: get_config फिक्स ---
    if message.chat.type == enums.ChatType.PRIVATE:
        if user_id not in ADMINS and not is_prm:
            # पुराने डेटाबेस स्ट्रक्चर के अनुसार stg का उपयोग
            stg = db.get_bot_sttgs()
            pm_search_all = stg.get('PM_SEARCH', True)
            if not pm_search_all:
                return await message.reply_text(
                    "<b>❌ ᴘᴍ sᴇᴀʀᴄʜ ᴅɪsᴀʙʟᴇᴅ</b>\n\nप्रीमियम यूजर्स ही PM में सर्च कर सकते हैं।"
                )

    # सर्च स्ट्रिंग को साफ करना
    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    if not search:
        return

    # ऑटो फिल्टर फंक्शन को कॉल करना
    await auto_filter(client, message, None, search)


async def auto_filter(client, message, reply_msg, search, offset=0, is_edit=False):
    settings = await get_settings(message.chat.id)
    files, n_offset, total = await get_search_results(search, offset=offset)

    if not files:
        if settings.get("spell_check", True):
            if not reply_msg:
                reply_msg = await message.reply_text("🔎 Searching...")
            return await suggest_spelling(message, reply_msg, search)
        else:
            if is_edit:
                return await reply_msg.answer("कोई और फाइल नहीं मिली।", show_alert=True)
            return await message.reply(f"क्षमा करें, `{search}` नहीं मिला।")

    req = message.from_user.id if message.from_user else 0
    is_prm = await is_premium(req, client)
    short_search = search[:25] 
    
    btn = []
    # --- 'h4hBYE>' हटाने और शॉर्टलिंक जोड़ने का लॉजिक ---
    for file in files:
        # फ़ाइल नाम से कचरा साफ करना (RegEx का उपयोग)
        clean_name = re.sub(r'^[a-zA-Z0-9]+>', '', file['file_name']).strip()
        f_size = get_size(file['file_size'])
        
        if is_prm:
            # प्रीमियम यूजर्स को डायरेक्ट फाइल बटन मिलेगा
            btn.append([
                InlineKeyboardButton(f"[{f_size}] {clean_name}", callback_data=f"file#{file['_id']}")
            ])
        else:
            # फ्री यूजर्स के लिए शॉर्टलिंक जनरेट करना
            f_link = await get_shortlink(
                settings['url'], 
                settings['api'], 
                f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}"
            )
            btn.append([
                InlineKeyboardButton(f"⚡ [{f_size}] {clean_name}", url=f_link)
            ])

    # पेजिनेशन बटन्स (Back | Page/Total | Next)
    pagination = []
    if offset != 0:
        pagination.append(
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{int(offset)-MAX_BTN}_{short_search}")
        )
    
    pagination.append(
        InlineKeyboardButton(
            f"{math.ceil(int(offset)/MAX_BTN)+1}/{math.ceil(int(total)/MAX_BTN)}", 
            callback_data="pages"
        )
    )
    
    if n_offset != "":
        pagination.append(
            InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{n_offset}_{short_search}")
        )
    
    btn.append(pagination)
    
    # भाषा और क्वालिटी के बटन्स
    btn.insert(0, [
        InlineKeyboardButton("🌐 ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"filter_menu#lang#{req}#{offset}#{short_search}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"filter_menu#qual#{req}#{offset}#{short_search}")
    ])

    # प्रीमियम खरीदने का बटन (सिर्फ नॉन-प्रीमियम के लिए)
    if not is_prm:
        btn.append([
            InlineKeyboardButton('🤑 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ', url=f"https://t.me/{temp.U_NAME}?start=premium")
        ])

    full_caption = f"<b>💭 ʜᴇʏ,\n♻️ ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ {search}...</b>"

    if is_edit:
        try:
            await reply_msg.edit_text(
                text=full_caption, 
                reply_markup=InlineKeyboardMarkup(btn), 
                disable_web_page_preview=True
            )
        except Exception:
            pass
    else:
        await message.reply_text(
            text=full_caption,
            reply_markup=InlineKeyboardMarkup(btn),
            disable_web_page_preview=True,
            quote=True
        )


# --- CALLBACK HANDLERS (बहाल किया गया) ---
@Client.on_callback_query(filters.regex(r"^(next|filter_menu|apply_filter)"))
async def cb_handler(client, query):
    data = query.data
    
    # अगले पेज के लिए हैंडलर
    if data.startswith("next"):
        _, req, offset, search = data.split("_")
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer("यह आपके लिए नहीं है!", show_alert=True)
        await auto_filter(client, query.message.reply_to_message, query.message, search, offset=int(offset), is_edit=True)
    
    # भाषा/क्वालिटी मेनू के लिए
    elif data.startswith("filter_menu"):
        _, type, req, offset, search = data.split("#")
        items = LANGUAGES if type == "lang" else QUALITY
        btn = []
        for i in range(0, len(items), 2):
            row = [InlineKeyboardButton(items[i].title(), callback_data=f"apply_filter#{items[i]}#{search}#{offset}#{req}")]
            if i+1 < len(items):
                row.append(InlineKeyboardButton(items[i+1].title(), callback_data=f"apply_filter#{items[i+1]}#{search}#{offset}#{req}"))
            btn.append(row)
        
        btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{offset}_{search}")])
        await query.message.edit_text(
            f"<b>Select {type.title()} for '{search}':</b>", 
            reply_markup=InlineKeyboardMarkup(btn)
        )

    # फिल्टर अप्लाई करने के लिए
    elif data.startswith("apply_filter"):
        _, choice, search, offset, req = data.split("#")
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer("यह आपके लिए नहीं है!", show_alert=True)
        await auto_filter(client, query.message.reply_to_message, query.message, f"{search} {choice}", offset=0, is_edit=True)
    
    await query.answer()


# --- SPELLING SUGGESTION (बहाल किया गया) ---
async def suggest_spelling(message, reply_msg, search):
    """अगर फिल्म नहीं मिलती तो गूगल सर्च का सुझाव दें"""
    btn = [
        [InlineKeyboardButton("🔎 Search Google", url=f"https://www.google.com/search?q={search.replace(' ', '+')}")],
        [InlineKeyboardButton("🚫 Close", callback_data="close_data")]
    ]
    await reply_msg.edit(
        text=f"👋 Hello {message.from_user.mention if message.from_user else 'User'},\n\nमुझे डेटाबेस में <b>'{search}'</b> नहीं मिला।\n\nकृपया स्पेलिंग चेक करें या गूगल पर खोजें।", 
        reply_markup=InlineKeyboardMarkup(btn)
    )

