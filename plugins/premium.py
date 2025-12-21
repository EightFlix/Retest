import qrcode
import secrets
import asyncio
from io import BytesIO
from datetime import datetime, timedelta

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram.errors import ListenerTimeout

from info import (
    ADMINS, IS_PREMIUM, PRE_DAY_AMOUNT,
    UPI_ID, UPI_NAME, RECEIPT_SEND_USERNAME
)

from database.users_chats_db import db
from utils import is_premium

# ================= CONFIG =================
REMINDER_STEPS = [
    ("12h", timedelta(hours=12)),
    ("6h", timedelta(hours=6)),
    ("3h", timedelta(hours=3)),
    ("1h", timedelta(hours=1)),
    ("10m", timedelta(minutes=10)),
]

# ================= HELPERS =================
def fmt(dt): 
    return dt.strftime("%d %b %Y, %I:%M %p")

def gen_invoice_id():
    return "PRM-" + secrets.token_hex(3).upper()

def parse_duration(txt):
    txt = txt.lower()
    num = int("".join(filter(str.isdigit, txt)) or 0)
    if num <= 0: return None
    if "min" in txt: return timedelta(minutes=num)
    if "hour" in txt: return timedelta(hours=num)
    if "day" in txt: return timedelta(days=num)
    if "month" in txt: return timedelta(days=30*num)
    if "year" in txt: return timedelta(days=365*num)

def buy_btn():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💰 Buy / Renew Premium", callback_data="buy_premium")]]
    )

# ================= USER =================
@Client.on_message(filters.command("plan") & filters.private)
async def plan(_, m):
    if m.from_user.id in ADMINS:
        return await m.reply("👑 Admin = Lifetime Premium")
    if await is_premium(m.from_user.id, m._client):
        return await m.reply("✅ Premium Active\nUse /myplan")
    await m.reply("💎 Premium Benefits\n🚀 Fast\n📩 PM Search", reply_markup=buy_btn())

@Client.on_message(filters.command("myplan") & filters.private)
async def myplan(_, m):
    p = db.get_plan(m.from_user.id)
    if not p.get("premium"):
        return await m.reply("❌ No active premium")
    await m.reply(
        f"🎉 Premium Active\n\n"
        f"💎 {p['plan']}\n"
        f"⏰ Expires: {fmt(p['expire'])}"
    )

# ================= INVOICE =================
@Client.on_message(filters.command("invoice") & filters.private)
async def invoice(_, m):
    p = db.get_plan(m.from_user.id)
    invs = p.get("invoices", [])
    if not invs:
        return await m.reply("❌ No invoices found")
    if len(m.command) > 1 and m.command[1] == "history":
        text = "🧾 **Invoice History**\n\n"
        for i in invs[-5:][::-1]:
            text += f"• `{i['id']}` | ₹{i['amount']} | {i['plan']}\n"
        return await m.reply(text)
    i = invs[-1]
    await m.reply(
        f"🧾 **Invoice**\n\n"
        f"ID: `{i['id']}`\n"
        f"Plan: {i['plan']}\n"
        f"Amount: ₹{i['amount']}\n"
        f"Expire: {i['expire']}"
    )

# ================= BUY =================
@Client.on_callback_query(filters.regex("^buy_premium$"))
async def buy(_, q: CallbackQuery):
    await q.message.edit(
        "⏳ Send duration:\n`1 day`, `1 month`, `1 year`"
    )
    try:
        msg = await q._client.listen(q.message.chat.id, q.from_user.id, timeout=300)
        dur = parse_duration(msg.text)
        if not dur: raise
    except:
        return await q.message.reply("❌ Invalid duration")

    days = max(1, dur.days)
    amount = days * PRE_DAY_AMOUNT

    upi = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
    qr = qrcode.make(upi)
    bio = BytesIO()
    qr.save(bio, "PNG")
    bio.seek(0)

    await q.message.reply_photo(
        bio,
        caption=f"💰 Amount: ₹{amount}\nSend payment screenshot"
    )

    try:
        ss = await q._client.listen(q.message.chat.id, q.from_user.id, timeout=600)
        if not ss.photo: raise
    except:
        return await q.message.reply("❌ Screenshot missing")

    btn = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"pay_ok#{q.from_user.id}#{msg.text}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"pay_no#{q.from_user.id}")
    ]])

    await q._client.send_photo(
        RECEIPT_SEND_USERNAME,
        ss.photo.file_id,
        caption=f"#PAYMENT\nUser: {q.from_user.id}\nPlan: {msg.text}",
        reply_markup=btn
    )

# ================= ADMIN PANEL =================
@Client.on_message(filters.command("premium") & filters.user(ADMINS))
async def admin_panel(_, m):
    total = db.get_premium_count()
    await m.reply(
        f"👑 **ADMIN PREMIUM PANEL**\n\n"
        f"💎 Active Premium: {total}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎁 Trial Requests", callback_data="trial_list")],
            [InlineKeyboardButton("➕ Add Premium", callback_data="add_prm")],
        ])
    )

# ================= TRIAL =================
@Client.on_callback_query(filters.regex("^trial_list$"))
async def trial_list(_, q):
    reqs = db.req.find({})
    text = "🎁 Trial Requests\n\n"
    btn = []
    for r in reqs:
        uid = r["id"]
        text += f"• `{uid}`\n"
        btn.append([
            InlineKeyboardButton("✅ Approve", callback_data=f"trial_ok#{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"trial_no#{uid}")
        ])
    await q.message.edit(text, reply_markup=InlineKeyboardMarkup(btn or [[
        InlineKeyboardButton("No Requests", callback_data="noop")
    ]]))

@Client.on_callback_query(filters.regex("^trial_ok"))
async def trial_ok(_, q):
    uid = int(q.data.split("#")[1])
    expire = datetime.utcnow() + timedelta(days=1)
    db.update_plan(uid, {
        "premium": True,
        "plan": "Trial (1 Day)",
        "expire": expire,
        "trial": True,
        "invoices": []
    })
    await q._client.send_message(uid, "🎉 Trial Approved (24h)")
    db.req.delete_many({"id": uid})
    await q.message.edit("✅ Trial Approved")

# ================= REMINDER WORKER =================
async def premium_reminder_worker(bot: Client):
    while True:
        for u in db.get_premium_users():
            uid = u["id"]
            if uid in ADMINS: continue
            st = u["status"]
            if not st.get("premium"): continue

            rem = st["expire"] - datetime.utcnow()
            if rem.total_seconds() <= 0:
                st["premium"] = False
                db.update_plan(uid, st)
                await bot.send_message(uid, "❌ Premium expired")
        await asyncio.sleep(300)
