import random
import time
from datetime import timedelta

from hydrogram import Client, filters
from hydrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    InputMediaPhoto
)

from info import (
    ADMINS,
    PICS,
    URL,
    BIN_CHANNEL,
    QUALITY,
    LANGUAGES,
    script
)

from utils import is_premium, get_wish, temp
from database.users_chats_db import db
from database.ia_filterdb import db_count_documents


# ======================================================
# 🔘 UI HELPERS (CLEAN & MINIMAL)
# ======================================================

def start_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "+ Add Me To Your Group +",
                    url=f"https://t.me/{temp.U_NAME}?startgroup=start"
                )
            ],
            [
                InlineKeyboardButton("👨‍🚒 Help", callback_data="help"),
                InlineKeyboardButton("📚 About", callback_data="about")
            ]
        ]
    )


def back_btn(cb="start"):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("« Back", callback_data=cb)]]
    )


# ======================================================
# 🚀 /START
# ======================================================

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)

    await message.reply_photo(
        photo=random.choice(PICS),
        caption=script.START_TXT.format(
            message.from_user.mention,
            get_wish()
        ),
        reply_markup=start_buttons()
    )


# ======================================================
# 🔁 CALLBACK HANDLER
# ======================================================

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    uid = query.from_user.id

    # ---------------- CLOSE ----------------
    if data == "close_data":
        await query.answer("Closed")
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except:
            pass
        return

    # ---------------- IGNORE ----------------
    if data == "pages":
        return await query.answer()

    # ---------------- STREAM (PREMIUM) ----------------
    if data.startswith("stream#"):
        if not await is_premium(uid, client):
            return await query.answer(
                "🔒 Premium only feature.\nUse /plan to upgrade.",
                show_alert=True
            )

        file_id = data.split("#", 1)[1]
        msg = await client.send_cached_media(
            chat_id=BIN_CHANNEL,
            file_id=file_id
        )

        watch = f"{URL}watch/{msg.id}"
        download = f"{URL}download/{msg.id}"

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("▶️ Watch Online", url=watch),
                        InlineKeyboardButton("⬇️ Fast Download", url=download)
                    ],
                    [InlineKeyboardButton("❌ Close", callback_data="close_data")]
                ]
            )
        )
        return await query.answer("Links ready")

    # ---------------- HELP ----------------
    if data == "help":
        return await query.message.edit_media(
            InputMediaPhoto(
                random.choice(PICS),
                caption=script.HELP_TXT.format(query.from_user.mention)
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👤 User Commands", callback_data="user_cmds"),
                        InlineKeyboardButton("🛡️ Admin Commands", callback_data="admin_cmds")
                    ],
                    [InlineKeyboardButton("« Back", callback_data="start")]
                ]
            )
        )

    if data == "user_cmds":
        return await query.message.edit_caption(
            script.USER_COMMAND_TXT,
            reply_markup=back_btn("help")
        )

    if data == "admin_cmds":
        if uid not in ADMINS:
            return await query.answer("Admins only", show_alert=True)

        return await query.message.edit_caption(
            script.ADMIN_COMMAND_TXT,
            reply_markup=back_btn("help")
        )

    # ---------------- ABOUT ----------------
    if data == "about":
        return await query.message.edit_media(
            InputMediaPhoto(
                random.choice(PICS),
                caption=script.MY_ABOUT_TXT
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("📊 Stats", callback_data="stats_callback"),
                        InlineKeyboardButton("👤 Owner", callback_data="owner_info")
                    ],
                    [InlineKeyboardButton("« Back", callback_data="start")]
                ]
            )
        )

    if data == "owner_info":
        return await query.message.edit_caption(
            script.MY_OWNER_TXT,
            reply_markup=back_btn("about")
        )

    # ---------------- BACK TO START ----------------
    if data == "start":
        return await query.message.edit_media(
            InputMediaPhoto(
                random.choice(PICS),
                caption=script.START_TXT.format(
                    query.from_user.mention,
                    get_wish()
                )
            ),
            reply_markup=start_buttons()
        )

    # ---------------- SMART GROUPING (QUALITY UI HOOK) ----------------
    if data.startswith("group_quality#"):
        _, search, req = data.split("#")
        if int(req) != uid:
            return await query.answer(
                "This result is not for you",
                show_alert=True
            )

        btn = []
        for i in range(0, len(QUALITY), 2):
            row = [
                InlineKeyboardButton(
                    QUALITY[i].upper(),
                    callback_data=f"apply_quality#{QUALITY[i]}#{search}#{req}"
                )
            ]
            if i + 1 < len(QUALITY):
                row.append(
                    InlineKeyboardButton(
                        QUALITY[i + 1].upper(),
                        callback_data=f"apply_quality#{QUALITY[i + 1]}#{search}#{req}"
                    )
                )
            btn.append(row)

        btn.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])

        return await query.message.edit_text(
            "<b>Select Quality 👇</b>",
            reply_markup=InlineKeyboardMarkup(btn)
        )

    # ---------------- ADMIN STATS (POPUP) ----------------
    if data == "stats_callback":
        if uid not in ADMINS:
            return await query.answer("Admins only", show_alert=True)

        files = db_count_documents()
        users = await db.total_users_count()
        uptime = str(
            timedelta(seconds=int(time.time() - temp.START_TIME))
        )

        return await query.answer(
            f"📊 Files: {files}\n"
            f"👥 Users: {users}\n"
            f"⏱ Uptime: {uptime}",
            show_alert=True
        )

    # ---------------- FALLBACK ----------------
    await query.answer("Unknown action")
