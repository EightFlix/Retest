from datetime import datetime, timedelta

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import ListenerTimeout

from info import ADMINS
from database.users_chats_db import db
from utils import get_readable_time


# ======================================================
# 🧠 HELPERS
# ======================================================

def fmt(dt):
    if isinstance(dt, (int, float)):
        dt = datetime.utcfromtimestamp(dt)
    return dt.strftime("%d %b %Y, %I:%M %p")


# ======================================================
# 🎛 ADMIN PANEL BUTTONS
# ======================================================

def premium_panel_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Add", callback_data="prm_add"),
                InlineKeyboardButton("➖ Remove", callback_data="prm_remove"),
                InlineKeyboardButton("⏳ Extend", callback_data="prm_extend")
            ],
            [
                InlineKeyboardButton("🔍 Check User", callback_data="prm_check")
            ],
            [
                InlineKeyboardButton("⏰ Expiring 3d", callback_data="prm_exp_3"),
                InlineKeyboardButton("⏰ 7d", callback_data="prm_exp_7"),
                InlineKeyboardButton("⏰ 30d", callback_data="prm_exp_30")
            ],
            [
                InlineKeyboardButton("📊 Expiry Chart", callback_data="prm_chart")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
    )


# ======================================================
# 💎 /premium PANEL
# ======================================================

@Client.on_message(filters.command("premium") & filters.user(ADMINS))
async def premium_admin_panel(client, message):
    total = db.premium.count_documents({"plan.premium": True})

    await message.reply(
        (
            "💎 <b>Premium Admin Panel</b>\n\n"
            f"👤 Active Premium : <code>{total}</code>\n"
            f"🕒 Time : <code>{fmt(datetime.utcnow())}</code>"
        ),
        reply_markup=premium_panel_buttons(),
        disable_web_page_preview=True
    )


# ======================================================
# 🔘 CALLBACK HANDLER
# ======================================================

@Client.on_callback_query(filters.regex("^prm_"))
async def premium_callbacks(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Admins only", show_alert=True)

    action = query.data
    now = datetime.utcnow()

    await query.answer()

    # ==================================================
    # ⏰ EXPIRING SOON (3 / 7 / 30)
    # ==================================================
    if action.startswith("prm_exp_"):
        days = int(action.split("_")[-1])
        limit = now + timedelta(days=days)

        users = db.get_premium_users()
        result = []

        for u in users:
            uid = u.get("id")
            if uid in ADMINS:
                continue

            plan = u.get("plan", {})
            expire = plan.get("expire")
            if not expire:
                continue

            if isinstance(expire, (int, float)):
                expire = datetime.utcfromtimestamp(expire)

            if now <= expire <= limit:
                left = int((expire - now).total_seconds())
                result.append(
                    f"👤 <code>{uid}</code> → ⏳ {get_readable_time(left)}"
                )

            if len(result) >= 20:
                break

        if not result:
            return await query.message.edit(
                f"✅ No premium users expiring in next {days} days."
            )

        await query.message.edit(
            f"⏰ <b>Premium Expiring in {days} Days</b>\n\n"
            + "\n".join(result)
        )

    # ==================================================
    # 📊 EXPIRY CHART (TEXT BASED)
    # ==================================================
    elif action == "prm_chart":
        users = db.get_premium_users()

        c_3 = c_7 = c_30 = c_30p = 0

        for u in users:
            uid = u.get("id")
            if uid in ADMINS:
                continue

            plan = u.get("plan", {})
            expire = plan.get("expire")
            if not expire:
                continue

            if isinstance(expire, (int, float)):
                expire = datetime.utcfromtimestamp(expire)

            days_left = (expire - now).days

            if days_left <= 3:
                c_3 += 1
            elif days_left <= 7:
                c_7 += 1
            elif days_left <= 30:
                c_30 += 1
            else:
                c_30p += 1

        await query.message.edit(
            "📊 <b>Premium Expiry Chart</b>\n\n"
            f"🟥 0–3 days   : <code>{c_3}</code>\n"
            f"🟧 4–7 days   : <code>{c_7}</code>\n"
            f"🟨 8–30 days  : <code>{c_30}</code>\n"
            f"🟩 30+ days   : <code>{c_30p}</code>"
        )
