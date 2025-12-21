import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logging.getLogger("hydrogram").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

import os
import time
import asyncio
import uvloop
from datetime import datetime, timedelta
import pytz

from hydrogram import Client, types
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from typing import Union, Optional, AsyncGenerator

from web import web_app
from info import API_ID, API_HASH, BOT_TOKEN, PORT, LOG_CHANNEL, ADMINS
from utils import temp, check_premium
from database.users_chats_db import db


# ==========================
# 🕒 TIME / CONFIG
# ==========================
IST = pytz.timezone("Asia/Kolkata")
GRACE_PERIOD = timedelta(minutes=20)

REMINDER_STEPS = [
    ("12h", timedelta(hours=12)),
    ("6h", timedelta(hours=6)),
    ("3h", timedelta(hours=3)),
    ("1h", timedelta(hours=1)),
    ("10m", timedelta(minutes=10)),
]


def ist_time(dt=None):
    dt = dt.astimezone(IST) if dt else datetime.now(IST)
    return dt.strftime("%d %b %Y, %I:%M %p")


def buy_button():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💎 Buy Plan Now", callback_data="buy_premium")]]
    )


def progress_bar(total: float, remaining: float) -> str:
    if total <= 0:
        return "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩 100%"
    percent = max(0, min(1, remaining / total))
    filled = int(percent * 10)
    return "🟩" * filled + "⬜" * (10 - filled) + f" {int(percent * 100)}%"


# ==========================
# 🔁 PREMIUM REMINDER LOOP
# ==========================
async def premium_reminder_loop(bot: Client):
    await asyncio.sleep(15)

    while True:
        try:
            users = db.get_premium_users()
            now = datetime.utcnow()

            for user in users:
                uid = user["id"]
                if uid in ADMINS:
                    continue

                st = user.get("status", {})
                expire = st.get("expire")
                activated = st.get("activated_at") or expire
                last_step = st.get("last_reminder")
                last_msg = st.get("last_msg_id")

                if not expire:
                    continue

                if isinstance(expire, (int, float)):
                    expire = datetime.utcfromtimestamp(expire)
                if isinstance(activated, (int, float)):
                    activated = datetime.utcfromtimestamp(activated)

                remaining = expire - now
                total = (expire - activated).total_seconds()
                rem_sec = remaining.total_seconds()

                # ===== EXPIRED (after grace)
                if rem_sec <= -GRACE_PERIOD.total_seconds():
                    if last_step == "expired":
                        continue

                    if last_msg:
                        try:
                            await bot.delete_messages(uid, last_msg)
                        except:
                            pass

                    msg = await bot.send_message(
                        uid,
                        "❌ **Premium Expired**\n\n"
                        "Your premium plan has ended.\n"
                        "Renew now to continue premium access 🚀",
                        reply_markup=buy_button()
                    )

                    db.update_plan(uid, {
                        "premium": False,
                        "last_reminder": "expired",
                        "last_msg_id": msg.id
                    })
                    continue

                # ===== REMINDERS
                for step, delta in REMINDER_STEPS:
                    if remaining <= delta and last_step != step:

                        if last_msg:
                            try:
                                await bot.delete_messages(uid, last_msg)
                            except:
                                pass

                        bar = progress_bar(total, rem_sec)
                        hrs = int(rem_sec // 3600)
                        mins = int((rem_sec % 3600) // 60)
                        left = f"{hrs} hours" if hrs > 0 else f"{mins} minutes"

                        msg = await bot.send_message(
                            uid,
                            "⏰ **Premium Expiry Reminder**\n\n"
                            f"Time Left: **{left}**\n"
                            f"{bar}\n\n"
                            f"🕒 Valid Till: {ist_time(expire)}",
                            reply_markup=buy_button()
                        )

                        db.update_plan(uid, {
                            "last_reminder": step,
                            "last_msg_id": msg.id
                        })
                        break

            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
            await asyncio.sleep(10)


# ==========================
# 🤖 BOT CLASS
# ==========================
class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Auto_Filter_Bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"}
        )

    async def start(self):
        await super().start()
        temp.START_TIME = time.time()
        temp.BOT = self

        if os.path.exists("restart.txt"):
            with open("restart.txt") as f:
                try:
                    cid, mid = map(int, f.read().split())
                    await self.edit_message_text(cid, mid, "✅ Restarted Successfully!")
                except:
                    pass
            os.remove("restart.txt")

        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name

        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        asyncio.create_task(check_premium(self))
        asyncio.create_task(premium_reminder_loop(self))

        for admin in ADMINS:
            try:
                await self.send_message(
                    admin,
                    "♻️ **Bot Restarted Successfully**\n\n"
                    f"🕒 Time: {ist_time()}\n"
                    "🤖 Status: Online & Running"
                )
            except:
                pass

        try:
            await self.send_message(
                LOG_CHANNEL,
                f"<b>{me.mention} Restarted Successfully 🤖</b>"
            )
        except:
            pass

        logger.info(f"@{me.username} started")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped")

    async def iter_messages(
        self: Client,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        current = offset
        while True:
            diff = min(200, limit - current)
            if diff <= 0:
                return
            msgs = await self.get_messages(chat_id, list(range(current, current + diff)))
            for msg in msgs:
                yield msg
                current += 1


async def main():
    uvloop.install()
    bot = Bot()
    try:
        await bot.start()
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
