from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.enums import ChatType

from database.users_chats_db import db
from utils import temp


# =====================================================
# 🔐 ADMIN CHECK
# =====================================================
async def is_group_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False


# =====================================================
# ⚙️ SETTINGS UI
# =====================================================
def settings_buttons(settings):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🔍 Search {'✅ ON' if settings.get('search', True) else '❌ OFF'}",
                    callback_data="stg#search"
                )
            ],
            [
                InlineKeyboardButton(
                    f"🔗 Shortlink {'✅ ON' if settings.get('shortlink') else '❌ OFF'}",
                    callback_data="stg#shortlink"
                )
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
    )


# =====================================================
# 📩 /settings COMMAND (GROUP ONLY)
# =====================================================
@Client.on_message(filters.command("settings") & filters.group)
async def settings_cmd(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_group_admin(client, chat_id, user_id):
        return await message.reply("❌ Only group admins can use this command.")

    settings = await db.get_settings(chat_id)

    await message.reply(
        "⚙️ <b>Group Settings</b>\n\n"
        "Configure how this group behaves:",
        reply_markup=settings_buttons(settings),
        quote=True
    )


# =====================================================
# 🔁 SETTINGS CALLBACK
# =====================================================
@Client.on_callback_query(filters.regex("^stg#"))
async def settings_callback(client, query: CallbackQuery):
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    if query.message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await query.answer("Invalid chat", show_alert=True)

    if not await is_group_admin(client, chat_id, user_id):
        return await query.answer("Admins only", show_alert=True)

    action = query.data.split("#")[1]

    settings = await db.get_settings(chat_id)

    # ---- TOGGLES ----
    if action == "search":
        settings["search"] = not settings.get("search", True)

    elif action == "shortlink":
        settings["shortlink"] = not settings.get("shortlink", False)

    # ---- SAVE ----
    await db.save_group_settings(chat_id, settings)
    temp.SETTINGS[chat_id] = settings  # cache update

    await query.message.edit_reply_markup(
        reply_markup=settings_buttons(settings)
    )

    await query.answer("✅ Updated")
