import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client, Client


BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    username = user.username
    first_name = user.first_name or ""

    try:
        supabase.table("users").upsert(
            {
                "telegram_id": user.id,
                "username": username,
                "first_name": first_name,
            },
            on_conflict="telegram_id"
        ).execute()

        await update.message.reply_text(
            f"👋 Салом, {first_name}!\n\n"
            "⚽ Хуш омадед ба «МАЙДОНИ САБЗ»!\n\n"
            "Дар ин ҷо шумо метавонед барои бозиҳои футбол "
            "пешгӯӣ гузоред ва хол ҷамъ кунед."
        )

    except Exception:
        except Exception as e:
    print("SUPABASE ERROR:", repr(e), flush=True)

    await update.message.reply_text(
        "⚠️ Хатогӣ ҳангоми пайвастшавӣ ба система."
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    await update.message.reply_text(
        f"🆔 Telegram ID: {user.id}\n"
        f"👤 Ном: {user.first_name}\n"
        f"🔹 Username: @{user.username if user.username else 'надорад'}"
    )


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ MaydoniSabz bot фаъол аст.")


def main():
    port = int(os.environ.get("PORT", "10000"))
    render_url = os.environ.get("RENDER_EXTERNAL_URL")

    if not render_url:
        raise RuntimeError("RENDER_EXTERNAL_URL not found")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("health", health))

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=render_url + "/",
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
