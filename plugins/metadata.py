import re
from hydrogram import enums
from hydrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import get_poster, get_size, get_readable_time, temp
from info import DELETE_TIME, script

async def get_imdb_metadata(search, files, settings):
    """
    IMDb से डेटा लाता है और फॉर्मेट किया हुआ कैप्शन और पोस्टर देता है।
    """
    # IMDb सर्च और डेटा फेचिंग (utils.get_poster का उपयोग)
    imdb = await get_poster(search, file=(files[0])['file_name']) if settings["imdb"] else None
    TEMPLATE = settings.get('template', script.IMDB_TEMPLATE)
    
    if imdb:
        # सभी वेरिएबल्स को टेम्पलेट के हिसाब से मैप करना
        cap = TEMPLATE.format(
            query=search,
            title=imdb.get('title'),
            votes=imdb.get('votes'),
            aka=imdb.get("aka"),
            seasons=imdb.get("seasons"),
            box_office=imdb.get('box_office'),
            localized_title=imdb.get('localized_title'),
            kind=imdb.get('kind'),
            imdb_id=imdb.get("imdb_id"),
            cast=imdb.get("cast"),
            runtime=imdb.get("runtime"),
            countries=imdb.get("countries"),
            certificates=imdb.get("certificates"),
            languages=imdb.get("languages"),
            director=imdb.get("director"),
            writer=imdb.get("writer"),
            producer=imdb.get("producer"),
            composer=imdb.get("composer"),
            cinematographer=imdb.get("cinematographer"),
            music_team=imdb.get("music_department"),
            distributors=imdb.get("distributors"),
            release_date=imdb.get('release_date'),
            year=imdb.get('year'),
            genres=imdb.get('genres'),
            poster=imdb.get('poster'),
            plot=imdb.get('plot'),
            rating=imdb.get('rating'),
            url=imdb.get('url'),
            **locals()
        )
    else:
        # अगर IMDb नहीं मिलता तो डिफॉल्ट कैप्शन
        cap = f"<b>💭 ʜᴇʏ,\n♻️ ʜᴇʀᴇ ɪ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ sᴇᴀʀᴄʜ {search}...</b>"
    
    return cap, imdb.get('poster') if imdb else None

def get_file_list_string(files, chat_id, offset=1):
    """सर्च रिजल्ट में फाइलों की लिस्ट (links) तैयार करता है।"""
    files_link = ""
    # यहाँ फाइलों के नाम और साइज के साथ लिंक बनाए जाते हैं
    for file_num, file in enumerate(files, start=offset):
        files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{chat_id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    return files_link

def get_auto_delete_str(settings):
    """Auto-delete की सूचना वाला स्ट्रिंग तैयार करता है।"""
    if settings.get("auto_delete"):
        return f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>"
    return ""

async def send_metadata_reply(message, cap, poster, reply_markup, settings, files_link):
    """पोस्टर के साथ या बिना पोस्टर के मैसेज भेजने का लॉजिक (Error Handling के साथ)।"""
    del_msg = get_auto_delete_str(settings)
    
    # कैप्शन की लिमिट 1024 होती है, इसलिए इसे ट्रिम करना जरूरी है का उपयोग]
    full_cap = cap[:800] + files_link + del_msg
    
    if poster:
        try:
            return await message.reply_photo(
                photo=poster,
                caption=full_cap,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            # अगर मुख्य पोस्टर फेल हो जाए तो कम रेजोल्यूशन वाला ट्राई करें
            poster_low = poster.replace('.jpg', "._V1_UX360.jpg")
            return await message.reply_photo(
                photo=poster_low,
                caption=full_cap,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
        except Exception:
            # अगर फोटो बिलकुल न जाए तो सिर्फ टेक्स्ट भेजें
            return await message.reply_text(
                text=full_cap,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
    else:
        # अगर पोस्टर नहीं है तो सीधा टेक्स्ट मैसेज
        return await message.reply_text(
            text=full_cap,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
