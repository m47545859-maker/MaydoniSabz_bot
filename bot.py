import os
import logging
import asyncio

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
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
logger = logging.getLogger(__name__)


# =========================================================
# ENVIRONMENT
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ADMIN_ID = int(os.environ.get("ADMIN_ID", "7321949962"))

PORT = int(os.environ.get("PORT", "10000"))

RENDER_EXTERNAL_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "https://maydonisabz-bot.onrender.com",
).rstrip("/")

WEBHOOK_PATH = "/telegram"
WEBHOOK_URL = RENDER_EXTERNAL_URL + WEBHOOK_PATH


# =========================================================
# SUPABASE
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
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
# HELPERS
# =========================================================

def safe(value, default="—"):
    if value is None or value == "":
        return default
    return str(value)


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == ADMIN_ID)


async def deny(update: Update):
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ Доступ танҳо барои администратор аст."
        )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    try:
        supabase.table("users").upsert(
            {
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name or "",
            },
            on_conflict="telegram_id",
        ).execute()

        await update.message.reply_text(
            f"👋 Салом, {user.first_name}!\n\n"
            "⚽ Хуш омадед ба «МАЙДОНИ САБЗ»!\n\n"
            "Барои пешгӯиҳо аз веб-сайт истифода баред."
        )

    except Exception:
        logger.exception("START ERROR")
        await update.message.reply_text(
            "⚠️ Хатогӣ ҳангоми пайвастшавӣ ба система."
        )


# =========================================================
# MY ID
# =========================================================

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    await update.message.reply_text(
        f"🆔 Telegram ID: {user.id}\n"
        f"👤 Ном: {user.first_name}\n"
        f"🔹 Username: @{user.username if user.username else 'надорад'}"
    )


# =========================================================
# HEALTH
# =========================================================

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ MaydoniSabz bot фаъол аст."
    )


# =========================================================
# ADMIN MENU
# =========================================================

def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎯 Пешгӯиҳои нав",
                    callback_data="admin_predictions",
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 Истифодабарандагон",
                    callback_data="admin_users",
                ),
                InlineKeyboardButton(
                    "🏆 Рейтинг",
                    callback_data="admin_rating",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Навсозӣ",
                    callback_data="admin_menu",
                )
            ],
        ]
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny(update)
        return

    await update.message.reply_text(
        "🛠 АДМИН-ПАНЕЛЬ — МАЙДОНИ САБЗ\n\n"
        "Аз меню интихоб кунед:",
        reply_markup=admin_keyboard(),    )


# =========================================================
# PREDICTION DETAILS
# =========================================================

async def get_prediction_details(prediction):
    user = None
    match = None

    user_id = prediction.get("user_id")
    match_id = prediction.get("match_id")

    if user_id is not None:
        result = (
            supabase.table("users")
            .select(
                "id,telegram_id,username,first_name,points"
            )
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if result.data:
            user = result.data[0]

    if match_id is not None:
        result = (
            supabase.table("matches")
            .select(
                "id,home_team,away_team,match_date,"
                "match_time,competition,status,"
                "home_score,away_score"
            )
            .eq("id", match_id)
            .limit(1)
            .execute()
        )

        if result.data:
            match = result.data[0]

    return user, match


# =========================================================
# SHOW PREDICTIONS
# =========================================================

async def show_predictions(query=None, message=None):
    result = (
        supabase.table("predictions")
        .select(
            "id,user_id,match_id,predicted_home,"
            "predicted_away,predicted_scorer,"
            "points,created_at"
        )
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    predictions = result.data or []

    if not predictions:
        text = "🎯 Пешгӯиҳо ҳоло вуҷуд надоранд."

        if query:
            await query.edit_message_text(
                text,
                reply_markup=admin_keyboard(),
            )
        elif message:
            await message.reply_text(
                text,
                reply_markup=admin_keyboard(),
            )

        return

    pending = [
        p for p in predictions
        if p.get("points") is None
    ]

    if not pending:
        text = (
            "✅ Ҳамаи пешгӯиҳои охирин "
            "аллакай баррасӣ шудаанд."
        )

        if query:
            await query.edit_message_text(
                text,
                reply_markup=admin_keyboard(),
            )
        elif message:
            await message.reply_text(
                text,
                reply_markup=admin_keyboard(),
            )

        return

    if query:
        await query.edit_message_text(
            f"🎯 Пешгӯиҳои интизори тасдиқ: {len(pending)}"
        )

    target = query.message if query else message

    for prediction in pending[:10]:
        user, match = await get_prediction_details(prediction)

        user_name = safe(
            (user or {}).get("first_name")
            or (user or {}).get("username"),
            "Истифодабаранда",
        )

        telegram_id = safe(
            (user or {}).get("telegram_id")
        )

        home = safe(
            (match or {}).get("home_team"),
            "Дастаи 1",
        )

        away = safe(
            (match or {}).get("away_team"),
            "Дастаи 2",
        )

        predicted_home = safe(
            prediction.get("predicted_home")
        )

        predicted_away = safe(
            prediction.get("predicted_away")
        )

        text = (
            "🔔 <b>ПЕШГӮИИ НАВ</b>\n\n"
            f"👤 {user_name}\n"
            f"🆔 {telegram_id}\n"
            f"⚽ {home} — {away}\n"
            f"🎯 Пешгӯӣ: "
            f"<b>{predicted_home}:{predicted_away}</b>\n"
            f"🆔 Prediction ID: "
            f"<code>{prediction['id']}</code>"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Дуруст +1",
                        callback_data=(
                            f"award:{prediction['id']}:1"
                        ),
                    ),
                    InlineKeyboardButton(
                        "❌ Нодуруст 0",
                        callback_data=(
                            f"award:{prediction['id']}:0"
                        ),
                    ),
                ]
            ]
        )

        await target.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# =========================================================
# USERS
# =========================================================

async def show_users(query):
    result = (
        supabase.table("users")
        .select(
            "telegram_id,username,first_name,points"
        )
        .order("points", desc=True)
        .limit(10)
        .execute()
        )    users = result.data or []

    if not users:
        await query.edit_message_text(
            "👥 Истифодабарандагон ҳоло нестанд.",
            reply_markup=admin_keyboard(),
        )
        return

    lines = ["👥 <b>ИСТИФОДАБАРАНДАГОН</b>\n"]

    for index, user in enumerate(users, 1):
        name = safe(
            user.get("first_name")
            or user.get("username"),
            "Без ном",
        )

        points = user.get("points") or 0

        lines.append(
            f"{index}. {name} — 🏆 {points}"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# RATING
# =========================================================

async def show_rating(query):
    result = (
        supabase.table("users")
        .select("first_name,username,points")
        .order("points", desc=True)
        .limit(10)
        .execute()
    )

    users = result.data or []

    if not users:
        await query.edit_message_text(
            "🏆 Рейтинг ҳоло хол надорад.",
            reply_markup=admin_keyboard(),
        )
        return

    medals = ["🥇", "🥈", "🥉"]

    lines = ["🏆 <b>РЕЙТИНГ</b>\n"]

    for index, user in enumerate(users, 1):
        name = safe(
            user.get("first_name")
            or user.get("username"),
            "Без ном",
        )

        points = user.get("points") or 0

        prefix = (
            medals[index - 1]
            if index <= 3
            else f"{index}."
        )

        lines.append(
            f"{prefix} {name} — "
            f"<b>{points}</b> хол"
        )

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# AWARD POINTS
# =========================================================

async def award_points(query, prediction_id, points):
    result = (
        supabase.table("predictions")
        .select("id,user_id,points")
        .eq("id", prediction_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        await query.answer(
            "❌ Пешгӯӣ ёфт нашуд.",
            show_alert=True,
        )
        return

    prediction = result.data[0]

    # Нельзя обработать один прогноз дважды.
    if prediction.get("points") is not None:
        await query.answer(
            "⚠️ Барои ин пешгӯӣ хол "
            "аллакай дода шудааст.",
            show_alert=True,
        )
        return

    user_id = prediction.get("user_id")

    if user_id is None:
        await query.answer(
            "❌ user_id нест.",
            show_alert=True,
        )
        return

    user_result = (
        supabase.table("users")
        .select(
            "id,telegram_id,first_name,points"
        )
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not user_result.data:
        await query.answer(
            "❌ Истифодабаранда ёфт нашуд.",
            show_alert=True,
        )
        return

    user = user_result.data[0]

    old_points = user.get("points") or 0
    new_points = old_points + points

    # Общий рейтинг пользователя.
    supabase.table("users").update(
        {
            "points": new_points
        }
    ).eq(
        "id",
        user_id,
    ).execute()

    # Результат конкретного прогноза.
    supabase.table("predictions").update(
        {
            "points": points
        }
    ).eq(
        "id",
        prediction_id,
    ).execute()

    await query.answer(
        "✅ Пешгӯӣ баррасӣ шуд."
    )

    await query.edit_message_reply_markup(
        reply_markup=None
    )

    name = safe(
        user.get("first_name"),
        "Истифодабаранда",
    )

    result_text = (
        "✅ Дуруст +1"
        if points == 1
        else "❌ Нодуруст 0"
    )

    await query.message.reply_text(
        "📋 <b>ПЕШГӮӢ БАРРАСӢ ШУД</b>\n\n"
        f"👤 {name}\n"
        f"📌 Натиҷа: <b>{result_text}</b>\n"
        f"🏆 Ҳоли умумӣ: <b>{new_points}</b>",
        parse_mode="HTML",
    )


# =========================================================
# CALLBACKS
# =========================================================
