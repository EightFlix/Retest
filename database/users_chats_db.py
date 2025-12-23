from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
import time
import asyncio
from functools import wraps

from info import (
    BOT_ID,
    ADMINS,
    DATABASE_NAME,
    DATA_DATABASE_URL,
    VERIFY_EXPIRE
)

# =========================
# 🔗 MongoDB Connection
# =========================
try:
    client = MongoClient(
        DATA_DATABASE_URL,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        maxPoolSize=50,
        retryWrites=True
    )
    client.server_info()
    dbase = client[DATABASE_NAME]
    print("✅ Database connected successfully")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    dbase = None


# =========================
# 🛡️ Async Wrapper
# =========================
def run_sync(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


class Database:

    default_settings = {
        "pm_search": True,
        "group_search": True,
        "auto_delete": False,
        "anti_link": False,
    }

    default_verify = {
        "is_verified": False,
        "verified_time": 0,
        "verify_token": "",
        "expire_time": 0,
    }

    default_plan = {
        "premium": False,
        "plan": "free",
        "expire": None,
        "invoice": [],
        "last_reminder": None,
        "last_msg_id": None,
    }

    default_warn = {
        "count": 0,
        "last_warn": 0,
    }

    # =========================
    # 🧠 INIT
    # =========================
    def __init__(self):
        if dbase is None:
            raise Exception("Database not connected")

        self.users = dbase.users
        self.groups = dbase.groups
        self.premium = dbase.premium
        self.reminders = dbase.reminders
        self.bans = dbase.bans
        self.warns = dbase.warns

        self._create_indexes()

    def _create_indexes(self):
        try:
            self.users.create_index("id", unique=True)
            self.groups.create_index("id", unique=True)
            self.bans.create_index("id")
            self.bans.create_index("until")
            self.warns.create_index([("user_id", 1), ("chat_id", 1)])
            self.premium.create_index("id")
            self.reminders.create_index([("sent", 1), ("remind_at", 1)])
        except:
            pass

    # =========================
    # 👤 USERS
    # =========================
    async def is_user_exist(self, user_id: int):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.users.find_one({"id": user_id}) is not None
        )

    async def add_user(self, user_id: int, name: str):
        if await self.is_user_exist(user_id):
            return False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.users.insert_one({
                "id": user_id,
                "name": name,
                "created_at": time.time(),
                "verify": self.default_verify.copy()
            })
        )
        return True

    async def total_users_count(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.users.count_documents,
            {}
        )

    async def get_all_users(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: list(self.users.find({}))
        )

    # =========================
    # 🚫 BANS
    # =========================
    async def get_banned_users(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: list(self.bans.find({"until": {"$gt": time.time()}}))
        )

    async def ban_user(self, user_id: int, until: float, reason: str = ""):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.bans.update_one(
                {"id": user_id},
                {"$set": {
                    "until": until,
                    "reason": reason,
                    "banned_at": time.time()
                }},
                upsert=True
            )
        )
        return True

    async def unban_user(self, user_id: int):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.bans.delete_one({"id": user_id})
        )
        return True

    # =========================
    # ✅ FIX: BAN STATUS (MISSING METHOD)
    # =========================
    async def get_ban_status(self, user_id: int):
        """
        Used by plugins/banned.py
        """
        try:
            loop = asyncio.get_event_loop()
            ban = await loop.run_in_executor(
                None,
                lambda: self.bans.find_one({"id": user_id})
            )

            if not ban:
                return {"status": False}

            # Auto-unban if expired
            if ban.get("until", 0) <= time.time():
                await self.unban_user(user_id)
                return {"status": False}

            return {
                "status": True,
                "reason": ban.get("reason", ""),
                "until": ban.get("until")
            }

        except Exception as e:
            print(f"[BAN_STATUS_ERROR] {e}")
            return {"status": False}

    # =========================
    # 👥 GROUPS
    # =========================
    async def add_group(self, chat_id: int, title: str):
        loop = asyncio.get_event_loop()
        if await loop.run_in_executor(None, lambda: self.groups.find_one({"id": chat_id})):
            return False

        await loop.run_in_executor(
            None,
            lambda: self.groups.insert_one({
                "id": chat_id,
                "title": title,
                "settings": self.default_settings.copy(),
                "joined_at": time.time()
            })
        )
        return True

    async def get_settings(self, chat_id: int):
        loop = asyncio.get_event_loop()
        group = await loop.run_in_executor(
            None,
            lambda: self.groups.find_one({"id": chat_id})
        )

        settings = self.default_settings.copy()
        if group and "settings" in group:
            settings.update(group["settings"])
        return settings

    async def update_settings(self, chat_id: int, settings: dict):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.groups.update_one(
                {"id": chat_id},
                {"$set": {"settings": settings}},
                upsert=True
            )
        )
        return True


# =========================
# ✅ EXPORT
# =========================
db = Database()
