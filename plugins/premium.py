import qrcode
import secrets
import asyncio
from io import BytesIO
from datetime import datetime, timedelta

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import ListenerTimeout, FloodWait

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
# ⚙️ CONFIG
# ======================================================

LISTEN_SHORT = 180   # 3 min
LISTEN_LONG = 300    # 5 min

active_sessions = set()


# ======================================================
# 🧠 HELPERS
# ======================================================

def fmt(dt):
    if isinstance(dt, (int, float)):
        dt = datetime.utcfromtimestamp(dt)
    return dt.strftime("%d %b %Y, %I:%M %p")


def parse_duration(text: str):
    if not text:
        return None

    text = text.lower()
    num = int("".join(filter(str.isdigit, text)) or 0)
    if num <= 0:
        return None

    if "day" in text:
        return timedelta(days=num)
    if "month" in text:
        return timedelta(days=30 * num)
    if "year" in text:
        return timedelta(days=365 * num)
    if "hour" in text:
        return timedelta(hours=num)

    return None


def gen_invoice_id():
    return "PRM-" + secrets.token_hex(3).upper()


def buy_btn():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💰 Buy / Renew Premium", callback_data="buy_premium")]]
    )


def cancel_btn():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]]
    )


# ======================================================
# 👤 USER COMMANDS
# ======================================================

@Client.on_message(filters.command("plan") & filters.private)
async def plan_cmd(client, message):
    if not IS_PREMIUM:
        return await message.reply("⚠️ Premium system disabled")

    uid = message.from_user.id

    if uid in ADMINS:
        return await message.reply("👑 Admin = Lifetime Premium")

    premium = await is_premium(uid, client)

    text = f"""
💎 **Premium Benefits**

🚀 Faster search  
📩 PM Search  
🔕 No ads  
⚡ Instant files  
🎯 Priority support  

💰 **Price:** ₹{PRE_DAY_AMOUNT}/day
"""

    if premium:
        text += "\n✅ **You already have Premium**\nYou can renew or extend your plan."

    await message.reply(text, reply_markup=buy_btn())


@Client.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client, message):
    uid = message.from_user.id

    if uid in ADMINS:
        return await message.reply("👑 Admin = Lifetime Premium")

    plan = await db.get_plan(uid)

    if not plan or not plan.get("premium"):
        return await message.reply(
            "❌ No active premium plan",
            reply_markup=buy_btn()
        )

    expire = plan.get("expire")
    exp_dt = datetime.utcfromtimestamp(expire) if isinstance(expire, (int, float)) else expire
    remaining = exp_dt - datetime.utcnow()

    await message.reply(
        f"""
🎉 **Premium Active**

💎 Plan   : {plan.get("plan")}
⏰ Expire : {fmt(exp_dt)}
⏳ Left   : {max(0, remaining.days)} days
""",
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("🔄 Renew", callback_data="buy_premium"),
                InlineKeyboardButton("🧾 Invoices", callback_data="show_invoices")
            ]]
        )
    )


@Client.on_message(filters.command("invoice") & filters.private)
async def invoice_cmd(client, message):
    plan = await db.get_plan(message.from_user.id)
    invoices = plan.get("invoices", []) if plan else []

    if not invoices:
        return await message.reply("❌ No invoices found")

    inv = invoices[-1]

    await message.reply(
        f"""
🧾 **Latest Invoice**

🆔 **ID:** `{inv.get('id')}`
💎 **Plan:** {inv.get('plan')}
💰 **Amount:** ₹{inv.get('amount')}
⏰ **Expire:** {inv.get('expire')}
""",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📜 Invoice History", callback_data="show_invoices")]]
        )
    )


@Client.on_callback_query(filters.regex("^show_invoices$"))
async def show_invoice_cb(client, query: CallbackQuery):
    plan = await db.get_plan(query.from_user.id)
    invoices = plan.get("invoices", []) if plan else []

    if not invoices:
        return await query.answer("No invoices found", show_alert=True)

    text = "🧾 **Invoice History**\n\n"
    for inv in invoices[-10:][::-1]:
        text += f"• `{inv.get('id')}` | ₹{inv.get('amount')} | {inv.get('plan')}\n"

    await query.message.edit(text)


# ======================================================
# 💰 BUY FLOW
# ======================================================

@Client.on_callback_query(filters.regex("^buy_premium$"))
async def buy_premium(client, query: CallbackQuery):
    uid = query.from_user.id

    if uid in active_sessions:
        return await query.answer("⚠️ Already in process", show_alert=True)

    active_sessions.add(uid)

    await query.message.edit(
        "🕒 Send duration like:\n`1 day`, `7 days`, `1 month`, `1 year`",
        reply_markup=cancel_btn()
    )

    try:
        msg = await client.listen(query.message.chat.id, uid, timeout=LISTEN_SHORT)
        duration = parse_duration(msg.text)
        if not duration:
            raise ValueError
    except Exception:
        active_sessions.discard(uid)
        return await query.message.reply("❌ Invalid duration")

    days = max(1, duration.days)
    amount = days * PRE_DAY_AMOUNT

    upi = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
    qr = qrcode.make(upi)
    bio = BytesIO()
    qr.save(bio, "PNG")
    bio.seek(0)

    await query.message.reply_photo(
        bio,
        caption=f"""
💰 **Payment Details**

📦 Plan   : {msg.text}
💵 Amount : ₹{amount}

📸 Send payment screenshot
""",
        reply_markup=cancel_btn()
    )

    try:
        receipt = await client.listen(query.message.chat.id, uid, timeout=LISTEN_LONG)
        if not receipt.photo:
            raise ValueError
    except Exception:
        active_sessions.discard(uid)
        return await query.message.reply("❌ Screenshot not received")

    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Approve", callback_data=f"pay_ok#{uid}#{msg.text}#{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"pay_no#{uid}")
        ]]
    )

    await client.send_photo(
        RECEIPT_SEND_USERNAME,
        receipt.photo.file_id,
        caption=f"""
#PremiumPayment

User ID : {uid}
Plan    : {msg.text}
Amount  : ₹{amount}
""",
        reply_markup=buttons
    )

    await receipt.reply("✅ Screenshot sent for approval")
    active_sessions.discard(uid)


@Client.on_callback_query(filters.regex("^cancel_payment$"))
async def cancel_payment(_, query: CallbackQuery):
    active_sessions.discard(query.from_user.id)
    await query.message.edit("❌ Payment cancelled")


# ======================================================
# 🛂 ADMIN APPROVAL
# ======================================================

@Client.on_callback_query(filters.regex("^pay_ok#"))
async def approve_payment(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    _, uid, plan_txt, amount = query.data.split("#")
    uid = int(uid)
    amount = int(amount)

    duration = parse_duration(plan_txt)
    if not duration:
        return await query.message.edit("❌ Invalid plan duration")

    now = datetime.utcnow()
    old = await db.get_plan(uid) or {}

    expire = old.get("expire")
    if expire:
        expire = datetime.utcfromtimestamp(expire)
        expire = expire + duration if expire > now else now + duration
    else:
        expire = now + duration

    invoice = {
        "id": gen_invoice_id(),
        "plan": plan_txt,
        "amount": amount,
        "activated": fmt(now),
        "expire": fmt(expire),
        "created_at": now.timestamp()
    }

    invoices = old.get("invoices", [])
    invoices.append(invoice)

    await db.update_plan(uid, {
        "premium": True,
        "plan": plan_txt,
        "expire": expire,
        "activated_at": now.timestamp(),
        "invoices": invoices
    })

    await client.send_message(
        uid,
        f"🎉 **Premium Activated**\n\n💎 Plan: {plan_txt}\n⏰ Till: {fmt(expire)}"
    )

    await query.message.edit("✅ Payment Approved")
    await query.answer("Done")


@Client.on_callback_query(filters.regex("^pay_no#"))
async def reject_payment(client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not allowed", show_alert=True)

    uid = int(query.data.split("#")[1])
    await client.send_message(uid, "❌ Payment rejected")
    await query.message.edit("❌ Rejected")


# ======================================================
# 📊 ADMIN PREMIUM STATS
# ======================================================

@Client.on_message(filters.command("premstats") & filters.user(ADMINS))
async def premium_stats(_, message):
    users = await db.get_premium_users()
    now = datetime.utcnow()

    total = len(users)
    active = expired = 0

    for u in users:
        exp = u.get("plan", {}).get("expire")
        if not exp:
            continue
        exp = datetime.utcfromtimestamp(exp)
        if exp > now:
            active += 1
        else:
            expired += 1

    await message.reply(
        f"""
📊 **Premium Stats**

👥 Total   : {total}
✅ Active  : {active}
❌ Expired: {expired}
"""
    )
