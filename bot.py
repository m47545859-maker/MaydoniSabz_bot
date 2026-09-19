import os
import logging

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
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
# ENV
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

PORT = int(os.environ.get("PORT", "10000"))

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
# TELEGRAM
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
            "Saving user: %s",
            user.id
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
            "SUPABASE ERROR: %s",
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

        await application.update_queue.put(
            telegram_update
        )

        return Response(
            status_code=200
        )

    except Exception as e:
        logger.exception(
            "WEBHOOK ERROR: %s",
            e
        )

        return Response(
            content="error",
            status_code=500
        )


# =========================================================
# HEALTH CHECK
# =========================================================

async def health(
    request: Request
):

    return PlainTextResponse(
        "MaydoniSabz bot is running!"
    )


# =========================================================
# ROOT
# =========================================================

async def root(
    request: Request
):

    return PlainTextResponse(
        "MaydoniSabz Bot"
    )


# =========================================================
# WEB SERVER
# =========================================================

web_app = Starlette(
    routes=[
        Route(
            "/",
            root,
            methods=["GET"]
        ),
        Route(
            "/health",
            health,
            methods=["GET"]
        ),
        Route(
            WEBHOOK_PATH,
            telegram_webhook,
            methods=["POST"]
        ),
    ]
)


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "Starting MaydoniSabz bot..."
    )

    logger.info(
        "Webhook: %s",
        WEBHOOK_URL
    )

    logger.info(
        "Port: %s",
        PORT
    )

    # Handlers
    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("myid", myid)
    )

    application.add_handler(
        CommandHandler("health", health_command)
    )

    # Initialize Telegram
    await application.initialize()

    # Set webhook
    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

    logger.info(
        "Webhook configured successfully."
    )

    # Start Telegram application
    await application.start()

    logger.info(
        "Telegram application started."
    )

    # Start web server
    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )

    server = uvicorn.Server(config)

    logger.info(
        "Starting web server..."
    )

    try:
        await server.serve()

    finally:
        logger.info(
            "Stopping bot..."
        )

        await application.stop()
        await application.shutdown()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
