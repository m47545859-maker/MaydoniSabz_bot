import os
import logging
import asyncio

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from supabase import create_client, Client


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("MaydoniSabz")


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]

SUPABASE_URL = os.environ["SUPABASE_URL"]

SUPABASE_SERVICE_ROLE_KEY = os.environ[
    "SUPABASE_SERVICE_ROLE_KEY"
]

PORT = int(
    os.environ.get("PORT", "10000")
)

RENDER_EXTERNAL_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "https://maydonisabz-bot.onrender.com"
)

WEBHOOK_PATH = "/telegram"

WEBHOOK_URL = (
    RENDER_EXTERNAL_URL.rstrip("/")
    + WEBHOOK_PATH
)


# =========================================================
# SUPABASE
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# =========================================================
# TELEGRAM APPLICATION
# =========================================================

application = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)
    .build()
)


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    try:

        user_data = {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name or "",
        }

        logger.info(
            "Saving user: telegram_id=%s username=%s",
            user.id,
            user.username
        )

        result = (
            supabase
            .table("users")
            .upsert(
                user_data,
                on_conflict="telegram_id"
            )
            .execute()
        )

        logger.info(
            "Supabase response: %s",
            result
        )

        if update.message:

            await update.message.reply_text(
                f"👋 Салом, {user.first_name or 'дӯст'}!\n\n"
                "⚽ Хуш омадед ба «МАЙДОНИ САБЗ»!\n\n"
                "Дар ин ҷо шумо метавонед барои "
                "бозиҳои футбол пешгӯӣ гузоред "
                "ва хол ҷамъ кунед."
            )

    except Exception as e:

        logger.exception(
            "SUPABASE ERROR: %r",
            e
        )

        if update.message:

            await update.message.reply_text(
                "⚠️ Хатогӣ ҳангоми пайвастшавӣ "
                "ба система."
            )


# =========================================================
# /MYID
# =========================================================

async def myid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    username = (
        f"@{user.username}"
        if user.username
        else "надорад"
    )

    if update.message:

        await update.message.reply_text(
            f"🆔 Telegram ID: {user.id}\n"
            f"👤 Ном: {user.first_name or ''}\n"
            f"🔹 Username: {username}"
        )


# =========================================================
# /HEALTH
# =========================================================

async def health_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message:

        await update.message.reply_text(
            "✅ MaydoniSabz bot фаъол аст."
        )


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

async def telegram_webhook(
    request: Request
):

    try:

        data = await request.json()

        telegram_update = Update.de_json(
            data,
            application.bot
        )

        await application
