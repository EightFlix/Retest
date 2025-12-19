import re
import math
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import ADMINS, MAX_BTN, SPELL_CHECK, script, PROTECT_CONTENT
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
    
    if message.chat.type == enums.ChatType.PRIVATE:
        stg = db.get_bot_sttgs()
        if stg and not stg.get('PM_SEARCH'):
            return await message.reply_text('PM search is disabled by Admin!')

    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    if not search: return

    reply_msg = await message.reply_text(f"<b><i>🔍 `{search}` सर्च किया जा रहा है...</i></b>")
    await auto_filter(client, message, reply_msg, search)

async def auto_filter(client, message, reply_msg, search, offset=0):
    settings = await get_settings(message.chat.id)
    files, n_offset, total = await get_search_results(search, offset=offset)

    if not files:
        if settings["spell_check"]:
            return await suggest_spelling(message, reply_msg, search)
        else:
            return await reply_msg.edit(f"क्षमा करें, `{search}` नहीं मिला।")

    req = message.from_user.id if message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search

    btn = []
    if settings['links']:
        files_link = get_file_list_string(files, message.chat.id)
    else:
        files_link = ""
        for file in files:
            btn.append([InlineKeyboardButton(f"[{get_size(file['file_size'])}] {file['file_name']}", callback_data=f"file#{file['_id']}")])

    # पेजिनेशन बटन (Next/Back)
    if n_offset != "":
        btn.append([
            InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(int(total) / MAX_BTN)}", callback_data="pages"),
            InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    elif offset != 0:
        btn.append([
            InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(int(total) / MAX_BTN)}", callback_data="pages"),
            InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{int(offset)-MAX_BTN}")
        ])

    btn.insert(0, [
        InlineKeyboardButton("🌐 ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#{req}#{offset}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"qualities#{key}#{req}#{offset}")
    ])

    btn.append([InlineKeyboardButton('🤑 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ', url=f"https://t.me/{temp.U_NAME}?start=premium")])

    cap, poster = await get_imdb_metadata(search, files, settings)
    await send_metadata_reply(message, cap, poster, InlineKeyboardMarkup(btn), settings, files_link)
    await reply_msg.delete()

async def suggest_spelling(message, reply_msg, search):
    btn = [[
        InlineKeyboardButton("🔎 Search Google", url=f"https://www.google.com/search?q={search.replace(' ', '+')}")
    ],[
        InlineKeyboardButton("🚫 Close", callback_data="close_data")
    ]]
    await reply_msg.edit(
        f"👋 Hello {message.from_user.mention if message.from_user else 'User'},\n\nमुझे डेटाबेस में <b>'{search}'</b> नहीं मिला।",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page_handler(bot, query: CallbackQuery):
    _, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("यह आपके लिए नहीं है!", show_alert=True)

    search = BUTTONS.get(key)
    if not search: 
        return await query.answer("पुरानी रिक्वेस्ट है, फिर से सर्च करें।", show_alert=True)

    # पुराने मैसेज को डिलीट करके नया रिजल्ट दिखाने के लिए
    await query.message.delete()
    reply_msg = await query.message.reply_text("<b><i>लोड हो रहा है...</i></b>")
    
    # ओरिजिनल मैसेज का रेफरेंस देने के लिए
    orig_msg = query.message.reply_to_message
    await auto_filter(bot, orig_msg, reply_msg, search, offset=int(offset))

