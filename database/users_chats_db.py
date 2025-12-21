from pymongo import MongoClient
from datetime import datetime, timedelta
import time

from info import (
    BOT_ID,
    ADMINS,
    DATABASE_NAME,
    DATA_DATABASE_URL,

    # defaults
    IMDB_TEMPLATE,
    WELCOME_TEXT,
    LINK_MODE,
    TUTORIAL,
    SHORTLINK_URL,
    SHORTLINK_API,
    SHORTLINK,
    FILE_CAPTION,
    IMDB,
    WELCOME,
    SPELL_CHECK,
    PROTECT_CONTENT,
    AUTO_DELETE,
    IS_STREAM,
    VERIFY_EXPIRE
)

# =========================
# 🔗 MongoDB (SINGLE DB)
# =========================
client = MongoClient(DATA_DATABASE_URL)
dbase = client[DATABASE_NAME]


class Database:
    # =========================
    # ⚙️ DEFAULT STRUCTURES
    # =========================
    default_settings = {
        "file_secure": PROTECT_CONTENT,
        "imdb": IMDB,
        "spell_check": SPELL_CHECK,
        "auto_delete": AUTO_DELETE,
        "welcome": WELCOME,
        "welcome_text": WELCOME_TEXT,
        "template": IMDB_TEMPLATE,
        "caption": FILE_CAPTION,
        "url": SHORTLINK_URL,
        "api": SHORTLINK_API,
        "shortlink": SHORTLINK,
        "tutorial": TUTORIAL,
        "links": LINK_MODE,
        "pm_search": True,
        "group_search": True
    }

    default_verify = {
        "is_verified": False,
        "verified_time": 0,
        "verify_token": "",
        "link": "",
        "expire_time": 0
    }

    default_plan = {
        "premium": False,
        "plan": "",
        "expire": None,
        "invoice": [],
        "last_reminder": None
    }

    # =========================
    # 🧠 INIT COLLECTIONS
    # =========================
    def __init__(self):
        self.users = dbase.Users
        self.groups = dbase.Groups
        self.premium = dbase.Premiums
        self.settings = dbase.BotSettings
        self.connections = dbase.Connections
        self.reminders = dbase.Reminders
        self.bans = dbase.Bans

    # =========================
    # 👤 USERS
    # =========================
    async def add_user(self, user_id, name):
        if not self.users.find_one({"id": user_id}):
            self.users.insert_one({
                "id": user_id,
                "name": name,
                "created_at": time.time(),
                "verify": self.default_verify,
                "ban": {"status": False, "reason": ""}
            })

    async def is_user_exist(self, user_id):
        return bool(self.users.find_one({"id": user_id}))

    async def total_users_count(self):
        return self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({})

    async def delete_user(self, user_id):
        self.users.delete_one({"id": user_id})

    # =========================
    # 🚫 BAN SYSTEM
    # =========================
    async def ban_user(self, user_id, reason="No reason"):
        self.users.update_one(
            {"id": user_id},
            {"$set": {"ban": {"status": True, "reason": reason}}}
        )

    async def unban_user(self, user_id):
        self.users.update_one(
            {"id": user_id},
            {"$set": {"ban": {"status": False, "reason": ""}}}
        )

    async def get_ban_status(self, user_id):
        user = self.users.find_one({"id": user_id})
        if not user:
            return {"status": False, "reason": ""}
        return user.get("ban", {"status": False, "reason": ""})

    # =========================
    # 👥 GROUPS
    # =========================
    async def add_group(self, chat_id, title):
        if not self.groups.find_one({"id": chat_id}):
            self.groups.insert_one({
                "id": chat_id,
                "title": title,
                "settings": self.default_settings,
                "disabled": False
            })

    async def total_chat_count(self):
        return self.groups.count_documents({})

    async def get_all_chats(self):
        return self.groups.find({})

    async def get_settings(self, chat_id):
        grp = self.groups.find_one({"id": chat_id})
        return grp.get("settings", self.default_settings) if grp else self.default_settings

    async def update_settings(self, chat_id, settings):
        self.groups.update_one(
            {"id": chat_id},
            {"$set": {"settings": settings}},
            upsert=True
        )

    # =========================
    # 💎 PREMIUM SYSTEM
    # =========================
    def get_plan(self, user_id):
        doc = self.premium.find_one({"id": user_id})
        return doc["plan"] if doc else self.default_plan

    def update_plan(self, user_id, plan_data):
        self.premium.update_one(
            {"id": user_id},
            {"$set": {"plan": plan_data}},
            upsert=True
        )

    def get_premium_users(self):
        return self.premium.find({"plan.premium": True})

    def get_premium_count(self):
        return self.premium.count_documents({"plan.premium": True})

    # =========================
    # 🧾 INVOICE
    # =========================
    def add_invoice(self, user_id, invoice):
        self.premium.update_one(
            {"id": user_id},
            {"$push": {"plan.invoice": invoice}},
            upsert=True
        )

    def get_invoices(self, user_id):
        doc = self.premium.find_one({"id": user_id})
        if not doc:
            return []
        return doc.get("plan", {}).get("invoice", [])

    # =========================
    # ⏰ SMART REMINDER ENGINE
    # =========================
    def add_reminder(self, user_id, remind_at, rtype="premium"):
        self.reminders.insert_one({
            "user_id": user_id,
            "type": rtype,
            "remind_at": remind_at,
            "sent": False
        })

    def get_due_reminders(self):
        return self.reminders.find({
            "sent": False,
            "remind_at": {"$lte": datetime.utcnow()}
        })

    def mark_reminder_sent(self, _id):
        self.reminders.update_one(
            {"_id": _id},
            {"$set": {"sent": True}}
        )

    # =========================
    # ⚙️ BOT GLOBAL SETTINGS
    # =========================
    def update_bot_setting(self, key, value):
        self.settings.update_one(
            {"id": BOT_ID},
            {"$set": {key: value}},
            upsert=True
        )

    def get_bot_settings(self):
        return self.settings.find_one({"id": BOT_ID}) or {}

    # =========================
    # 📊 DB SIZE
    # =========================
    async def get_data_db_size(self):
        return dbase.command("dbstats")["dataSize"]


# =========================
# ✅ EXPORT INSTANCE
# =========================
db = Database()
