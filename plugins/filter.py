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

# इन-मेमोरी स्टोरेज
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
    short_search = search[:25] 
    
    btn = []
    files_link = ""

    # ✅ फाइल लिस्ट जनरेट करना
    if settings['links']:
        files_link = get_file_list_string(files, message.chat.id, offset=offset+1)
    
    # ✅ बटन मोड
    if not settings['links']:
        for file in files:
            # फाइल नाम से कचरा (h4hBYE>) साफ करना
            clean_name = re.sub(r'^[a-zA-Z0-9]+>', '', file['file_name']).strip()
            if is_prm:
                btn.append([InlineKeyboardButton(f"[{get_size(file['file_size'])}] {clean_name}", callback_data=f"file#{file['_id']}")])
            else:
                f_link = await get_shortlink(settings['url'], settings['api'], f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}")
                btn.append([InlineKeyboardButton(f"⚡ [{get_size(file['file_size'])}] {clean_name}", url=f_link)])

    # ✅ पेजिनेशन बटन्स
    pagination_row = []
    if offset != 0:
        pagination_row.append(InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{int(offset)-MAX_BTN}_{short_search}"))
    
    pagination_row.append(InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(int(total) / MAX_BTN)}", callback_data="pages"))
    
    if n_offset != "":
        pagination_row.append(InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{n_offset}_{short_search}"))
    
    btn.append(pagination_row)
    
    btn.insert(0, [
        InlineKeyboardButton("🌐 ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"filter_menu#lang#{req}#{offset}#{short_search}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"filter_menu#qual#{req}#{offset}#{short_search}")
    ])

    if not is_prm:
        btn.append([InlineKeyboardButton('🤑 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ', url=f"https://t.me/{temp.U_NAME}?start=premium")])

    # ✅ स्पीड फिक्स: अगर पेज बदल रहे हैं (is_edit), तो IMDb दोबारा लोड न करें
    if is_edit:
        cap = f"<b>💭 ʜᴇʏ,\n♻️ ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ {search}...</b>"
        poster = None
    else:
        cap, poster = await get_imdb_metadata(search, files, settings)
    
    full_caption = cap + (files_link if files_link else "")

    if is_edit:
        try:
            # edit_text ज्यादा तेज काम करता है
            await reply_msg.edit_text(text=full_caption[:4096], reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except: pass
    else:
        await send_metadata_reply(message, cap, poster, InlineKeyboardMarkup(btn), settings, files_link)
        await reply_msg.delete()

# --- CALLBACK HANDLERS ---

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
    # यहाँ भी is_edit=True रखें ताकि पोस्टर दोबारा लोड न हो
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
