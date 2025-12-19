from pymongo import MongoClient
from info import BOT_ID, ADMINS, DATABASE_NAME, DATA_DATABASE_URL, FILES_DATABASE_URL, SECOND_FILES_DATABASE_URL, IMDB_TEMPLATE, WELCOME_TEXT, LINK_MODE, TUTORIAL, SHORTLINK_URL, SHORTLINK_API, SHORTLINK, FILE_CAPTION, IMDB, WELCOME, SPELL_CHECK, PROTECT_CONTENT, AUTO_DELETE, IS_STREAM, VERIFY_EXPIRE
import time
from datetime import datetime

files_db_client = MongoClient(FILES_DATABASE_URL)
files_db = files_db_client[DATABASE_NAME]

data_db_client = MongoClient(DATA_DATABASE_URL)
data_db = data_db_client[DATABASE_NAME]

if SECOND_FILES_DATABASE_URL:
     second_files_db_client = MongoClient(SECOND_FILES_DATABASE_URL)
     second_files_db = second_files_db_client[DATABASE_NAME]

class Database:
    default_setgs = {
        'file_secure': PROTECT_CONTENT,
        'imdb': IMDB,
        'spell_check': SPELL_CHECK,
        'auto_delete': AUTO_DELETE,
        'welcome': WELCOME,
        'welcome_text': WELCOME_TEXT,
        'template': IMDB_TEMPLATE,
        'caption': FILE_CAPTION,
        'url': SHORTLINK_URL,
        'api': SHORTLINK_API,
        'shortlink': SHORTLINK,
        'tutorial': TUTORIAL,
        'links': LINK_MODE
    }

    default_verify = {
        'is_verified': False,
        'verified_time': 0,
        'verify_token': "",
        'link': "",
        'expire_time': 0
    }
    
    default_prm = {
        'expire': '',
        'trial': False,
        'plan': '',
        'premium': False
    }

    def __init__(self):
        self.col = data_db.Users
        self.grp = data_db.Groups
        self.prm = data_db.Premiums
        self.req = data_db.Requests
        self.con = data_db.Connections
        self.stg = data_db.Settings

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
            verify_status=self.default_verify
        )

    def new_group(self, id, title):
        return dict(
            id = id,
            title = title,
            chat_status=dict(
                is_disabled=False,
                reason="",
            ),
            settings=self.default_setgs
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = self.col.count_documents({})
        return count
    
    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})
    
    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})
    
    async def delete_user(self, user_id):
        self.col.delete_many({'id': int(user_id)})

    async def delete_chat(self, grp_id):
        self.grp.delete_many({'id': int(grp_id)})

    def find_join_req(self, id):
        return bool(self.req.find_one({'id': id}))

    def add_join_req(self, id):
        self.req.insert_one({'id': id})

    def del_join_req(self):
        self.req.drop()

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        chats = self.grp.find({'chat_status.is_disabled': True})
        b_chats = [chat['id'] for chat in chats]
        b_users = [user['id'] for user in users]
        return b_users, b_chats
    
    async def add_chat(self, chat, title):
        chat = self.new_group(chat, title)
        self.grp.insert_one(chat)

    async def get_chat(self, chat):
        chat = self.grp.find_one({'id':int(chat)})
        return False if not chat else chat.get('chat_status')
    
    async def re_enable_chat(self, id):
        chat_status=dict(
            is_disabled=False,
            reason="",
            )
        self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})
        
    async def update_settings(self, id, settings):
        self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})      
    
    async def get_settings(self, id):
        chat = self.grp.find_one({'id':int(id)})
        if chat:
            return chat.get('settings', self.default_setgs)
        return self.default_setgs
    
    async def disable_chat(self, chat, reason="No Reason"):
        chat_status=dict(
            is_disabled=True,
            reason=reason,
            )
        self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})
    
    async def get_verify_status(self, user_id):
        user = self.col.find_one({'id':int(user_id)})
        if user:
            info = user.get('verify_status', self.default_verify)
            try:
                info.get('expire_time')
            except:
                expire_time = info.get('verified_time') + datetime.timedelta(seconds=VERIFY_EXPIRE)
                info.append({
                    'expire_time': expire_time
                })
            return info
        return self.default_verify
        
    async def update_verify_status(self, user_id, verify):
        self.col.update_one({'id': int(user_id)}, {'$set': {'verify_status': verify}})
    
    async def total_chat_count(self):
        count = self.grp.count_documents({})
        return count
    
    async def get_all_chats(self):
        return self.grp.find({})
    
    async def get_files_db_size(self):
        return (files_db.command("dbstats"))['dataSize']
   
    async def get_second_files_db_size(self):
        return (second_files_db.command("dbstats"))['dataSize']
    
    async def get_data_db_size(self):
        return (data_db.command("dbstats"))['dataSize']
    
    async def get_all_chats_count(self):
        grp = self.grp.count_documents({})
        return grp
    
    def get_plan(self, id):
        st = self.prm.find_one({'id': id})
        if st:
            return st['status']
        return self.default_prm
    
    def update_plan(self, id, data):
        if not self.prm.find_one({'id': id}):
            self.prm.insert_one({'id': id, 'status': data})
        self.prm.update_one({'id': id}, {'$set': {'status': data}})

    def get_premium_count(self):
        return self.prm.count_documents({'status.premium': True})
    
    def get_premium_users(self):
        return self.prm.find({})
    
    def add_connect(self, group_id, user_id):
        user= self.con.find_one({'_id': user_id})
        if user:
            if group_id not in user["group_ids"]:
                self.con.update_one({'_id': user_id}, {"$push": {"group_ids": group_id}})
        else:
            self.con.insert_one({'_id': user_id, 'group_ids': [group_id]})

    def get_connections(self, user_id):
        user = self.con.find_one({'_id': user_id})
        if user:
            return user["group_ids"]
        else:
            return []
        
    def update_bot_sttgs(self, var, val):
        if not self.stg.find_one({'id': BOT_ID}):
            self.stg.insert_one({'id': BOT_ID, var: val})
        self.stg.update_one({'id': BOT_ID}, {'$set': {var: val}})

    def get_bot_sttgs(self):
        return self.stg.find_one({'id': BOT_ID})


db = Database()