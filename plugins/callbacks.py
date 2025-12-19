import random
import time
from datetime import timedelta # एरर फिक्स: इसे जोड़ा गया है
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from info import ADMINS, PICS, UPDATES_LINK, SUPPORT_LINK, URL, BIN_CHANNEL, QUALITY, LANGUAGES, script
from utils import get_settings, is_premium, get_wish, temp
from database.users_chats_db import db
from database.ia_filterdb import db_count_documents

# --- Commands ---

@Client.on_message(filters.command('start') & filters.private)
async def start_command(client, message):
    """सिंपल /start कमांड को हैंडल करता है"""
    if len(message.command) < 2:
        # यूजर को डेटाबेस में जोड़ना
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

    # --- क्लोज बटन ---
    if data == "close_data":
        await query.answer("बंद किया गया!")
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass

    # --- पेजिनेशन बटन ---
    elif data == "pages":
        await query.answer()

    # --- स्ट्रीमिंग लॉजिक ---
    elif data.startswith("stream"):
        file_id = data.split('#', 1)[1]
        if not await is_premium(query.from_user.id, client):
            return await query.answer("यह केवल प्रीमियम यूजर्स के लिए है! /plan चेक करें।", show_alert=True)
        
        msg = await client.send_cached_media(chat_id=BIN_CHANNEL, file_id=file_id)
        watch = f"{URL}watch/{msg.id}"
        download = f"{URL}download/{msg.id}"
        
        btn = [[
            InlineKeyboardButton("ᴡᴀᴛᴄʜ ᴏɴʟɪɴᴇ", url=watch),
            InlineKeyboardButton("ꜰᴀsᴛ ᴅᴏᴡɴʟᴏᴀᴅ", url=download)
        ],[
            InlineKeyboardButton('❌ ᴄʟᴏsᴇ ❌', callback_data='close_data')
        ]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        await query.answer("लिंक तैयार हैं!", show_alert=False)

    # --- हेल्प सेक्शन (बटन फिक्स के साथ) ---
    elif data == "help":
        buttons = [[
            InlineKeyboardButton('User Commands', callback_data='user_cmds'),
            InlineKeyboardButton('Admin Commands', callback_data='admin_cmds')
        ],[
            InlineKeyboardButton('« Back', callback_data='start')
        ]]
        # edit_media का इस्तेमाल फोटो के साथ कैप्शन बदलने के लिए
        await query.message.edit_media(
            InputMediaPhoto(random.choice(PICS), caption=script.HELP_TXT.format(query.from_user.mention)),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # --- हेल्प के अंदर के बटन्स (मिसिंग फीचर्स जोड़े गए) ---
    elif data == "user_cmds":
        await query.message.edit_caption(
            caption=script.USER_COMMANDS_TXT, # यह script.py से आएगा
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='help')]])
        )

    elif data == "admin_cmds":
        if query.from_user.id not in ADMINS:
            return await query.answer("यह केवल एडमिन्स के लिए है!", show_alert=True)
        await query.message.edit_caption(
            caption=script.ADMIN_COMMANDS_TXT, # यह script.py से आएगा
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='help')]])
        )

    # --- अबाउट सेक्शन ---
    elif data == "about":
        buttons = [[
            InlineKeyboardButton('📊 Stats', callback_data='stats_callback'),
            InlineKeyboardButton('🧑‍💻 Owner', callback_data='owner_info')
        ],[
            InlineKeyboardButton('« Back', callback_data='start')
        ]]
        await query.message.edit_media(
            InputMediaPhoto(random.choice(PICS), caption=script.MY_ABOUT_TXT),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # --- मेन स्टार्ट मेनू ---
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

    # --- लैंग्वेज और क्वालिटी (पूर्ण सुरक्षित) ---
    elif data.startswith("languages"):
        _, key, req, offset = data.split("#")
        if int(req) != query.from_user.id:
            return await query.answer("यह सर्च आपके लिए नहीं है!", show_alert=True)
        
        btn = [
            [InlineKeyboardButton(LANGUAGES[i].title(), callback_data=f"lang_filter#{LANGUAGES[i]}#{key}#{offset}#{req}"),
             InlineKeyboardButton(LANGUAGES[i+1].title(), callback_data=f"lang_filter#{LANGUAGES[i+1]}#{key}#{offset}#{req}")]
            for i in range(0, len(LANGUAGES)-1, 2)
        ]
        btn.append([InlineKeyboardButton("⪻ Back to Results", callback_data=f"next_{req}_{key}_{offset}")])
        await query.message.edit_text("<b>अपनी पसंद की भाषा चुनें 👇</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif data.startswith("qualities"):
        _, key, req, offset = data.split("#")
        if int(req) != query.from_user.id:
            return await query.answer("यह सर्च आपके लिए नहीं है!", show_alert=True)
        
        btn = [
            [InlineKeyboardButton(QUALITY[i].title(), callback_data=f"qual_filter#{QUALITY[i]}#{key}#{offset}#{req}"),
             InlineKeyboardButton(QUALITY[i+1].title(), callback_data=f"qual_filter#{QUALITY[i+1]}#{key}#{offset}#{req}")]
            for i in range(0, len(QUALITY)-1, 2)
        ]
        btn.append([InlineKeyboardButton("⪻ Back to Results", callback_data=f"next_{req}_{key}_{offset}")])
        await query.message.edit_text("<b>अपनी पसंद की क्वालिटी चुनें 👇</b>", reply_markup=InlineKeyboardMarkup(btn))

    # --- स्टेट्स अलर्ट (इम्पोर्ट एरर फिक्स) ---
    elif data == "stats_callback":
        if query.from_user.id not in ADMINS:
            return await query.answer("केवल एडमिन्स के लिए!", show_alert=True)
        files = db_count_documents()
        users = await db.total_users_count()
        # timedelta अब परिभाषित है
        uptime = str(timedelta(seconds=int(time.time() - temp.START_TIME)))
        await query.answer(f"Files: {files}\nUsers: {users}\nUptime: {uptime}", show_alert=True)

    # --- ओनर इन्फो ---
    elif data == "owner_info":
        await query.message.edit_caption(
            caption=script.MY_OWNER_TXT, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='about')]])
        )
