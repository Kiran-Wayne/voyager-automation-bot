print(">>> Voyager Assistant starting!")

import os
import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request
import uvicorn

def get_timestamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from dotenv import load_dotenv

load_dotenv()


# =====================================================
# CONFIGURATION
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
RENDER_URL = os.getenv("RENDER_URL")
application = None

USERS_FILE = "users.json"
LOG_FILE = "message_logs.jsonl"


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_timestamp():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

# =====================================================
# USER MANAGEMENT
# =====================================================

def load_users():

    if not os.path.exists(USERS_FILE):
        return {
            "approved_users": {},
            "pending_users": {}
        }

    try:
        with open(USERS_FILE, "r") as file:
            return json.load(file)

    except Exception:
        return {
            "approved_users": {},
            "pending_users": {}
        }



def save_users(users):

    with open(USERS_FILE, "w") as file:
        json.dump(
            users,
            file,
            indent=4
        )



def is_admin(user_id):

    return user_id == ADMIN_ID



def is_approved(user_id):

    users = load_users()

    return str(user_id) in users["approved_users"]



def add_pending_user(user):


    users = load_users()

    user_id = str(user.id)


    if user_id not in users["pending_users"]:

        users["pending_users"][user_id] = {
            "username": user.username or "unknown",
            "requested_at": get_timestamp()
        }

        save_users(users)



def approve_user(user_id):

    users = load_users()

    user_id = str(user_id)


    if user_id in users["pending_users"]:

        user_data = users["pending_users"].pop(user_id)


        users["approved_users"][user_id] = {
            "username": user_data["username"],
            "approved_at": get_timestamp(),
            "role": "user"
        }

    save_users(users)



def reject_user(user_id):

    users = load_users()

    user_id = str(user_id)


    if user_id in users["pending_users"]:
        users["pending_users"].pop(user_id)


    save_users(users)
# =====================================================
# MESSAGE LOGGING
# =====================================================

def save_log(data):

    data["timestamp"] = datetime.now(
        timezone.utc
    ).isoformat()

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(
            json.dumps(data)
            + "\n"
        )



# =====================================================
# BASIC RESPONSES
# =====================================================

WELCOME_MESSAGE = """
🚀 Welcome to Voyager Assistant

Your access request has been submitted.

Please wait for administrator approval.
"""


ACCESS_GRANTED_MESSAGE = """
✅ Access Granted!

Welcome to Voyager Assistant 🚀

You can now use available bot features.
"""


ACCESS_DENIED_MESSAGE = """
⛔ Access denied.

Please contact administrator.
"""
# =====================================================
# TELEGRAM COMMAND HANDLERS
# =====================================================

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = user.id
    username = user.username or "unknown"

    logging.info(
        f"Start request from {username} ({user_id})"
    )

    # Admin
    if is_admin(user_id):
        await update.message.reply_text(
            "👑 Voyager Admin Console Activated 🚀"
        )
        return


    # Already approved
    if is_approved(user_id):

        await update.message.reply_text(
            ACCESS_GRANTED_MESSAGE
        )
        return


    # New user request
    add_pending_user(user)


    await update.message.reply_text(
        WELCOME_MESSAGE
    )


    # Notify admin
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"approve_{user_id}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"reject_{user_id}"
            )
        ]
    ]


    await context.bot.send_message(
        ADMIN_ID,
        f"""
🔔 New Access Request

👤 Username:
@{username}

🆔 User ID:
{user_id}
        """,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )



# =====================================================
# ADMIN APPROVAL CALLBACK
# =====================================================

async def approval_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()


    if not is_admin(query.from_user.id):
        return


    action, user_id = query.data.split("_")

    user_id = int(user_id)


    if action == "approve":

        approve_user(user_id)


        await context.bot.send_message(
            user_id,
            ACCESS_GRANTED_MESSAGE
        )


        await query.edit_message_text(
            f"✅ User {user_id} approved."
        )


    elif action == "reject":

        reject_user(user_id)


        await context.bot.send_message(
            user_id,
            ACCESS_DENIED_MESSAGE
        )


        await query.edit_message_text(
            f"❌ User {user_id} rejected."
        )



# =====================================================
# ADMIN COMMANDS
# =====================================================

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return

    users = load_users()

    approved = users["approved_users"]
    pending = users["pending_users"]

    message = "👥 Voyager User Management\n\n"


    message += "✅ Approved Users:\n"

    if approved:
        for uid, data in approved.items():
            message += (
                f"\n👤 @{data['username']}"
                f"\n🆔 {uid}"
                f"\n📅 {data['approved_at'][:10]}\n"
            )
    else:
        message += "\nNo approved users."


    message += "\n\n⏳ Pending Requests:\n"

    if pending:
        for uid, data in pending.items():
            message += (
                f"\n👤 @{data['username']}"
                f"\n🆔 {uid}"
                f"\n📅 {data['requested_at'][:10]}\n"
            )
    else:
        message += "\nNo pending requests."


    await update.message.reply_text(message)



async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return


    users = load_users()

    approved_count = len(users["approved_users"])
    pending_count = len(users["pending_users"])


    await update.message.reply_text(
        f"""
📊 Voyager Statistics

👥 Total Users:
{approved_count + pending_count}

✅ Approved:
{approved_count}

⏳ Pending:
{pending_count}

🤖 Status:
Online
"""
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = str(user.id)

    # Admin profile
    if is_admin(user.id):

        await update.message.reply_text(
            f"""
👑 Voyager Admin Profile

Username:
@{user.username}

User ID:
{user.id}

Role:
Administrator

Status:
Active
"""
        )
        return

async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return


    if not context.args:
        await update.message.reply_text(
            "Usage:\n/userinfo USER_ID"
        )
        return


    user_id = context.args[0]

    users = load_users()


    if user_id in users["approved_users"]:

        data = users["approved_users"][user_id]

        await update.message.reply_text(
            f"""
👤 User Information

🆔 ID:
{user_id}

👤 Username:
@{data['username']}

Status:
✅ Approved

📅 Approved:
{data['approved_at'][:10]}
"""
        )

    elif user_id in users["pending_users"]:

        data = users["pending_users"][user_id]

        await update.message.reply_text(
            f"""
👤 User Information

🆔 ID:
{user_id}

👤 Username:
@{data['username']}

Status:
⏳ Pending

📅 Requested:
{data['requested_at'][:10]}
"""
        )

    else:

        await update.message.reply_text(
            "❌ User not found."
        )

# =====================================================
# USER COMMANDS
# =====================================================


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not is_approved(user_id) and not is_admin(user_id):
        await update.message.reply_text(
            "⛔ You don't have access to Voyager Assistant."
        )
        return


    await update.message.reply_text(
        """
🚀 Voyager Assistant Help

Available Commands:

/start
Start Voyager Assistant

/help
View available commands

/status
Check your account status

/profile
View your profile
"""
    )



async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id


    if is_admin(user_id):

        status = "👑 Administrator"

    elif is_approved(user_id):

        status = "✅ Approved User"

    else:

        status = "⛔ Not Approved"


    await update.message.reply_text(
        f"""
🟢 Voyager Status

Account:
{status}

Bot:
Online 🚀

Version:
1.0
"""
    )



async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = str(user.id)

    users = load_users()


    if user_id in users["approved_users"]:

        data = users["approved_users"][user_id]

        await update.message.reply_text(
            f"""
👤 Voyager Profile

Username:
@{data['username']}

User ID:
{user_id}

Status:
✅ Approved

Joined:
{data['approved_at'][:10]}
"""
        )

    elif user_id in users["pending_users"]:

        data = users["pending_users"][user_id]

        await update.message.reply_text(
            f"""
👤 Voyager Profile

Username:
@{data['username']}

User ID:
{user_id}

Status:
⏳ Pending Approval

Requested:
{data['requested_at'][:10]}
"""
        )

    else:

        await update.message.reply_text(
            """
👤 Voyager Profile

No account found.

Use /start to request access.
"""
        )

# =====================================================
# TELEGRAM APPLICATION SETUP
# =====================================================

from telegram.ext import ApplicationBuilder


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not is_approved(user.id) and not is_admin(user.id):
        await update.message.reply_text(
            "⛔ You don't have access to Voyager Assistant yet."
        )
        return


    await update.message.reply_text(
        "🚀 Voyager received your message."
    )


# =====================================================
# MAIN FUNCTION
# =====================================================

async def start_bot():

    global application


    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN missing. Add it in environment variables."
        )


    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )


    # Commands

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("users", users_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CommandHandler("userinfo", userinfo_command)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("status", status_command)
    )

    application.add_handler(
        CommandHandler("profile", profile_command)
    )


    # Approval buttons

    application.add_handler(
        CallbackQueryHandler(
            approval_handler
        )
    )


    # Text messages

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            unknown_message
        )
    )


    await application.initialize()

    await application.start()


    await application.bot.set_webhook(
        url=f"{RENDER_URL}/webhook"
    )


    logging.info(
        "🚀 Voyager webhook started"
    )


    
# =====================================================
# FASTAPI WEBHOOK SERVER
# =====================================================

app = FastAPI()
@app.on_event("startup")
async def startup_event():

    await start_bot()

@app.on_event("shutdown")
async def shutdown_event():

    await application.stop()
    await application.shutdown()


@app.get("/")
async def home():

    return {
        "status": "Voyager Assistant online 🚀"
    }


@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    update = Update.de_json(
        data,
        application.bot
    )

    await application.process_update(update)

    return {
        "status": "ok"
    }


if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000))
    )
    