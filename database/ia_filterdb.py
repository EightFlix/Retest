import logging
import re
import time
import base64
from struct import pack
from difflib import get_close_matches

from pymongo import MongoClient, TEXT
from pymongo.errors import DuplicateKeyError
from hydrogram.file_id import FileId

from info import (
    FILES_DATABASE_URL,
    DATABASE_NAME,
    COLLECTION_NAME,
    MAX_BTN,
    USE_CAPTION_FILTER
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DATABASE (SINGLE DB – FASTEST)
# ─────────────────────────────────────────────
client = MongoClient(FILES_DATABASE_URL, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

collection.create_index([("file_name", TEXT), ("caption", TEXT)], name="text_index")

# ─────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────
SEARCH_CACHE = {}
CACHE_TTL = 60  # seconds

def cache_get(key):
    v = SEARCH_CACHE.get(key)
    if not v:
        return None
    data, ts = v
    if time.time() - ts > CACHE_TTL:
        SEARCH_CACHE.pop(key, None)
        return None
    return data

def cache_set(key, value):
    SEARCH_CACHE[key] = (value, time.time())

# ─────────────────────────────────────────────
# QUALITY DETECT (NO ML – FAST)
# ─────────────────────────────────────────────
def detect_quality(name: str, caption: str = "") -> str:
    text = f"{name} {caption}".lower()

    if "2160" in text or "4k" in text:
        return "2160p"
    if "1080" in text:
        return "1080p"
    if "720" in text:
        return "720p"
    if "hdr" in text:
        return "HDR"
    return "SD"

# ─────────────────────────────────────────────
# FILE ID UTILS
# ─────────────────────────────────────────────
def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    return encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )

# ─────────────────────────────────────────────
# SAVE FILE (DUP SAFE)
# ─────────────────────────────────────────────
async def save_file(media, quality=None):
    file_id = unpack_new_file_id(media.file_id)

    name = re.sub(r"@\w+|[_\-.+]", " ", media.file_name or "").strip()
    cap = re.sub(r"@\w+|[_\-.+]", " ", media.caption or "").strip()

    doc = {
        "_id": file_id,
        "file_name": name,
        "file_size": media.file_size,
        "caption": cap,
        "quality": quality or detect_quality(name, cap),
        "indexed_at": time.time()
    }

    try:
        collection.insert_one(doc)
        return "suc"
    except DuplicateKeyError:
        return "dup"
    except Exception as e:
        logger.error(f"SAVE ERROR: {e}")
        return "err"

# ─────────────────────────────────────────────
# UPDATE CAPTION (EDIT SUPPORT)
# ─────────────────────────────────────────────
async def update_file_caption(file_id, new_caption, quality=None):
    cap = re.sub(r"@\w+|[_\-.+]", " ", new_caption or "").strip()

    res = collection.update_one(
        {"_id": unpack_new_file_id(file_id)},
        {
            "$set": {
                "caption": cap,
                "quality": quality or detect_quality("", cap),
                "updated_at": time.time()
            }
        }
    )
    return res.modified_count > 0

# ─────────────────────────────────────────────
# SEARCH (TEXT + FUZZY)
# ─────────────────────────────────────────────
async def get_search_results(query, offset=0, max_results=MAX_BTN):
    q = query.lower().strip()
    if len(q) < 2:
        return [], "", 0

    cache_key = f"{q}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    files = []
    total = 0

    try:
        cursor = collection.find(
            {"$text": {"$search": q}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]) \
         .skip(offset).limit(max_results)

        files = list(cursor)
        total = collection.count_documents({"$text": {"$search": q}})
    except Exception:
        files = []

    # ─── REGEX FALLBACK ───
    if not files:
        regex = re.compile(re.escape(q), re.I)
        flt = (
            {"$or": [{"file_name": regex}, {"caption": regex}]}
            if USE_CAPTION_FILTER
            else {"file_name": regex}
        )
        files = list(collection.find(flt).skip(offset).limit(max_results))
        total = collection.count_documents(flt)

    # ─── FUZZY RETRY (ML-LESS) ───
    if not files:
        try:
            names = collection.distinct("file_name")
            close = get_close_matches(q, names, n=1, cutoff=0.72)
            if close:
                return await get_search_results(close[0], offset, max_results)
        except:
            pass

    next_offset = offset + max_results if total > offset + max_results else ""
    result = (files[:max_results], next_offset, total)
    cache_set(cache_key, result)
    return result

# ─────────────────────────────────────────────
# FILE DETAILS
# ─────────────────────────────────────────────
async def get_file_details(file_id):
    return collection.find_one({"_id": file_id})

# ─────────────────────────────────────────────
# DELETE FILES (ADMIN)
# ─────────────────────────────────────────────
async def delete_files(query):
    regex = re.compile(re.escape(query), re.I)
    res = collection.delete_many({"file_name": regex})
    return res.deleted_count

# ─────────────────────────────────────────────
# COUNT
# ─────────────────────────────────────────────
def db_count_documents():
    return collection.estimated_document_count()
