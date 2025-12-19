import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from info import (
    temp, UPDATES_LINK, SUPPORT_LINK, IS_STREAM, 
    PM_FILE_DELETE_TIME, PROTECT_CONTENT, script
)
from database.users_chats_db import db
from database.ia_filterdb import get_file_details
from utils import get_settings, get_size, is_premium, get_shortlink, get_readable_time

@Client.on_callback_query(filters.regex(r"^file#"))
async def file_delivery_handler(client: Client, query: CallbackQuery):
    """बटन पर क्लिक करने पर फाइल PM में भेजने का लॉजिक"""
    _, file_id = query.data.split("#")
    
    # चेक करें कि क्या यूजर ने सर्च रिक्वेस्ट खुद की थी (Safety Check)
    try:
        user = query.message.reply_to_message.from_user.id
    except:
        user = query.message.from_user.id
        
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("यह आपके लिए नहीं है! कृपया खुद सर्च करें।", show_alert=True)

    # फाइल की डिटेल्स डेटाबेस से लाएं
    file = await get_file_details(file_id)
    if not file:
        return await query.answer("फाइल नहीं मिली या डेटाबेस से डिलीट हो गई है।", show_alert=True)

    # ग्रुप सेटिंग्स चेक करें
    settings = await get_settings(query.message.chat.id)
    
    # शॉर्टलिंक वेरिफिकेशन (यदि प्रीमियम नहीं है)
    if settings['shortlink'] and not await is_premium(query.from_user.id, client):
        await query.answer("शॉर्टलिंक के जरिए फाइल अनलॉक की जा रही है...", show_alert=False)
        link = await get_shortlink(settings['url'], settings['api'], f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")
        btn = [[
            InlineKeyboardButton("🚀 ɢᴇᴛ ғɪʟᴇ 🚀", url=link)
        ],[
            InlineKeyboardButton("📍 ʜᴏᴡ ᴛᴏ ᴏᴘᴇɴ ʟɪɴᴋ 📍", url=settings['tutorial'])
        ]]
        return await query.message.reply_text(
            f"<b>फाइल:</b> {file['file_name']}\n<b>साइज:</b> {get_size(file['file_size'])}\n\nआपकी फाइल तैयार है, नीचे दिए गए लिंक से प्राप्त करें।",
            reply_markup=InlineKeyboardMarkup(btn)
        )

    # सीधा फाइल भेजने का लॉजिक (PM में)
    await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")

@Client.on_message(filters.command('start') & filters.private)
async def start_handler(client, message):
    """फाइल डिलीवरी और वेरिफिकेशन के लिए स्टार्ट कमांड हैंडलर"""
    if len(message.command) < 2:
        # अगर सिर्फ /start है, तो callbacks.py का 'start' लॉजिक काम करेगा
        return 

    data = message.command[1]
    
    # फाइल डिलीवरी लॉजिक
    if data.startswith("file_"):
        _, grp_id, file_id = data.split("_")
        file = await get_file_details(file_id)
        if not file: return await message.reply("फाइल नहीं मिली।")

        settings = await get_settings(int(grp_id))
        cap = settings['caption'].format(
            file_name=file['file_name'],
            file_size=get_size(file['file_size']),
            file_caption=file.get('caption', '')
        )

        # स्ट्रीमिंग और क्लोज बटन
        btn = []
        if IS_STREAM:
            btn.append([InlineKeyboardButton("✛ ᴡᴀᴛᴄʜ & ᴅᴏᴡɴʟᴏᴀᴅ ✛", callback_data=f"stream#{file_id}")])
        btn.append([InlineKeyboardButton('⚡️ ᴜᴘᴅᴀᴛᴇs', url=UPDATES_LINK), InlineKeyboardButton('💡 sᴜᴘᴘᴏʀᴛ', url=SUPPORT_LINK)])
        btn.append([InlineKeyboardButton('⁉️ ᴄʟᴏsᴇ ⁉️', callback_data='close_data')])

        # फाइल भेजें
        delivered_msg = await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            caption=cap,
            protect_content=PROTECT_CONTENT,
            reply_markup=InlineKeyboardMarkup(btn)
        )

        # ऑटो-डिलीट लॉजिक (कॉपीराइट सुरक्षा)
        time_str = get_readable_time(PM_FILE_DELETE_TIME)
        notification = await delivered_msg.reply(f"<b>⚠️ यह फाइल {time_str} में डिलीट हो जाएगी।</b>")
        
        await asyncio.sleep(PM_FILE_DELETE_TIME)
        
        # फाइल डिलीट करें और 'Get Again' बटन दिखाएं
        await delivered_msg.delete()
        await notification.edit(
            "<b>समय समाप्त! फाइल डिलीट कर दी गई है।</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ', callback_data=f"file#{file_id}")
            ]])
        )

    # 'Send All' लॉजिक
    elif data.startswith("all_"):
        _, grp_id, key = data.split("_")
        files = temp.FILES.get(key)
        if not files: return await message.reply("फाइलें अब उपलब्ध नहीं हैं, फिर से सर्च करें।")
        
        sent_files = []
        for file in files:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file['_id'],
                protect_content=PROTECT_CONTENT
            )
            sent_files.append(msg.id)
            await asyncio.sleep(1) # फ्लड वेट से बचने के लिए

        await message.reply(f"कुल {len(sent_files)} फाइलें भेज दी गई हैं। ये {get_readable_time(PM_FILE_DELETE_TIME)} में डिलीट हो जाएंगी।")
        await asyncio.sleep(PM_FILE_DELETE_TIME)
        await client.delete_messages(message.chat.id, sent_files)
