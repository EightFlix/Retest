from pymongo import MongoClient
from datetime import datetime
import time

# =========================
# 🔐 REQUIRED CONFIGS
# =========================
from info import (
    BOT_ID,
    ADMINS,
    DATABASE_NAME,
    DATA_DATABASE_URL,
    VERIFY_EXPIRE
)

# =========================
# 🧩 OPTIONAL CONFIGS (SAFE)
# =========================
try:
    from info import (
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
    )
except ImportError:
    IMDB_TEMPLATE = ""
    WELCOME_TEXT = ""
    LINK_MODE = True
    TUTORIAL = ""
    SHORTLINK_URL = None
    SHORTLINK_API = None
    SHORTLINK = False
    FILE_CAPTION = "{file_name}"
    IMDB = False
    WELCOME = True
    SPELL_CHECK = False
    PROTECT_CONTENT = True
    AUTO_DELETE = False
    IS_STREAM = True


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
        "shortlink": SHORTLINK,
        "shortlink_url": SHORTLINK_URL,
        "shortlink_api": SHORTLINK_API,
        "tutorial": TUTORIAL,
        "links": LINK_MODE,
        "pm_search": True,
        "group_search": True,
    }

    default_verify = {
        "is_verified": False,
        "verified_time": 0,
        "verify_token": "",
        "expire_time": 0,
    }

    default_plan = {
        "premium": False,
        "plan": "",
        "expire": None,
        "invoice": [],
        "last_reminder": None,
        "last_msg_id": None,
    }

    # =========================
    # 🧠 INIT COLLECTIONS
    # =========================
    def __init__(self):
        self.users = dbase.Users
        self.groups = dbase.Groups
        self.premium = dbase.Premiums
        self.settings = dbase.BotSettings
        self.reminders = dbase.Reminders
        self.trials = dbase.Trials

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
                "ban": {"status": False, "reason": ""},
            })

    async def total_users_count(self):
        return self.users.count_documents({})

    async def get_all_users(self):
        return self.users.find({})

    async def delete_user(self, user_id):
        self.users.delete_one({"id": user_id})

    async def get_ban_status(self, user_id):
        u = self.users.find_one({"id": user_id})
        return u.get("ban", {"status": False, "reason": ""}) if u else {"status": False}

    # =========================
    # 👥 GROUPS
    # =========================
    async def add_group(self, chat_id, title):
        if not self.groups.find_one({"id": chat_id}):
            self.groups.insert_one({
                "id": chat_id,
                "title": title,
                "settings": self.default_settings,
            })

    async def total_chat_count(self):
        return self.groups.count_documents({})

    async def get_settings(self, chat_id):
        g = self.groups.find_one({"id": chat_id})
        return g.get("settings", self.default_settings) if g else self.default_settings

    async def update_settings(self, chat_id, settings):
        self.groups.update_one(
            {"id": chat_id},
            {"$set": {"settings": settings}},
            upsert=True
        )

    # =========================
    # 💎 PREMIUM
    # =========================
    def get_plan(self, user_id):
        p = self.premium.find_one({"id": user_id})
        return p["plan"] if p else self.default_plan

    def update_plan(self, user_id, plan):
        self.premium.update_one(
            {"id": user_id},
            {"$set": {"plan": plan}},
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
        p = self.premium.find_one({"id": user_id})
        return p.get("plan", {}).get("invoice", []) if p else []

    # =========================
    # ⏰ SMART REMINDERS
    # =========================
    def add_reminder(self, user_id, remind_at, rtype="premium"):
        self.reminders.insert_one({
            "user_id": user_id,
            "type": rtype,
            "remind_at": remind_at,
            "sent": False,
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
    # ⚙️ BOT SETTINGS
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
# ✅ EXPORT
# =========================
db = Database()
