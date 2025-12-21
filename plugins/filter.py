from hydrogram import Client, filters, enums
from info import ADMINS
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_size, is_premium, temp

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

    # ---------------- GROUP SEARCH BLOCK ----------------
    if message.chat.type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
        stg = await db.get_settings(message.chat.id)
        if stg.get("search") is False:
            return

    # ---------------- PM PREMIUM CHECK ----------------
    if message.chat.type == enums.ChatType.PRIVATE:
        if user_id not in ADMINS:
            bot_stg = db.get_bot_sttgs()
            if not bot_stg.get("PM_SEARCH", True):
                if not await is_premium(user_id, client):
                    return

    await send_results(client, message, search)


# =====================================================
# 🔎 RESULT SENDER (LINK MODE ONLY)
# =====================================================
async def send_results(client, message, search):
    files, _, _ = await get_search_results(search)

    if not files:
        return await message.reply_text(
            f"❌ <b>No results found for:</b>\n<code>{search}</code>",
            parse_mode=enums.ParseMode.HTML
        )

    text = (
        f"<b>♻️ Results for:</b>\n"
        f"<code>{search}</code>\n\n"
    )

    for f in files:
        name = f["file_name"]
        size = get_size(f["file_size"])
        link = f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{f['_id']}"

        text += f"📁 <a href='{link}'>[{size}] {name}</a>\n"

    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
        quote=True
    )
