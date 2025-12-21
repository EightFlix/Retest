import qrcode
from io import BytesIO
from datetime import datetime, timedelta

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import ListenerTimeout

from info import (
    ADMINS,
    IS_PREMIUM,
    PRE_DAY_AMOUNT,
    UPI_ID,
    UPI_NAME,
    RECEIPT_SEND_USERNAME,
)

from database.users_chats_db import db
from utils import is_premium

# ======================================================
# 🔧 HELPERS
# ======================================================

def format_time(dt: datetime) -> str:
    return dt.strftime("%d %b %Y, %I:%M %p")


def parse_duration(text: str):
    text = text.lower().strip()
    num = int("".join(filter(str.isdigit, text)) or 0)

    if num <= 0:
        return None
    if "min" in text:
        return timedelta(minutes=num)
    if "hour" in text or "hr" in text:
        return timedelta(hours=num)
    if "day" in text:
        return timedelta(days=num)
    if "month" in text:
        return timedelta(days=30 * num)
    if "year" in text:
        return timedelta(days=365 * num)
    return None


def user_buttons(is_prm: bool):
    if is_prm:
        return None
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Buy Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("📨 Request Trial", callback_data="request_trial")],
        ]
    )


# ======================================================
# 👤 USER COMMANDS
# ======================================================

@Client.on_message(filters.command("plan") & filters.private)
async def plan_cmd(_, message):
    if not IS_PREMIUM:
        return await message.reply("⚠️ Premium system is currently disabled.")

    if message.from_user.id in ADMINS:
        return await message.reply(
            "👑 **Admin Access**\n\n"
            "You have lifetime premium access.\n"
            "No expiry. No limits. 🚀"
        )

    premium = await is_premium(message.from_user.id, message._client)

    await message.reply(
        "💎 **Premium Plans**\n\n"
        "Upgrade to premium and enjoy:\n"
        "🚀 Faster Access\n"
        "🔓 No Ads\n"
        "📩 PM Search Enabled\n",
        reply_markup=user_buttons(premium),
    )


@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(_, message):
    if message.from_user.id in ADMINS:
        return await message.reply(
            "👑 **Admin Plan**\nPlan: Lifetime Premium\nExpires: Never"
        )

    if not await is_premium(message.from_user.id, message._client):
        return await message.reply(
            "❌ You do not have an active premium plan.\nUse /plan to upgrade."
        )

    mp = db.get_plan(message.from_user.id)
    await message.reply(
        "🎉 **Premium Active**\n\n"
        f"💎 Plan: {mp.get('plan','Premium')}\n"
        f"⏰ Valid Till: {format_time(mp['expire'])}"
    )


# ======================================================
# 📨 TRIAL REQUEST
# ======================================================

@Client.on_callback_query(filters.regex("^request_trial$"))
async def trial_request(_, query: CallbackQuery):
    await query.answer("Trial request sent to admin.", show_alert=True)

    await query.message.edit(
        "📨 **Trial Requested**\n\n"
        "Your request has been sent to the admin.\n"
        "You will be notified if approved."
    )

    await query._client.send_message(
        ADMINS[0],
        f"#TrialRequest\n"
        f"👤 User: {query.from_user.mention}\n"
        f"🆔 ID: `{query.from_user.id}`"
    )


# ======================================================
# 💰 BUY / RENEW PREMIUM
# ======================================================

@Client.on_callback_query(filters.regex("^buy_premium$"))
async def buy_premium(_, query: CallbackQuery):
    # cleanup reminders hook
    db.update_plan(query.from_user.id, {
        "last_msg_id": None,
        "last_reminder": None
    )

    # One-click renew support
    last_plan = db.get_plan(query.from_user.id).get("last_plan")

    ask = (
        f"⏳ **Choose Premium Duration**\n\n"
        f"{'Last Plan: ' + last_plan + '\\n' if last_plan else ''}"
        "Send duration like:\n"
        "`10 minutes`\n"
        "`3 hours`\n"
        "`7 days`\n"
        "`1 month`\n"
        "`1 year`"
    )

    await query.message.edit(ask)

    try:
        msg = await query._client.listen(
            chat_id=query.message.chat.id,
            user_id=query.from_user.id,
            timeout=300,
        )
        duration = parse_duration(msg.text)
        if not duration:
            raise ValueError
    except (ListenerTimeout, ValueError):
        return await query.message.reply("❌ Invalid or timed out. Try again.")

    days = max(1, duration.days)
    amount = days * PRE_DAY_AMOUNT

    db.update_plan(query.from_user.id, {"last_plan": msg.text})

    upi = (
        f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}"
        f"&am={amount}&cu=INR&tn=Premium for {query.from_user.id}"
    )

    qr = qrcode.make(upi)
    bio = BytesIO()
    qr.save(bio, "PNG")
    bio.seek(0)

    await query.message.reply_photo(
        bio,
        caption=(
            "💰 **Complete Payment**\n\n"
            f"🕒 Plan: {msg.text}\n"
            f"💵 Amount: ₹{amount}\n\n"
            "Scan the QR and send the payment screenshot."
        ),
    )

    try:
        receipt = await query._client.listen(
            chat_id=query.message.chat.id,
            user_id=query.from_user.id,
            timeout=600,
        )
        if not receipt.photo:
            raise ValueError
    except Exception:
        return await query.message.reply("❌ Screenshot not received.")

    await receipt.reply("✅ Screenshot received.\n⏳ Waiting for admin approval.")

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Payment Received", callback_data=f"pay_ok#{query.from_user.id}"),
            InlineKeyboardButton("❌ Payment Not Received", callback_data=f"pay_no#{query.from_user.id}")
        ]]
    )

    await query._client.send_photo(
        RECEIPT_SEND_USERNAME,
        receipt.photo.file_id,
        caption=(
            "#PremiumPayment\n"
            f"👤 User: {query.from_user.mention}\n"
            f"🆔 ID: `{query.from_user.id}`\n"
            f"💵 Amount: ₹{amount}\n"
            f"📦 Requested: {msg.text}"
        ),
        reply_markup=buttons,
    )


# ======================================================
# 🛂 ADMIN DECISION
# ======================================================

@Client.on_callback_query(filters.regex("^pay_ok"))
async def admin_ok(_, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    user_id = int(query.data.split("#")[1])

    await query.message.reply(
        "⏳ **Activate Premium**\n\n"
        "Send duration like:\n"
        "`1 day`, `1 month`, `1 year`, `3 hours`"
    )

    try:
        msg = await query._client.listen(
            chat_id=query.message.chat.id,
            user_id=query.from_user.id,
            timeout=300,
        )
        duration = parse_duration(msg.text)
        if not duration:
            raise ValueError
    except Exception:
        return await query.message.reply("❌ Invalid duration.")

    now = datetime.utcnow()
    expire = now + duration

    db.update_plan(
        user_id,
        {
            "premium": True,
            "plan": msg.text,
            "activated_at": now,
            "expire": expire,
            "last_msg_id": None,
            "last_reminder": None,
        },
    )

    await query._client.send_message(
        user_id,
        "🎉 **Premium Activated!**\n\n"
        f"💎 Plan: {msg.text}\n"
        f"🕒 Activated At: {format_time(now)}\n"
        f"⏰ Valid Till: {format_time(expire)}",
    )

    await query.message.edit("✅ Premium activated successfully.")


@Client.on_callback_query(filters.regex("^pay_no"))
async def admin_no(_, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    user_id = int(query.data.split("#")[1])

    await query._client.send_message(
        user_id,
        "❌ **Payment Not Received**\n\n"
        "If you have paid, please contact the admin 📩",
    )

    await query.message.edit("❌ Payment marked as not received.")
