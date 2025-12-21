from hydrogram import Client, filters, enums
from info import INDEX_CHANNELS
from database.ia_filterdb import (
    save_file,
    get_file_details,
    update_file_caption,
    update_file_quality
)

# ======================================================
# 🎥 VIDEO QUALITY DETECTOR (sync with index.py)
# ======================================================
def detect_video_quality(text: str) -> str:
    if not text:
        return "unknown"
    t = text.lower()
    if "2160" in t or "4k" in t:
        return "2160p"
    if "1080" in t:
        return "1080p"
    if "720" in t:
        return "720p"
    if "480" in t:
        return "480p"
    return "unknown"

# ======================================================
# 📥 CHANNEL AUTO INDEX HANDLER
# ======================================================
@Client.on_message(filters.chat(INDEX_CHANNELS))
async def channel_media_handler(bot, message):
    if message.empty or not message.media:
        return

    # ================= VIDEO =================
    if message.media == enums.MessageMediaType.VIDEO:
        media = message.video
        src_text = f"{media.file_name or ''} {message.caption or ''}"
        media.quality = detect_video_quality(src_text)

    # ================= DOCUMENT (PDF / PHP) =================
    elif message.media == enums.MessageMediaType.DOCUMENT:
        media = message.document
        if not media or not media.file_name:
            return

        name = media.file_name.lower()
        if not (name.endswith(".pdf") or name.endswith(".php")):
            return

    # ================= BLOCK EVERYTHING ELSE =================
    else:
        return

    media.caption = message.caption
    status = await save_file(media)

    # ================= EMOJI FEEDBACK =================
    try:
        if status == "suc":
            await message.react("✅")
        elif status == "dup":
            await message.react("♻️")
    except:
        pass

# ======================================================
# ✏️ CAPTION EDIT HANDLER (QUALITY RE-DETECT)
# ======================================================
@Client.on_edited_message(filters.chat(INDEX_CHANNELS))
async def channel_caption_edit_handler(bot, message):
    if not message.media or not message.caption:
        return

    # ================= MEDIA TYPE =================
    if message.media == enums.MessageMediaType.VIDEO:
        media = message.video
        src_text = f"{media.file_name or ''} {message.caption}"
        new_quality = detect_video_quality(src_text)

    elif message.media == enums.MessageMediaType.DOCUMENT:
        media = message.document
        if not media or not media.file_name:
            return

        name = media.file_name.lower()
        if not (name.endswith(".pdf") or name.endswith(".php")):
            return

        new_quality = None  # documents don't need quality

    else:
        return

    file_id = media.file_id

    # ================= CHECK EXISTENCE =================
    file = await get_file_details(file_id)
    if not file:
        return

    # ================= UPDATE DB =================
    await update_file_caption(file_id, message.caption)

    if new_quality:
        await update_file_quality(file_id, new_quality)

    # ================= EMOJI FEEDBACK =================
    try:
        await message.react("✏️")
    except:
        pass
