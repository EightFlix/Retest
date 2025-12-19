import random
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from info import ADMINS, PICS, UPDATES_LINK, SUPPORT_LINK, URL, BIN_CHANNEL, QUALITY, LANGUAGES, script, temp
from utils import get_settings, is_premium, get_wish

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data

    # --- क्लोज बटन ---
    if data == "close_data":
        await query.answer("बंद किया गया!")
        await query.message.delete()
        try:
            # अगर रिप्लाई में ओरिजिनल मैसेज है तो उसे भी डिलीट करें
            await query.message.reply_to_message.delete()
        except:
            pass

    # --- पेजिनेशन बटन (सिर्फ अलर्ट के लिए) ---
    elif data == "pages":
        await query.answer()

    # --- स्ट्रीमिंग लॉजिक (Watch/Download) ---
    elif data.startswith("stream"):
        file_id = data.split('#', 1)[1]
        if not await is_premium(query.from_user.id, client):
            return await query.answer("यह केवल प्रीमियम यूजर्स के लिए है! /plan चेक करें।", show_alert=True)
        
        # फाइल को बिन चैनल में भेजकर लिंक जेनरेट करना
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

    # --- हेल्प और अबाउट सेक्शन ---
    elif data == "help":
        buttons = [[
            InlineKeyboardButton('User Commands', callback_data='user_cmds'),
            InlineKeyboardButton('Admin Commands', callback_data='admin_cmds')
        ],[
            InlineKeyboardButton('« Back', callback_data='start')
        ]]
        await query.message.edit_media(
            InputMediaPhoto(random.choice(PICS), caption=script.HELP_TXT.format(query.from_user.mention)),
            reply_markup=InlineKeyboardMarkup(buttons)
        )

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

    elif data == "start":
        # मुख्य स्टार्ट मेनू पर वापस जाना
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

    # --- लैंग्वेज और क्वालिटी चयन के लिए मेनू ---
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

    # --- एडमिन स्टेट्स (About से) ---
    elif data == "stats_callback":
        if query.from_user.id not in ADMINS:
            return await query.answer("केवल एडमिन्स के लिए!", show_alert=True)
        # यहाँ आप चाहें तो admin_tools से stats_cmd को कॉल कर सकते हैं या अलर्ट दिखा सकते हैं
        await query.answer("कृपया /stats कमांड का उपयोग करें।", show_alert=True)

    elif data == "owner_info":
        await query.message.edit_caption(caption=script.MY_OWNER_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('« Back', callback_data='about')]]))
