import os
import sys
import time
import asyncio
from datetime import datetime
from collections import defaultdict

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from hydrogram.errors import MessageNotModified, MessageIdInvalid, BadRequest

from info import ADMINS, LOG_CHANNEL
from database.users_chats_db import db
from database.ia_filterdb import db_count_documents, delete_files
from utils import get_size, get_readable_time, temp


# ======================================================
# 🧠 LIVE DASHBOARD CONFIG
# ======================================================

DASH_REFRESH = 45  # seconds
DASH_CACHE = {}    # admin_id -> {"text": str, "ts": float}
DASH_LOCKS = defaultdict(asyncio.Lock)  # Prevent race conditions

# ensure index stats exists (SAFE)
if not hasattr(temp, "INDEX_STATS"):
    temp.INDEX_STATS = {
        "running": False,
        "start": 0,
        "saved": 0
    }


# ======================================================
# 🛡 SAFE OPERATIONS (IMPROVED)
# ======================================================

async def safe_edit(msg, text, **kwargs):
    """Safely edit message with error handling"""
    try:
        # Check if content is actually different
        if hasattr(msg, 'text') and msg.text == text:
            return True
        
        await msg.edit(text, **kwargs)
        return True
    except MessageNotModified:
        return True  # Already in desired state
    except (MessageIdInvalid, BadRequest) as e:
        print(f"Edit error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected edit error: {e}")
        return False


async def safe_send_log(bot, text):
    """Safely send message to log channel"""
    if not LOG_CHANNEL:
        return False
    
    try:
        await bot.send_message(LOG_CHANNEL, text)
        return True
    except Exception as e:
        print(f"Log send error: {e}")
        return False


async def safe_answer_query(query, text="", show_alert=False):
    """Safely answer callback query"""
    try:
        await query.answer(text, show_alert=show_alert)
        return True
    except Exception as e:
        print(f"Answer query error: {e}")
        return False


# ======================================================
# 📊 DASHBOARD BUILDER (OPTIMIZED)
# ======================================================

async def build_dashboard():
    """Build dashboard with individual error handling for each stat"""
    
    # Parallel stat gathering with error handling
    stats = {
        "users": 0,
        "chats": 0,
        "files": 0,
        "premium": 0,
        "used_data": "0 B",
        "uptime": "N/A",
        "now": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }
    
    # Get users count
    try:
        stats["users"] = await db.total_users_count()
    except Exception as e:
        print(f"Users count error: {e}")
    
    # Get groups count
    try:
        stats["chats"] = await asyncio.wait_for(
            asyncio.to_thread(db.groups.count_documents, {}),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        print("Groups count timeout")
    except Exception as e:
        print(f"Groups count error: {e}")
    
    # Get files count
    try:
        stats["files"] = await asyncio.wait_for(
            asyncio.to_thread(db_count_documents),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        print("Files count timeout")
    except Exception as e:
        print(f"Files count error: {e}")
    
    # Get premium users count
    try:
        stats["premium"] = await asyncio.wait_for(
            asyncio.to_thread(db.premium.count_documents, {"plan.premium": True}),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        print("Premium count timeout")
    except Exception as e:
        print(f"Premium count error: {e}")
    
    # Get database size
    try:
        db_size = await db.get_data_db_size()
        stats["used_data"] = get_size(db_size)
    except Exception as e:
        print(f"DB size error: {e}")
    
    # Calculate uptime
    try:
        stats["uptime"] = get_readable_time(time.time() - temp.START_TIME)
    except Exception as e:
        print(f"Uptime error: {e}")
    
    # Live indexing stats
    idx_text = "❌ Not running"
    try:
        idx = temp.INDEX_STATS
        if idx.get("running"):
            start_time = idx.get("start", time.time())
            dur = max(1, time.time() - start_time)
            speed = idx.get("saved", 0) / dur
            idx_text = f"🚀 {speed:.2f} files/sec"
    except Exception as e:
        print(f"Index stats error: {e}")
    
    return (
        "📊 <b>LIVE ADMIN DASHBOARD</b>\n\n"
        f"👤 <b>Users</b>        : <code>{stats['users']}</code>\n"
        f"👥 <b>Groups</b>       : <code>{stats['chats']}</code>\n"
        f"📦 <b>Indexed Files</b>: <code>{stats['files']}</code>\n"
        f"💎 <b>Premium Users</b>: <code>{stats['premium']}</code>\n\n"
        f"⚡ <b>Index Speed</b>  : <code>{idx_text}</code>\n"
        f"🗃 <b>DB Size</b>      : <code>{stats['used_data']}</code>\n\n"
        f"⏱ <b>Uptime</b>       : <code>{stats['uptime']}</code>\n"
        f"🔄 <b>Updated</b>      : <code>{stats['now']}</code>"
    )


# ======================================================
# 🎛 DASHBOARD BUTTONS
# ======================================================

def dashboard_buttons():
    """Generate dashboard inline keyboard"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="dash_refresh"),
                InlineKeyboardButton("🩺 Health", callback_data="dash_health")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="dash_broadcast"),
                InlineKeyboardButton("🗑 Delete", callback_data="dash_delete")
            ],
            [
                InlineKeyboardButton("🔄 Restart", callback_data="dash_restart"),
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
    )


# ======================================================
# 🚀 OPEN DASHBOARD (/admin, /dashboard)
# ======================================================

@Client.on_message(filters.command(["admin", "dashboard"]) & filters.user(ADMINS))
async def open_dashboard(bot, message):
    """Open admin dashboard with loading message"""
    try:
        # Show loading message
        loading_msg = await message.reply("⏳ <i>Loading dashboard...</i>")
        
        # Build dashboard
        try:
            text = await asyncio.wait_for(build_dashboard(), timeout=10.0)
        except asyncio.TimeoutError:
            await loading_msg.edit("❌ Dashboard loading timed out. Please try again.")
            return
        
        # Update with dashboard
        success = await safe_edit(
            loading_msg,
            text,
            reply_markup=dashboard_buttons(),
            disable_web_page_preview=True
        )
        
        if success:
            # Cache for this admin
            DASH_CACHE[message.from_user.id] = {
                "text": text,
                "ts": time.time()
            }
        else:
            await loading_msg.edit("❌ Failed to load dashboard")
    
    except Exception as e:
        print(f"Dashboard open error: {e}")
        try:
            await message.reply("❌ Error opening dashboard")
        except:
            pass


# ======================================================
# 🔁 DASHBOARD CALLBACKS
# ======================================================

@Client.on_callback_query(filters.regex("^dash_"))
async def dashboard_callbacks(bot, query: CallbackQuery):
    """Handle all dashboard callback actions"""
    
    # Admin verification
    if query.from_user.id not in ADMINS:
        await safe_answer_query(query, "⚠️ Not allowed", show_alert=True)
        return

    action = query.data
    admin_id = query.from_user.id
    
    try:
        # ---------- REFRESH ----------
        if action == "dash_refresh":
            # Use lock to prevent multiple simultaneous refreshes
            async with DASH_LOCKS[admin_id]:
                # Check cache
                cached = DASH_CACHE.get(admin_id)
                now = time.time()
                
                if cached and (now - cached["ts"]) < DASH_REFRESH:
                    # Use cached version
                    text = cached["text"]
                    await safe_answer_query(query, f"✅ Using cached data (refreshes every {DASH_REFRESH}s)")
                else:
                    # Build fresh dashboard
                    await safe_answer_query(query, "🔄 Refreshing...")
                    
                    try:
                        text = await asyncio.wait_for(build_dashboard(), timeout=10.0)
                        DASH_CACHE[admin_id] = {"text": text, "ts": now}
                    except asyncio.TimeoutError:
                        await safe_answer_query(query, "❌ Refresh timed out", show_alert=True)
                        return
                
                # Update message
                await safe_edit(
                    query.message,
                    text,
                    reply_markup=dashboard_buttons(),
                    disable_web_page_preview=True
                )

        # ---------- HEALTH ----------
        elif action == "dash_health":
            await safe_answer_query(query, "🩺 Running health check...")
            
            try:
                report = await asyncio.wait_for(
                    run_premium_health(False),
                    timeout=15.0
                )
                
                # Update message with report
                success = await safe_edit(
                    query.message,
                    report,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Back", callback_data="dash_back")],
                         [InlineKeyboardButton("🛠 Auto-Fix", callback_data="dash_health_fix")]]
                    )
                )
                
                # Send to log channel
                if success:
                    await safe_send_log(bot, report)
                    
            except asyncio.TimeoutError:
                await safe_edit(query.message, "❌ Health check timed out")

        # ---------- HEALTH AUTO-FIX ----------
        elif action == "dash_health_fix":
            await safe_answer_query(query, "🛠 Running auto-fix...", show_alert=True)
            
            try:
                report = await asyncio.wait_for(
                    run_premium_health(True),
                    timeout=20.0
                )
                
                await safe_edit(
                    query.message,
                    report,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Back", callback_data="dash_back")]]
                    )
                )
                
                await safe_send_log(bot, "🛠 " + report)
                
            except asyncio.TimeoutError:
                await safe_edit(query.message, "❌ Auto-fix timed out")

        # ---------- BACK TO DASHBOARD ----------
        elif action == "dash_back":
            await safe_answer_query(query)
            
            # Get latest dashboard
            try:
                text = await asyncio.wait_for(build_dashboard(), timeout=10.0)
                DASH_CACHE[admin_id] = {"text": text, "ts": time.time()}
            except asyncio.TimeoutError:
                text = "❌ Failed to load dashboard"
            
            await safe_edit(
                query.message,
                text,
                reply_markup=dashboard_buttons(),
                disable_web_page_preview=True
            )

        # ---------- BROADCAST ----------
        elif action == "dash_broadcast":
            await safe_answer_query(query)
            await safe_edit(
                query.message,
                "📢 <b>Broadcast Message</b>\n\n"
                "Reply to any message and use:\n"
                "<code>/broadcast</code>\n\n"
                "This will send the message to all users.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="dash_back")]]
                )
            )

        # ---------- DELETE ----------
        elif action == "dash_delete":
            await safe_answer_query(query)
            await safe_edit(
                query.message,
                "🗑 <b>Delete Files</b>\n\n"
                "Use command:\n"
                "<code>/delete keyword</code>\n\n"
                "⚠️ This will permanently delete all files matching the keyword.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Back", callback_data="dash_back")]]
                )
            )

        # ---------- RESTART ----------
        elif action == "dash_restart":
            await safe_answer_query(query, "🔄 Restarting bot...", show_alert=True)
            
            # Save restart info
            try:
                with open("restart.txt", "w") as f:
                    f.write(f"{query.message.chat.id}\n{query.message.id}")
            except Exception as e:
                print(f"Restart file write error: {e}")
            
            # Update message
            await safe_edit(
                query.message,
                "🔄 <b>Bot Restarting...</b>\n\n"
                "Please wait a moment."
            )
            
            # Send log
            await safe_send_log(
                bot,
                f"♻️ <b>Bot Restarted</b>\n"
                f"Admin: {query.from_user.mention}\n"
                f"Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
            )
            
            # Small delay before restart
            await asyncio.sleep(1)
            
            # Restart
            try:
                os.execl(sys.executable, sys.executable, "bot.py")
            except Exception as e:
                print(f"Restart error: {e}")
                await safe_edit(query.message, "❌ Restart failed")
        
        else:
            await safe_answer_query(query, "⚠️ Unknown action")
    
    except Exception as e:
        print(f"Dashboard callback error: {e}")
        await safe_answer_query(query, "❌ An error occurred", show_alert=True)


# ======================================================
# 🩺 PREMIUM HEALTH (OPTIMIZED)
# ======================================================

async def run_premium_health(auto_fix=False):
    """Check premium users health and optionally fix expired ones"""
    
    try:
        now = datetime.utcnow()
        
        # Get premium users with timeout
        try:
            users = await asyncio.wait_for(
                asyncio.to_thread(db.get_premium_users),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            return "❌ Premium health check timed out"
        
        total = expired = fixed = no_invoice = admin_skip = 0
        errors = 0

        for u in users:
            try:
                uid = u.get("id")
                
                # Skip admins
                if uid in ADMINS:
                    admin_skip += 1
                    continue

                plan = u.get("plan", {})
                expire = plan.get("expire")
                
                if not expire:
                    continue

                total += 1

                # Check if expired
                if expire < now:
                    expired += 1
                    
                    if auto_fix:
                        try:
                            plan.update({
                                "premium": False,
                                "expire": "",
                                "plan": "free"
                            })
                            await asyncio.to_thread(db.update_plan, uid, plan)
                            fixed += 1
                        except Exception as e:
                            print(f"Fix user {uid} error: {e}")
                            errors += 1

                # Check invoice
                if not plan.get("invoice"):
                    no_invoice += 1
            
            except Exception as e:
                print(f"Process user error: {e}")
                errors += 1
                continue

        status = "✅ Healthy" if expired == 0 else "⚠️ Issues Found"
        
        report = (
            f"🩺 <b>PREMIUM HEALTH REPORT</b>\n\n"
            f"<b>Status:</b> <code>{status}</code>\n\n"
            f"👥 Active Premium : <code>{total}</code>\n"
            f"❌ Expired Bug   : <code>{expired}</code>\n"
            f"🧾 No Invoice    : <code>{no_invoice}</code>\n"
            f"👑 Admin Skipped : <code>{admin_skip}</code>\n\n"
            f"🛠 Auto Fix      : <code>{'ON' if auto_fix else 'OFF'}</code>\n"
            f"✅ Fixed         : <code>{fixed}</code>\n"
            f"⚠️ Errors        : <code>{errors}</code>\n\n"
            f"🕒 Checked At    : <code>{now.strftime('%d %b %Y, %I:%M %p')}</code>"
        )
        
        return report
    
    except Exception as e:
        print(f"Health check error: {e}")
        return f"❌ <b>Health Check Failed</b>\n\nError: <code>{str(e)}</code>"


# ======================================================
# 🗑 SAFE DELETE (IMPROVED)
# ======================================================

@Client.on_message(filters.command("delete") & filters.user(ADMINS))
async def delete_cmd(bot, message):
    """Delete files by keyword with confirmation"""
    
    try:
        if len(message.command) < 2:
            return await message.reply(
                "⚠️ <b>Usage:</b>\n<code>/delete keyword</code>\n\n"
                "This will delete all files matching the keyword."
            )

        key = message.text.split(" ", 1)[1].strip()
        
        if not key or len(key) < 2:
            return await message.reply("⚠️ Keyword must be at least 2 characters")

        btn = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Confirm Delete", callback_data=f"del#{key}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
            ]
        )

        await message.reply(
            f"⚠️ <b>Permanent Delete Confirmation</b>\n\n"
            f"<b>Keyword:</b> <code>{key}</code>\n\n"
            f"This action cannot be undone!",
            reply_markup=btn
        )
    
    except Exception as e:
        print(f"Delete command error: {e}")
        await message.reply("❌ Error processing delete command")


@Client.on_callback_query(filters.regex("^del#"))
async def confirm_delete(bot, query: CallbackQuery):
    """Confirm and execute file deletion"""
    
    # Admin verification
    if query.from_user.id not in ADMINS:
        await safe_answer_query(query, "⚠️ Not allowed", show_alert=True)
        return
    
    try:
        key = query.data.split("#", 1)[1]
        
        await safe_answer_query(query, "🗑 Deleting files...", show_alert=True)
        await safe_edit(query.message, "⏳ <i>Deleting files, please wait...</i>")
        
        # Delete with timeout
        try:
            count = await asyncio.wait_for(
                asyncio.to_thread(delete_files, key),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            await safe_edit(query.message, "❌ Delete operation timed out")
            return
        
        # Success message
        result_text = (
            f"✅ <b>Delete Completed</b>\n\n"
            f"<b>Keyword:</b> <code>{key}</code>\n"
            f"<b>Files Removed:</b> <code>{count}</code>\n\n"
            f"<b>Deleted By:</b> {query.from_user.mention}\n"
            f"<b>Time:</b> <code>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</code>"
        )
        
        await safe_edit(query.message, result_text)
        
        # Log the deletion
        await safe_send_log(bot, result_text)
    
    except Exception as e:
        print(f"Delete confirmation error: {e}")
        await safe_edit(query.message, f"❌ <b>Delete Failed</b>\n\nError: <code>{str(e)}</code>")
