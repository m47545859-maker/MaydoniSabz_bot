import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client, Client

BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Create/update the Telegram user in Supabase.
    supabase.table("users").upsert({
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
    }, on_conflict="telegram_id").execute()

    await update.message.reply_text(
        "🌿 Салом, дӯстдори футбол!\n\n"
        "Хуш омадед ба «МАЙДОНИ САБЗ» ⚽\n\n"
        "Аз ин ҷо шумо метавонед ба сайти пешгӯиҳо гузаред "
        "ва барои бозиҳо пешгӯӣ кунед."
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🆔 Telegram ID-и шумо: {user.id}\n"
        f"👤 Ном: {user.first_name or '—'}\n"
        f"🔗 Username: @{user.username}" if user.username else
        f"🆔 Telegram ID-и шумо: {user.id}\n"
        f"👤 Ном: {user.first_name or '—'}"
    )


async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))

    print("MaydoniSabz bot started...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
