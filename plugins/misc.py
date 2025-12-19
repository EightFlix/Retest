from info import ADMINS
from speedtest import Speedtest, ConfigRetrievalError, SpeedtestBestServerFailure
from hydrogram import Client, filters, enums
from hydrogram.errors import UserNotParticipant
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import get_size
from datetime import datetime
import os


@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    replied_to_msg = bool(message.reply_to_message)
    if replied_to_msg:
        return await message.reply_text(f"""The forwarded message channel {replied_to_msg.chat.title}'s id is, <code>{replied_to_msg.chat.id}</code>.""")
    if chat_type == enums.ChatType.PRIVATE:
        await message.reply_text(f'★ User ID: <code>{message.from_user.id}</code>')

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply_text(f'★ Group ID: <code>{message.chat.id}</code>')

    elif chat_type == enums.ChatType.CHANNEL:
        await message.reply_text(f'★ Channel ID: <code>{message.chat.id}</code>')


@Client.on_message(filters.command('speedtest') & filters.user(ADMINS))
async def speedtest(client, message):
    #from - https://github.com/weebzone/WZML-X/blob/master/bot/modules/speedtest.py
    msg = await message.reply_text("Initiating Speedtest...")
    try:
        speed = Speedtest()
        speed.get_best_server()
    except (ConfigRetrievalError, SpeedtestBestServerFailure):
        await msg.edit("Can't connect to Server at the Moment, Try Again Later !")
        return
    speed.download()
    speed.upload()
    speed.results.share()
    result = speed.results.dict()
    photo = result['share']
    text = f'''
➲ <b>SPEEDTEST INFO</b>
┠ <b>Upload:</b> <code>{get_size(result['upload'])}/s</code>
┠ <b>Download:</b>  <code>{get_size(result['download'])}/s</code>
┠ <b>Ping:</b> <code>{result['ping']} ms</code>
┠ <b>Time:</b> <code>{datetime.strptime(result['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")}</code>
┠ <b>Data Sent:</b> <code>{get_size(int(result['bytes_sent']))}</code>
┖ <b>Data Received:</b> <code>{get_size(int(result['bytes_received']))}</code>

➲ <b>SPEEDTEST SERVER</b>
┠ <b>Name:</b> <code>{result['server']['name']}</code>
┠ <b>Country:</b> <code>{result['server']['country']}, {result['server']['cc']}</code>
┠ <b>Sponsor:</b> <code>{result['server']['sponsor']}</code>
┠ <b>Latency:</b> <code>{result['server']['latency']}</code>
┠ <b>Latitude:</b> <code>{result['server']['lat']}</code>
┖ <b>Longitude:</b> <code>{result['server']['lon']}</code>

➲ <b>CLIENT DETAILS</b>
┠ <b>IP Address:</b> <code>{result['client']['ip']}</code>
┠ <b>Latitude:</b> <code>{result['client']['lat']}</code>
┠ <b>Longitude:</b> <code>{result['client']['lon']}</code>
┠ <b>Country:</b> <code>{result['client']['country']}</code>
┠ <b>ISP:</b> <code>{result['client']['isp']}</code>
┖ <b>ISP Rating:</b> <code>{result['client']['isprating']}</code>
'''
    await message.reply_photo(photo=photo, caption=text)
    await msg.delete()


@Client.on_message(filters.command("info"))
async def who_is(client, message):
    status_message = await message.reply_text(
        "Fetching user info..."
    )
    if message.reply_to_message:
        from_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        from_user_id = message.command[1]
    else:
        from_user_id = message.from_user.id
    try:
        from_user = await client.get_users(from_user_id)
    except Exception as error:
        await status_message.edit(f'Error: {error}')
        return

    message_out_str = ""
    message_out_str += f"<b>➲First Name:</b> {from_user.first_name}\n"
    last_name = from_user.last_name or 'Not have'
    message_out_str += f"<b>➲Last Name:</b> {last_name}\n"
    message_out_str += f"<b>➲Telegram ID:</b> <code>{from_user.id}</code>\n"
    username = f'@{from_user.username}' if from_user.username else 'Not have'
    dc_id = from_user.dc_id or "Not found"
    message_out_str += f"<b>➲Data Centre:</b> <code>{dc_id}</code>\n"
    message_out_str += f"<b>➲Username:</b> {username}\n"
    message_out_str += f"<b>➲Last Online:</b> {last_online(from_user)}\n"
    message_out_str += f"<b>➲User 𝖫𝗂𝗇𝗄:</b> <a href='tg://user?id={from_user.id}'><b>Click Here</b></a>\n"
    if message.chat.type in [enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
        try:
            chat_member_p = await message.chat.get_member(from_user.id)
            joined_date = chat_member_p.joined_date.strftime('%Y.%m.%d %H:%M:%S') if chat_member_p.joined_date else 'Not found'
            message_out_str += (
                "<b>➲Joined this Chat on:</b> <code>"
                f"{joined_date}"
                "</code>\n"
            )
        except UserNotParticipant:
            pass
    chat_photo = from_user.photo
    if chat_photo:
        local_user_photo = await client.download_media(
            message=chat_photo.big_file_id
        )
        await message.reply_photo(
            photo=local_user_photo,
            quote=True,
            caption=message_out_str,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
        os.remove(local_user_photo)
    else:
        await message.reply_text(
            text=message_out_str,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
    await status_message.delete()



def last_online(from_user):
    time = ""
    if from_user.is_bot:
        time += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        time += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return time
