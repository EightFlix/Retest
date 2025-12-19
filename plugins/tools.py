import os
import aiohttp
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# API URLs
CATBOX_URL = "https://catbox.moe/user/api.php"
LITTERBOX_URL = "https://litterbox.catbox.moe/resources/internals/api.php"

@Client.on_message(filters.command(['graph', 'link']) & filters.private)
async def graph_org_handler(bot, message):
    """Graph.org: Permanent (Limit: 5MB)"""
    if not message.reply_to_message or not (message.reply_to_message.photo or message.reply_to_message.video or message.reply_to_message.animation):
        return await message.reply("<b>Kripya kisi image ya 5MB se choti video par reply karein.</b>")

    # 5MB Limit Check
    media = message.reply_to_message.photo or message.reply_to_message.video or message.reply_to_message.animation
    file_size = media.file_size if not isinstance(media, list) else media[-1].file_size
    
    if file_size > 5 * 1024 * 1024:
        return await message.reply("<b>❌ Graph.org ki limit 5MB hai! Isse badi file ke liye /ct use karein.</b>")

    msg = await message.reply("<b>Graph.org par upload ho raha hai... 🚀</b>")
    path = await message.reply_to_message.download()
    
    try:
        async with aiohttp.ClientSession() as session:
            with open(path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f)
                async with session.post('https://graph.org/upload', data=data) as response:
                    res = await response.json()
                    link = "https://graph.org" + res[0]['src']
                    await msg.edit(f"<b>✅ Graph.org (Permanent Link):\n\n<code>{link}</code></b>",
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Open Link", url=link)]]))
    except Exception as e:
        await msg.edit(f"<b>❌ Graph.org error:</b> {e}")
    finally:
        if os.path.exists(path): os.remove(path)

@Client.on_message(filters.command(['litter', 'lt']) & filters.private)
async def litterbox_handler(bot, message):
    """Litterbox: 1GB (Expires in 24h) - Yeh hamesha rahega!"""
    if not message.reply_to_message:
        return await message.reply("<b>File par reply karke /lt likhein.</b>")
    
    msg = await message.reply("<b>Litterbox par upload ho raha hai (24h)... 📦</b>")
    path = await message.reply_to_message.download()
    
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('time', '24h')
            data.add_field('fileToUpload', open(path, 'rb'))
            async with session.post(LITTERBOX_URL, data=data) as response:
                link = await response.text()
                await msg.edit(f"<b>📦 Litterbox (Delete in 24h):\n\n<code>{link}</code></b>")
    except Exception as e:
        await msg.edit(f"<b>❌ Error:</b> {e}")
    finally:
        if os.path.exists(path): os.remove(path)

# Baki saare handlers (/ct, /go, /trans) niche waise hi raheinge...
