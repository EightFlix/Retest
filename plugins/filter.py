from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_size, is_premium, temp

RESULTS_PER_PAGE = 10


# =====================================================
# 📩 MESSAGE HANDLER
# =====================================================
@Client.on_message(filters.text & filters.incoming & (filters.group | filters.private))
async def filter_handler(client, message):
    if message.text.startswith("/"):
        return

    user_id = message.from_user.id
    search = message.text.strip().lower()

    if len(search) < 2:
        return

    # ---------- GROUP SEARCH CHECK ----------
    if message.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        stg = await db.get_settings(message.chat.id)
        if stg.get("search") is False:
            return

        source_chat_id = message.chat.id
        source_chat_title = message.chat.title

    else:
        source_chat_id = 0
        source_chat_title = "None"

        if user_id not in ADMINS:
            bot_stg = db.get_bot_sttgs()
            if not bot_stg.get("PM_SEARCH", True):
                if not await is_premium(user_id, client):
                    return

    await send_results_pm(
        client,
        user_id,
        search,
        offset=0,
        source_chat_id=source_chat_id,
        source_chat_title=source_chat_title
    )


# =====================================================
# 🔎 PM RESULT SENDER (PAGINATED)
# =====================================================
async def send_results_pm(client, user_id, search, offset, source_chat_id, source_chat_title):
    files, next_offset, total = await get_search_results(
        search,
        offset=offset,
        max_results=RESULTS_PER_PAGE
    )

    if not files:
        return await client.send_message(
            user_id,
            f"❌ <b>No results found for:</b>\n<code>{search}</code>",
            parse_mode=enums.ParseMode.HTML
        )

    start = offset + 1
    end = offset + len(files)

    text = (
        f"✅ <b>Search Results :- {search}</b>\n"
        f"👤 Requested By : <code>{user_id}</code>\n"
        f"⚡ Powered By : {source_chat_title}\n"
        f"🎬 Total File Found : {total}\n\n"
    )

    for f in files:
        size = get_size(f["file_size"])
        link = f"https://t.me/{temp.U_NAME}?start=file_{source_chat_id}_{f['_id']}"
        text += f"📁 <a href='{link}'>[{size}] {f['file_name']}</a>\n"

    text += f"\n📄 Showing <b>{start}-{end}</b> of <b>{total}</b>"

    buttons = []

    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"page#{search}#{offset-RESULTS_PER_PAGE}#{source_chat_id}"
            )
        )

    if next_offset:
        nav.append(
            InlineKeyboardButton(
                "➡️ Next",
                callback_data=f"page#{search}#{offset+RESULTS_PER_PAGE}#{source_chat_id}"
            )
        )

    if nav:
        buttons.append(nav)

    await client.send_message(
        user_id,
        text,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )


# =====================================================
# 🔁 PAGINATION CALLBACK
# =====================================================
@Client.on_callback_query(filters.regex("^page#"))
async def pagination_handler(client, query):
    _, search, offset, source_chat_id = query.data.split("#")
    offset = int(offset)
    source_chat_id = int(source_chat_id)

    if source_chat_id:
        try:
            chat = await client.get_chat(source_chat_id)
            source_chat_title = chat.title
        except:
            source_chat_title = "Unknown"
    else:
        source_chat_title = "None"

    await query.message.delete()

    await send_results_pm(
        client,
        query.from_user.id,
        search,
        offset,
        source_chat_id,
        source_chat_title
    )
