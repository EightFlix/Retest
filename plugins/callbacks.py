import random
import time
from datetime import timedelta # यह लाइन मिसिंग थी
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from info import ADMINS, PICS, UPDATES_LINK, SUPPORT_LINK, URL, BIN_CHANNEL, QUALITY, LANGUAGES, script
from utils import get_settings, is_premium, get_wish, temp
from database.users_chats_db import db
from database.ia_filterdb import db_count_documents

# --- Commands ---

@Client.on_message(filters.command('start') & filters.private)
async def start_command(client, message):
    if len(message.command) < 2:
        if not await db.is_user_exist(message.from_user.id):
            await db.add_user(message.from_user.id, message.from_user.first_name)
        
        buttons = [[
            InlineKeyboardButton("+ Add Me To Your Group +", url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('ℹ️ Updates', url=UPDATES_LINK),
            InlineKeyboardButton('🧑‍💻 Support', url=SUPPORT_LINK)
        ],[
            InlineKeyboardButton('👨‍🚒 Help', callback_data='help'),
            InlineKeyboardButton('📚 About', callback_data='about')
        ]]
        return await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, get_wish()),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- Callbacks ---

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data

    if data == "close_data":
        await query.answer("बंद किया गया!")
        await query.message.delete()
        try: await query.message.reply_to_message.delete()
        except: pass

    elif data == "start":
        buttons = [[
            InlineKeyboardButton("+ Add Me To Your Group +", url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('ℹ️ Updates', url=UPDATES_LINK),
            InlineKeyboardButton('🧑‍💻 Support', url=SUPPORT_LINK)
        ],[
            InlineKeyboardButton('👨‍🚒 Help', callback_data='help'),
            InlineKeyboardButton('📚 About', callback_data='about')
        ]]
        await query.message.edit_media(
            InputMediaPhoto(random.choice(PICS), caption=script.START_TXT.format(query.from_user.mention, get_wish())),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "help":
        buttons = [[
            InlineKeyboardButton('User Commands', callback_data='user_cmds'),
            InlineKeyboardButton('Admin Commands', callback_data='admin_cmds')
        ],[
            InlineKeyboardButton('« Back', callback_data='start')
        ]]
        await query.message.edit_caption(caption=script.HELP_TXT, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "about":
        buttons = [[
            InlineKeyboardButton('📊 Stats', callback_data='stats_callback'),
            InlineKeyboardButton('🧑‍💻 Owner', callback_data='owner_info')
        ],[
            InlineKeyboardButton('« Back', callback_data='start')
        ]]
        await query.message.edit_caption(caption=script.ABOUT_TXT, reply_markup=InlineKeyboardMarkup(buttons))

    # --- User & Admin Commands Buttons Fix ---
    elif data == "user_cmds":
        await query.message.edit_caption(
            caption=script.USER_COMMANDS_TXT, # सुनिश्चित करें कि यह script.py में है
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='help')]])
        )

    elif data == "admin_cmds":
        if query.from_user.id not in ADMINS:
            return await query.answer("यह केवल एडमिन्स के लिए है!", show_alert=True)
        await query.message.edit_caption(
            caption=script.ADMIN_COMMANDS_TXT, # सुनिश्चित करें कि यह script.py में है
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='help')]])
        )

    elif data == "stats_callback":
        if query.from_user.id not in ADMINS:
            return await query.answer("केवल एडमिन्स के लिए!", show_alert=True)
        files = db_count_documents()
        users = await db.total_users_count()
        uptime = str(timedelta(seconds=int(time.time() - temp.START_TIME)))
        await query.answer(f"Files: {files}\nUsers: {users}\nUptime: {uptime}", show_alert=True)

    elif data == "owner_info":
        await query.message.edit_caption(
            caption=script.MY_OWNER_TXT, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='about')]])
        )
