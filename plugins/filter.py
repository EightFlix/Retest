import re
import math
import time
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, MAX_BTN, LANGUAGES, QUALITY
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from utils import get_settings, get_size, is_premium, temp

# ===================== ⚡ SAFE CACHE =====================
SEARCH_CACHE = {}     # key -> (files, n_offset, total, ts)
CACHE_TTL = 45        # seconds

RE_CLEAN = re.compile(r"[-:\"';!]")
RE_SPACE = re.compile(r"\s+")

# ===================== 📩 MESSAGE HANDLER =====================
@Client.on_message(filters.text & filters.incoming & (filters.group | filters.private))
async def filter_handler(client, message):
    if message.text.startswith("/"):
        return

    user_id = message.from_user.id

    # ---- PM Search permission ----
    if message.chat.type == enums.ChatType.PRIVATE:
        is_prm = await is_premium(user_id, client)
        if user_id not in ADMINS and not is_prm:
            stg = db.get_bot_sttgs()
            if not stg.get("PM_SEARCH", True):
                return await message.reply_text(
                    "<b>❌ PM search disabled</b>\n\nOnly premium users can search in PM."
                )

    # ---- Clean + normalize search ----
    search = RE_SPACE.sub(
        " ",
        RE_CLEAN.sub(" ", message.text)
    ).strip().lower()

    if not search or len(search) < 2:
        return

    await auto_filter(client, message, None, search)

# ===================== 🔎 AUTO FILTER =====================
async def auto_filter(client, message, reply_msg, search, offset=0, is_edit=False):
    cache_key = f"{search}:{offset}"
    cached = SEARCH_CACHE.get(cache_key)

    # ---- CACHE ----
    if cached and time.time() - cached[3] < CACHE_TTL:
        files, n_offset, total = cached[:3]
    else:
        files, n_offset, total = await get_search_results(search, offset)
        if files:
            SEARCH_CACHE[cache_key] = (files, n_offset, total, time.time())

    if not files:
        return await message.reply_text(f"❌ <b>{search}</b> नहीं मिला")

    req = message.from_user.id
    short_search = search[:25]

    buttons = []

    # ================= FILE RESULTS (LINK MODE ONLY) =================
    for file in files:
        clean_name = re.sub(r'^[a-zA-Z0-9]+>', '', file['file_name']).strip()
        f_size = get_size(file['file_size'])

        link = f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}"

        buttons.append([
            InlineKeyboardButton(
                f"📁 [{f_size}] {clean_name}",
                url=link
            )
        ])

    # ================= PAGINATION =================
    page_btn = []

    if offset > 0:
        page_btn.append(
            InlineKeyboardButton(
                "« BACK",
                callback_data=f"next_{req}_{offset-MAX_BTN}_{short_search}"
            )
        )

    page_btn.append(
        InlineKeyboardButton(
            f"{offset//MAX_BTN + 1}/{math.ceil(total/MAX_BTN)}",
            callback_data="pages"
        )
    )

    if n_offset:
        page_btn.append(
            InlineKeyboardButton(
                "NEXT »",
                callback_data=f"next_{req}_{n_offset}_{short_search}"
            )
        )

    buttons.append(page_btn)

    # ================= FILTER BUTTONS =================
    buttons.insert(0, [
        InlineKeyboardButton("🌐 LANGUAGE", callback_data=f"filter_menu#lang#{req}#{offset}#{short_search}"),
        InlineKeyboardButton("🔍 QUALITY", callback_data=f"filter_menu#qual#{req}#{offset}#{short_search}")
    ])

    caption = (
        f"<b>HEY 👋</b>\n"
        f"♻️ Here I found results for:\n"
        f"<code>{search}</code>"
    )

    if is_edit:
        await reply_msg.edit_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

# ===================== 🔁 CALLBACK HANDLER =====================
@Client.on_callback_query(filters.regex(r"^(next|filter_menu|apply_filter)"))
async def cb_handler(client, query):
    data = query.data

    if data.startswith("next"):
        _, req, offset, search = data.split("_")
        if int(req) != query.from_user.id:
            return await query.answer("❌ Not for you", show_alert=True)

        await auto_filter(
            client,
            query.message.reply_to_message,
            query.message,
            search,
            int(offset),
            True
        )

    elif data.startswith("filter_menu"):
        _, ftype, req, offset, search = data.split("#")
        items = LANGUAGES if ftype == "lang" else QUALITY
        btn = []

        for i in range(0, len(items), 2):
            row = [
                InlineKeyboardButton(
                    items[i].title(),
                    callback_data=f"apply_filter#{items[i]}#{search}#{offset}#{req}"
                )
            ]
            if i + 1 < len(items):
                row.append(
                    InlineKeyboardButton(
                        items[i + 1].title(),
                        callback_data=f"apply_filter#{items[i + 1]}#{search}#{offset}#{req}"
                    )
                )
            btn.append(row)

        btn.append([
            InlineKeyboardButton("⪻ BACK", callback_data=f"next_{req}_{offset}_{search}")
        ])

        await query.message.edit_text(
            f"<b>Select {ftype.title()}</b>",
            reply_markup=InlineKeyboardMarkup(btn)
        )

    elif data.startswith("apply_filter"):
        _, choice, search, offset, req = data.split("#")
        if int(req) != query.from_user.id:
            return await query.answer("❌ Not for you", show_alert=True)

        await auto_filter(
            client,
            query.message.reply_to_message,
            query.message,
            f"{search} {choice}",
            0,
            True
        )

    await query.answer()
