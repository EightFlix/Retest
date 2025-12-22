import re
import base64
from struct import pack
from typing import List, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT
from pymongo.errors import DuplicateKeyError

from hydrogram.file_id import FileId
from info import DATA_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, MAX_BTN


# ======================================================
# DATABASE INIT
# ======================================================

client = AsyncIOMotorClient(DATA_DATABASE_URL)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]


# ======================================================
# INDEXES (IMPORTANT FOR SPEED)
# ======================================================

async def init_db():
    try:
        await collection.create_index(
            [
                ("file_name", TEXT),
                ("caption", TEXT)
            ],
            name="text_index",
            default_language="english"
        )
        await collection.create_index("file_unique_id", unique=True)
        await collection.create_index("file_id")
    except:
        pass


# ======================================================
# REGEX HELPERS
# ======================================================

RE_SPECIAL = re.compile(r"[._\-]+")
RE_TAGS = re.compile(r"@\w+")
RE_BRACKETS = re.compile(r"[\[\(\{].*?[\]\)\}]")
RE_EXT = re.compile(r"\.(mkv|mp4|avi|m4v|webm|flv)$", re.I)


def normalize(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = RE_TAGS.sub("", text)
    text = RE_BRACKETS.sub("", text)
    text = RE_EXT.sub("", text)
    text = RE_SPECIAL.sub(" ", text)
    return " ".join(text.split())


# ======================================================
# FILE ID ENCODE / DECODE
# ======================================================

def encode_file_id(file_id: str) -> str:
    return base64.urlsafe_b64encode(
        pack(">i", int(file_id))
    ).decode().rstrip("=")


def decode_file_id(file_id: str) -> int:
    return FileId.decode(file_id).media_id


# ======================================================
# SAVE FILE
# ======================================================

async def save_file(media, caption: str = ""):
    try:
        file_id = media.file_id
        file_unique_id = media.file_unique_id
        file_name = media.file_name or "file"
        file_size = media.file_size or 0

        doc = {
            "_id": file_unique_id,
            "file_id": file_id,
            "file_unique_id": file_unique_id,
            "file_name": file_name,
            "caption": caption or "",
            "file_size": file_size,
            "search": normalize(file_name + " " + (caption or ""))
        }

        await collection.insert_one(doc)
        return True

    except DuplicateKeyError:
        return False

    except:
        return False


# ======================================================
# GET FILE DETAILS
# ======================================================

async def get_file_details(file_id: str):
    return await collection.find_one(
        {"file_id": file_id},
        {
            "_id": 0,
            "file_id": 1,
            "file_name": 1,
            "caption": 1,
            "file_size": 1
        }
    )


# ======================================================
# SEARCH CORE (FAST)
# ======================================================

async def get_search_results(
    query: str,
    offset: int = 0,
    max_results: int = MAX_BTN
) -> Tuple[List[dict], int, int]:

    query = normalize(query)
    if not query:
        return [], 0, 0

    q = {
        "$text": {
            "$search": query
        }
    }

    total = await collection.count_documents(q)

    cursor = (
        collection.find(q, {"_id": 0})
        .skip(offset)
        .limit(max_results)
    )

    files = await cursor.to_list(length=max_results)

    next_offset = offset + max_results if offset + max_results < total else 0

    return files, next_offset, total


# ======================================================
# DELETE FILE
# ======================================================

async def delete_files(file_ids: List[str]) -> int:
    result = await collection.delete_many(
        {"file_unique_id": {"$in": file_ids}}
    )
    return result.deleted_count


# ======================================================
# COUNT DOCUMENTS
# ======================================================

async def db_count_documents() -> int:
    return await collection.count_documents({})
