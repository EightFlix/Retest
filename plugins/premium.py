import qrcode
import secrets
import asyncio
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
# 🔧 CONFIG
# ======================================================

REMINDER_STEPS = [
    ("12h", timedelta(hours=12)),
    ("6h", timedelta(hours=6)),
    ("3h", timedelta(hours=3)),
    ("1h", timedelta(hours=1)),
    ("10m", timedelta(minutes=10)),
]

# ======================================================
# 🧠 HELPERS
# ======================================================

def fmt(dt: datetime) -> str:
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

def gen_invoice_id():
    return "PRM-" + secrets.token_hex(3).upper()

def buy_button():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💰 Buy / Renew Premium", callback_data="buy_premium")]]
    )

# ======================================================
# 👤 USER COMMANDS
# ======================================================

@Client.on_message(filters.command("plan") & filters.private)
async def plan_cmd(_, message):
    if not IS_PREMIUM:
        return await message.reply("⚠️ Premium system is disabled.")

    if message.from_user.id in ADMINS:
        return await message.reply("👑 Admin = Lifetime Premium")

    if await is_premium(message.from_user.id, message._client):
        return await message.reply("✅ Premium already active.\nUse /myplan")

    await message.reply(
        "💎 **Premium Benefits**\n\n"
        "🚀 Faster search\n"
        "📩 PM Search access\n"
        "🔕 No ads\n",
        reply_markup=buy_button()
    )

@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(_, message):
    if message.from_user.id in ADMINS:
        return await message.reply("👑 Lifetime Premium")

    plan = db.get_plan(message.from_user.id)
    if not plan.get("premium"):
        return await message.reply("❌ No active premium plan.")

    await message.reply(
        "🎉 **Premium Active**\n\n"
        f"💎 Plan: {plan.get('plan')}\n"
        f"⏰ Valid Till: {fmt(plan.get('expire'))}"
    )

# ======================================================
# 🧾 INVOICE / HISTORY
# ======================================================

@Client.on_message(filters.command("invoice") & filters.private)
async def invoice_cmd(_, message):
    plan = db.get_plan(message.from_user.id)
    invoices = plan.get("invoices", [])

    if not invoices:
        return await message.reply("❌ No invoices found.")

    if len(message.command) > 1 and message.command[1] == "history":
        text = "🧾 **Invoice History**\n\n"
        for inv in invoices[-5:][::-1]:
            text += (
                f"• `{inv['id']}` | ₹{inv['amount']} | {inv['plan']}\n"
            )
        return await message.reply(text)

    inv = invoices[-1]
    await message.reply(
        "🧾 **Latest Invoice**\n\n"
        f"🆔 ID: `{inv['id']}`\n"
        f"💎 Plan: {inv['plan']}\n"
        f"💰 Amount: ₹{inv['amount']}\n"
        f"⏰ Expire: {inv['expire']}"
    )

# ======================================================
# 💰 BUY / RENEW FLOW
# ======================================================

@Client.on_callback_query(filters.regex("^buy_premium$"))
async def buy_premium(_, query: CallbackQuery):
    await query.message.edit(
        "⏳ **Send duration**\n\n"
        "`1 day`\n`7 days`\n`1 month`\n`1 year`"
    )

    try:
        msg = await query._client.listen(
            chat_id=query.message.chat.id,
            user_id=query.from_user.id,
            timeout=300
        )
        duration = parse_duration(msg.text)
        if not duration:
            raise ValueError
    except (ListenerTimeout, ValueError):
        return await query.message.reply("❌ Invalid duration.")

    days = max(1, duration.days)
    amount = days * PRE_DAY_AMOUNT

    upi = (
        f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}"
        f"&am={amount}&cu=INR"
    )

    qr = qrcode.make(upi)
    bio = BytesIO()
    qr.save(bio, "PNG")
    bio.seek(0)

    await query.message.reply_photo(
        bio,
        caption=(
            "💰 **Payment Details**\n\n"
            f"📦 Plan: {msg.text}\n"
            f"💵 Amount: ₹{amount}\n\n"
            "Send payment screenshot after paying."
        )
    )

    try:
        receipt = await query._client.listen(
            chat_id=query.message.chat.id,
            user_id=query.from_user.id,
            timeout=600
        )
        if not receipt.photo:
            raise ValueError
    except Exception:
        return await query.message.reply("❌ Screenshot not received.")

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Approve", callback_data=f"pay_ok#{query.from_user.id}#{msg.text}#{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"pay_no#{query.from_user.id}")
        ]]
    )

    await query._client.send_photo(
        RECEIPT_SEND_USERNAME,
        receipt.photo.file_id,
        caption=(
            "#PremiumPayment\n"
            f"👤 User: `{query.from_user.id}`\n"
            f"📦 Plan: {msg.text}\n"
            f"💰 Amount: ₹{amount}"
        ),
        reply_markup=buttons
    )

    await receipt.reply("✅ Screenshot sent to admin. Please wait.")

# ======================================================
# 🛂 ADMIN APPROVAL
# ======================================================

@Client.on_callback_query(filters.regex("^pay_ok#"))
async def admin_approve(_, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    _, uid, plan_txt, amount = query.data.split("#")
    uid = int(uid)
    amount = int(amount)

    duration = parse_duration(plan_txt)
    if not duration:
        return await query.message.edit("❌ Invalid plan.")

    now = datetime.utcnow()
    expire = now + duration

    invoice = {
        "id": gen_invoice_id(),
        "plan": plan_txt,
        "amount": amount,
        "activated": fmt(now),
        "expire": fmt(expire),
        "created_at": now
    }

    old = db.get_plan(uid)
    invoices = old.get("invoices", [])
    invoices.append(invoice)

    db.update_plan(uid, {
        "premium": True,
        "plan": plan_txt,
        "expire": expire,
        "activated_at": now,
        "invoices": invoices,
        "trial": False,
        "last_reminder": None,
        "last_msg_id": None
    })

    await query._client.send_message(
        uid,
        "🎉 **Premium Activated**\n\n"
        f"💎 Plan: {plan_txt}\n"
        f"⏰ Valid Till: {fmt(expire)}"
    )

    await query.message.edit("✅ Premium approved & activated.")

@Client.on_callback_query(filters.regex("^pay_no#"))
async def admin_reject(_, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    uid = int(query.data.split("#")[1])

    await query._client.send_message(
        uid,
        "❌ **Payment Rejected**\n\n"
        "If you have paid, contact admin."
    )
    await query.message.edit("❌ Payment rejected.")
