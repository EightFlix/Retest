import re
import math
import time
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from info import ADMINS, MAX_BTN, SPELL_CHECK, script, LANGUAGES, QUALITY
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_settings, get_size, is_premium, get_shortlink, get_readable_time, temp
from .metadata import get_imdb_metadata, get_file_list_string, send_metadata_reply

# इन-मेमोरी स्टोरेज (सिर्फ बैकअप के लिए)
BUTTONS = {}

@Client.on_message(filters.text & filters.incoming & (filters.group | filters.private))
async def filter_handler(client, message):
    if message.text.startswith("/"):
        return
    
    user_id = message.from_user.id
    is_prm = await is_premium(user_id, client)
    
    if message.chat.type == enums.ChatType.PRIVATE:
        if user_id not in ADMINS and not is_prm:
            pm_search_all = await db.get_config('PM_SEARCH_FOR_ALL')
            if not pm_search_all:
                return await message.reply_text("<b>❌ ᴘᴍ sᴇᴀʀᴄʜ ᴅɪsᴀʙʟᴇᴅ</b>\n\nप्रीमियम यूजर्स ही PM में सर्च कर सकते हैं।")

    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    if not search: return

    reply_msg = await message.reply_text(f"<b><i>🔍 `{search}` सर्च किया जा रहा है...</i></b>")
    await auto_filter(client, message, reply_msg, search)

async def auto_filter(client, message, reply_msg, search, offset=0, is_edit=False):
    settings = await get_settings(message.chat.id)
    files, n_offset, total = await get_search_results(search, offset=offset)

    if not files:
        if settings["spell_check"]:
            return await suggest_spelling(message, reply_msg, search)
        else:
            if is_edit: return await reply_msg.answer("कोई और फाइल नहीं मिली।", show_alert=True)
            return await reply_msg.edit(f"क्षमा करें, `{search}` नहीं मिला।")

    req = message.from_user.id if message.from_user else 0
    is_prm = await is_premium(req, client)
    
    # "Old Request" एरर से बचने के लिए सर्च क्वेरी को छोटा करें
    short_search = search[:25] 
    
    btn = []
    files_link = ""

    # ✅ लिंक मोड फिक्स: स्क्रीनशॉट के अनुसार फाइल लिस्ट जनरेट करना
    if settings['links']:
        files_link = get_file_list_string(files, message.chat.id, offset=offset+1)
    
    # ✅ बटन मोड: अगर लिंक मोड ऑफ है, तभी फाइल बटन्स दिखाएं
    if not settings['links']:
        for file in files:
            if is_prm:
                btn.append([InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name']}", callback_data=f"file#{file['_id']}")])
            else:
                f_link = await get_shortlink(settings['url'], settings['api'], f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}")
                btn.append([InlineKeyboardButton(f"⚡ [{get_size(file['file_size'])}] {file['file_name']}", url=f_link)])

    # ✅ पेजिनेशन बटन्स (Back/Next)
    pagination_row = []
    if offset != 0:
        pagination_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{int(offset)-MAX_BTN}_{short_search}"))
    
    pagination_row.append(InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(int(total) / MAX_BTN)}", callback_data="pages"))
    
    if n_offset != "":
        pagination_row.append(InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{n_offset}_{short_search}"))
    
    btn.append(pagination_row)
    
    # ✅ लैंग्वेज और क्वालिटी मेनू बटन्स
    btn.insert(0, [
        InlineKeyboardButton("🌐 ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"filter_menu#lang#{req}#{offset}#{short_search}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"filter_menu#qual#{req}#{offset}#{short_search}")
    ])

    if not is_prm:
        btn.append([InlineKeyboardButton('🤑 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ', url=f"https://t.me/{temp.U_NAME}?start=premium")])

    cap, poster = await get_imdb_metadata(search, files, settings)
    
    # केप्शन के साथ फाइल लिस्ट जोड़ना (यही मुख्य फिक्स है)
    full_caption = cap + (files_link if files_link else "")

    if is_edit:
        try:
            if poster and poster != "https://telegra.ph/file/default_poster.jpg":
                await reply_msg.edit_media(media=InputMediaPhoto(poster, caption=full_caption[:1024]), reply_markup=InlineKeyboardMarkup(btn))
            else:
                await reply_msg.edit_text(text=full_caption[:4096], reply_markup=InlineKeyboardMarkup(btn))
        except: pass
    else:
        # ✅ metadata.py का उपयोग करके मैसेज भेजना
        await send_metadata_reply(message, cap, poster, InlineKeyboardMarkup(btn), settings, files_link)
        await reply_msg.delete()

# --- CALLBACK HANDLERS (बटनों के लिए) ---

@Client.on_callback_query(filters.regex(r"^filter_menu"))
async def filter_selection_handler(client, query):
    _, type, req, offset, search = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer("यह आपके लिए नहीं है!", show_alert=True)
    
    items = LANGUAGES if type == "lang" else QUALITY
    btn = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i].title(), callback_data=f"apply_filter#{items[i]}#{search}#{offset}#{req}")]
        if i+1 < len(items):
            row.append(InlineKeyboardButton(items[i+1].title(), callback_data=f"apply_filter#{items[i+1]}#{search}#{offset}#{req}"))
        btn.append(row)
    
    btn.append([InlineKeyboardButton("⪻ ʙᴀᴄᴋ", callback_data=f"next_{req}_{offset}_{search}")])
    await query.message.edit_text(f"<b>Select {type.title()} for '{search}':</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^apply_filter"))
async def apply_filter_handler(client, query):
    _, choice, search, offset, req = query.data.split("#")
    await query.answer(f"Applying: {choice}")
    await auto_filter(client, query.message.reply_to_message, query.message, f"{search} {choice}", offset=0, is_edit=True)

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page_handler(bot, query):
    data = query.data.split("_")
    req = int(data[1])
    offset = int(data[2])
    search = data[3]

    if req not in [query.from_user.id, 0]:
        return await query.answer("यह आपके लिए नहीं है!", show_alert=True)

    await auto_filter(bot, query.message.reply_to_message, query.message, search, offset=offset, is_edit=True)
    await query.answer()

async def suggest_spelling(message, reply_msg, search):
    btn = [[InlineKeyboardButton("🔎 Search Google", url=f"https://www.google.com/search?q={search.replace(' ', '+')}")],
            [InlineKeyboardButton("🚫 Close", callback_data="close_data")]]
    await reply_msg.edit(f"👋 Hello {message.from_user.mention if message.from_user else 'User'},\n\nमुझे डेटाबेस में <b>'{search}'</b> नहीं मिला।", reply_markup=InlineKeyboardMarkup(btn))
