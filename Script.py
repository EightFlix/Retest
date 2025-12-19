class script(object):

    START_TXT = """<b>ʜᴇʏ {}, <i>{}</i><br>    <br>ɪ ᴀᴍ ᴘᴏᴡᴇʀғᴜʟ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ᴡɪᴛʜ ʟɪɴᴋ sʜᴏʀᴛᴇɴᴇʀ ʙᴏᴛ. ʏᴏᴜ ᴄᴀɴ ᴜꜱᴇ ᴀꜱ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ᴡɪᴛʜ ʟɪɴᴋ sʜᴏʀᴛᴇɴᴇʀ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ... ɪᴛ'ꜱ ᴇᴀꜱʏ ᴛᴏ ᴜꜱᴇ ᴊᴜsᴛ ᴀᴅᴅ ᴍᴇ ᴀꜱ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ ɪ ᴡɪʟʟ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇʀᴇ ᴍᴏᴠɪᴇꜱ ᴡɪᴛʜ ʏᴏᴜʀ ʟɪɴᴋ ꜱʜᴏʀᴛᴇɴᴇʀ... ♻️</b>"""

    MY_ABOUT_TXT = """★ Server: <a href=https://www.heroku.com>Heroku</a><br>★ Database: <a href=https://www.mongodb.com>MongoDB</a><br>★ Language: <a href=https://www.python.org>Python</a><br>★ Library: <a href=https://t.me/HydrogramNews>Hydrogram</a>"""

    MY_OWNER_TXT = """★ Name: HA Bots<br>★ Username: @HA_Bots<br>★ Country: Sri Lanka 🇱🇰"""

    STATUS_TXT = """👤 Total Users: <code>{}</code><br>😎 Premium Users: <code>{}</code><br>👥 Total Chats: <code>{}</code><br>🗳 Data database used: <code>{}</code><br><br>🗂 1st database Files: <code>{}</code><br>🗳 1st files database used: <code>{}</code><br><br>🗂 2nd database Files: <code>{}</code><br>🗳 2nd files database used: <code>{}</code><br><br>🚀 Bot Uptime: <code>{}</code>"""

    NEW_GROUP_TXT = """#NewGroup<br>Title - {}<br>ID - <code>{}</code><br>Username - {}<br>Total - <code>{}</code>"""

    NEW_USER_TXT = """#NewUser<br>★ Name: {}<br>★ ID: <code>{}</code>"""

    NOT_FILE_TXT = """👋 Hello {},<br><br>I can't find the <b>{}</b> in my database! 🥲<br><br>👉 Google Search and check your spelling is correct.<br>👉 Please read the Instructions to get better results.<br>👉 Or not been released yet."""
    
    IMDB_TEMPLATE = """✅ I Found: <code>{query}</code><br><br>🏷 Title: <a href={url}>{title}</a><br>🎭 Genres: {genres}<br>📆 Year: <a href={url}/releaseinfo>{year}</a><br>🌟 Rating: <a href={url}/ratings>{rating} / 10</a><br>☀️ Languages: {languages}<br>📀 RunTime: {runtime} Minutes<br><br>🗣 Requested by: {message.from_user.mention}<br>©️ Powered by: <b>{message.chat.title}</b>"""

    FILE_CAPTION = """<i>{file_name}</i><br><br>🚫 ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ᴄʟᴏsᴇ ʙᴜᴛᴛᴏɴ ɪꜰ ʏᴏᴜ ʜᴀᴠᴇ sᴇᴇɴ ᴛʜᴇ ᴍᴏᴠɪᴇ 🚫"""

    WELCOME_TEXT = """👋 Hello {mention}, Welcome to {title} group! 💞"""

    HELP_TXT = """👋 Hello {},<br>    <br>I can filter movie and series you want<br>Just type you want movie or series in my PM or adding me in to group<br>And i have more feature for you<br>Just try my commands"""

    ADMIN_COMMAND_TXT = """<b>Here is bot admin commands 👇<br><br><br>/index_channels - to check how many index channel id added<br>/stats - to get bot status<br>/delete - to delete files using query<br>/delete_all - to delete all indexed file<br>/broadcast - to send message to all bot users<br>/grp_broadcast - to send message to all groups<br>/pin_broadcast - to send message as pin to all bot users.<br>/pin_grp_broadcast - to send message as pin to all groups.<br>/restart - to restart bot<br>/leave - to leave your bot from particular group<br>/users - to get all users details<br>/chats - to get all groups<br>/invite_link - to generate invite link<br>/index - to index bot accessible channels<br>/add_prm - to add new premium user<br>/rm_prm - to remove premium user<br>/delreq - to delete join request in db<br>/set_req_fsub - to set request force subscribe channel<br>/set_fsub - to set force subscribe channels</b>"""
    
    PLAN_TXT = """Activate any premium plan to get exclusive features.<br><br>You can activate any premium plan and then you can get exclusive features.<br><br>- INR {} for pre day -<br><br>Basic premium features:<br>Ad free experience<br>Online watch and fast download<br>No need join channels<br>No need verify<br>No shortlink<br>Admins support<br>And more...<br><br>Support: {}"""

    USER_COMMAND_TXT = """<b>यहाँ बॉट के एडवांस टूल्स और कमांड्स हैं 👇</b>

<b>🖼️ Permanent Links (हमेशा के लिए):</b>
• /graph - Graph.org (Max 5MB - बेस्ट फॉर इमेजेज)
• /ct - Catbox (Max 200MB - बेस्ट फॉर फाइल्स)

<b>⏳ Temporary Links (समय सीमा के साथ):</b>
• /lt - Litterbox (24 घंटे बाद डिलीट, 1GB लिमिट)
• /go - GoFile (24 घंटे बाद डिलीट, कोई साइज लिमिट नहीं)
• /trans - Transfer.sh (14 दिन तक वैध, 10GB लिमिट)
• /img_2_link - Uguu.se (24 घंटे बाद डिलीट, 100MB लिमिट)

<b>⚙️ अन्य कमांड्स:</b>
• /start - बॉट की स्थिति जांचें
• /myplan - अपना प्रीमियम प्लान देखें
• /plan - प्रीमियम प्लान की जानकारी
• /settings - ग्रुप सेटिंग्स बदलें
• /connect - ग्रुप को PM से जोड़ें
• /id - चैट या फाइल की ID प्राप्त करें</b>"""
    
    SOURCE_TXT = """<b>ʙᴏᴛ ɢɪᴛʜᴜʙ ʀᴇᴘᴏsɪᴛᴏʀʏ -<br><br>- ᴛʜɪꜱ ʙᴏᴛ ɪꜱ ᴀɴ ᴏᴘᴇɴ ꜱᴏᴜʀᴄᴇ ᴘʀᴏᴊᴇᴄᴛ.<br><br>- ꜱᴏᴜʀᴄᴇ - <a href=https://github.com/HA-Bots/Auto-Filter-Bot>ʜᴇʀᴇ</a><br><br>- ᴅᴇᴠʟᴏᴘᴇʀ - @HA_Bots"""
