import os
import aiohttp
import asyncio
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp

# API URLs
CATBOX_URL = "https://catbox.moe/user/api.php"
LITTERBOX_URL = "https://litterbox.catbox.moe/resources/internals/api.php"

@Client.on_message(filters.command(['gofile', 'go']) & filters.private)
async def gofile_handler(bot, message):
    """GoFile: Updated API Fix (24h Expiry)"""
    if not message.reply_to_message:
        return await message.reply("<b>❌ कृपया फाइल पर रिप्लाई करें।</b>")
    
    msg = await message.reply("<b>⚡ GoFile (New API) पर अपलोड हो रहा है...</b>")
    path = await message.reply_to_message.download()
    
    try:
        async with aiohttp.ClientSession() as session:
            # GoFile New API: अब सीधा store1.gofile.io या उपलब्ध सर्वर का उपयोग करें
            data = aiohttp.FormData()
            data.add_field('file', open(path, 'rb'))
            
            # नई API के अनुसार अपलोड रिक्वेस्ट
            async with session.post('https://store1.gofile.io/contents/uploadfile', data=data) as r:
                res = await r.json()
                
                if res.get('status') == 'ok':
                    link = res['data']['downloadPage']
                    await msg.edit(f"<b>✅ ɢᴏғɪʟᴇ ʟɪɴᴋ (Updated):\n\n<code>{link}</code></b>")
                else:
                    await msg.edit(f"<b>❌ GoFile एरर: {res.get('status')}</b>")
    except Exception as e:
        await msg.edit(f"<b>❌ GoFile सिस्टम एरर: {e}</b>")
    finally:
        if os.path.exists(path): os.remove(path)

@Client.on_message(filters.command('trans') & filters.private)
async def transfer_sh_handler(bot, message):
    """Transfer.sh: Fix with Timeout (10GB Limit)"""
    if not message.reply_to_message:
        return await message.reply("<b>❌ फाइल पर रिप्लाई करें।</b>")
    
    msg = await message.reply("<b>⚡ Transfer.sh पर अपलोड हो रहा है (Max 10GB)...</b>")
    path = await message.reply_to_message.download()
    file_name = os.path.basename(path)
    
    # बड़ी फाइलों के लिए अधिक समय (Timeout) देना ज़रूरी है
    timeout = aiohttp.ClientTimeout(total=1800) # 30 मिनट
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            with open(path, 'rb') as f:
                async with session.put(f'https://transfer.sh/{file_name}', data=f) as r:
                    if r.status == 200:
                        link = await r.text()
                        await msg.edit(f"<b>✅ ᴛʀᴀɴsғᴇʀ.sʜ ʟɪɴᴋ:\n\n<code>{link.strip()}</code></b>")
                    else:
                        await msg.edit(f"<b>❌ Transfer.sh व्यस्त है (Status: {r.status})। बाद में प्रयास करें।</b>")
    except Exception as e:
        await msg.edit(f"<b>❌ Transfer.sh एरर: {e}</b>")
    finally:
        if os.path.exists(path): os.remove(path)

# पुराने वर्किंग कमांड्स (/ct, /lt, /graph) को वैसे ही रहने दें...

