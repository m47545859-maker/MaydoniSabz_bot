import os
import html
import logging
from datetime import datetime

from supabase import create_client, Client

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
import uvicorn


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

ADMIN_ID = int(os.getenv("ADMIN_ID", "7321949962"))

PORT = int(os.getenv("PORT", "10000"))

WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://maydonisabz-bot.onrender.com/telegram"
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# CHECK SETTINGS
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is not set")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set")


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
# TEMPORARY ADMIN STATES
# =========================================================

# Здесь храним состояние добавления матча.
# Это нормально для текущей версии.
add_match_state = {}


# =========================================================
# HELPERS
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def admin_keyboard():
    keyboard = [
        [
            KeyboardButton("➕ Добавить матч"),
            KeyboardButton("📋 Матчи"),
        ],
        [
            KeyboardButton("🎯 Пешгӯиҳои нав"),
            KeyboardButton("👥 Истифодабарандагон"),
        ],
        [
            KeyboardButton("🏆 Рейтинг"),
            KeyboardButton("🔄 Навсозӣ"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def cancel_keyboard():
    keyboard = [
        [KeyboardButton("❌ Отмена")]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


def escape(text):
    if text is None:
        return ""

    return html.escape(str(text))


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user:
        return

    try:

        existing = (
            supabase
            .table("users")
            .select("*")
            .eq("telegram_id", user.id)
            .execute()
        )

        if not existing.data:

            supabase.table("users").insert({
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "points": 0,
            }).execute()

        else:

            supabase.table("users").update({
                "username": user.username,
                "first_name": user.first_name,
            }).eq(
                "telegram_id",
                user.id
            ).execute()

        if is_admin(user.id):

            await update.message.reply_text(
                "👑 <b>МАЙДОНИ САБЗ</b>\n\n"
                "Панели администратор фаъол аст.",
                parse_mode="HTML",
                reply_markup=admin_keyboard()
            )

        else:

            await update.message.reply_text(
                "⚽️ <b>Хуш омадед ба МАЙДОНИ САБЗ!</b>\n\n"
                "Пешгӯиҳои худро дар сомона фиристед.",
                parse_mode="HTML"
            )

    except Exception as e:

        logger.exception("START ERROR")

        await update.message.reply_text(
            "❌ Хатогӣ ҳангоми бақайдгирӣ."
        )


# =========================================================
# /MYID
# =========================================================

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user:
        return

    await update.message.reply_text(
        f"🆔 Telegram ID: <code>{user.id}</code>",
        parse_mode="HTML"
    )


# =========================================================
# /HEALTH
# =========================================================

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "✅ Бот фаъол аст.\n"
        "🗄 Supabase: подключён\n"
        "🌐 Webhook: активен"
    )


# =========================================================
# /ADMIN
# =========================================================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user or not is_admin(user.id):

        await update.message.reply_text(
            "⛔ Доступ запрещён."
        )
        return

    await update.message.reply_text(
        "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        "Интихоб кунед:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================================================
# ADD MATCH
# =========================================================

async def start_add_match(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    add_match_state[user.id] = {
        "step": "home_team"
    }

    await update.message.reply_text(
        "➕ <b>ИЛОВА КАРДАНИ МАТЧ</b>\n\n"
        "🏠 Номи дастаи соҳибхонаро нависед:\n\n"
        "Мисол:\n"
        "<code>Манчестер Сити</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )


# =========================================================
# ADD MATCH PROCESS
# =========================================================

async def process_add_match(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return False

    if user.id not in add_match_state:
        return False

    text = update.message.text.strip()

    if text == "❌ Отмена":

        add_match_state.pop(user.id, None)

        await update.message.reply_text(
            "❌ Илова кардани матч бекор шуд.",
            reply_markup=admin_keyboard()
        )

        return True

    state = add_match_state[user.id]
    step = state["step"]

    # ---------------------------------------------
    # HOME TEAM
    # ---------------------------------------------

    if step == "home_team":

        state["home_team"] = text
        state["step"] = "away_team"

        await update.message.reply_text(
            "✈️ <b>Дастаи меҳмонро нависед:</b>\n\n"
            "Мисол:\n"
            "<code>Арсенал</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )

        return True

    # ---------------------------------------------
    # AWAY TEAM
    # ---------------------------------------------

    if step == "away_team":

        state["away_team"] = text
        state["step"] = "date"

        await update.message.reply_text(
            "📅 <b>Санаи матчро нависед:</b>\n\n"
            "Формат:\n"
            "<code>2026-09-21</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )

        return True

    # ---------------------------------------------
    # DATE
    # ---------------------------------------------

    if step == "date":

        try:

            datetime.strptime(text, "%Y-%m-%d")

        except ValueError:

            await update.message.reply_text(
                "❌ Формати сана нодуруст аст.\n\n"
                "Намуна:\n"
                "<code>2026-09-21</code>",
                parse_mode="HTML",
                reply_markup=cancel_keyboard()
            )

            return True

        state["match_date"] = text
        state["step"] = "time"

        await update.message.reply_text(
            "⏰ <b>Вақти матчро нависед:</b>\n\n"
            "Вақтро бо вақти Душанбе нависед.\n\n"
            "Формат:\n"
            "<code>23:00</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )

        return True

    # ---------------------------------------------
    # TIME
    # ---------------------------------------------

    if step == "time":

        try:

            datetime.strptime(text, "%H:%M")

        except ValueError:

            await update.message.reply_text(
                "❌ Формати вақт нодуруст аст.\n\n"
                "Намуна:\n"
                "<code>23:00</code>",
                parse_mode="HTML",
                reply_markup=cancel_keyboard()
            )

            return True

        state["match_time"] = text
        state["step"] = "competition"

        await update.message.reply_text(
            "🏆 <b>Номи мусобиқаро нависед:</b>\n\n"
            "Мисол:\n"
            "<code>Премер Лига</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard()
        )

        return True

    # ---------------------------------------------
    # COMPETITION
    # ---------------------------------------------

    if step == "competition":

        state["competition"] = text

        try:

            external_id = (
                f"{state['match_date']}_"
                f"{state['match_time']}_"
                f"{state['home_team']}_"
                f"{state['away_team']}"
            )

            result = (
                supabase
                .table("matches")
                .insert({
                    "external_id": external_id,
                    "home_team": state["home_team"],
                    "away_team": state["away_team"],
                    "match_date": state["match_date"],
                    "match_time": state["match_time"],
                    "competition": state["competition"],
                    "status": "upcoming",
                    "home_score": None,
                    "away_score": None,
                })
                .execute()
            )

            match = result.data[0] if result.data else None

            add_match_state.pop(user.id, None)

            if match:

                await update.message.reply_text(
                    "✅ <b>МАТЧ ИЛОВА ШУД!</b>\n\n"
                    f"🏠 {escape(state['home_team'])}\n"
                    f"✈️ {escape(state['away_team'])}\n\n"
                    f"📅 {state['match_date']}\n"
                    f"⏰ {state['match_time']}\n"
                    f"🏆 {escape(state['competition'])}\n\n"
                    "🌐 Матч дар Supabase нигоҳ дошта шуд.",
                    parse_mode="HTML",
                    reply_markup=admin_keyboard()
                )

            else:

                await update.message.reply_text(
                    "⚠️ Матч илова шуд, аммо маълумот баргардонида нашуд.",
                    reply_markup=admin_keyboard()
                )

        except Exception as e:

            logger.exception("ADD MATCH ERROR")

            add_match_state.pop(user.id, None)

            await update.message.reply_text(
                "❌ Ҳангоми илова кардани матч хатогӣ шуд.\n\n"
                f"<code>{escape(str(e))}</code>",
                parse_mode="HTML",
                reply_markup=admin_keyboard()
            )

        return True

    return True


# =========================================================
# SHOW MATCHES
# =========================================================

async def show_matches(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:

        result = (
            supabase
            .table("matches")
            .select("*")
            .order("match_date", desc=False)
            .order("match_time", desc=False)
            .execute()
        )

        matches = result.data or []

        if not matches:

            await update.message.reply_text(
                "📋 <b>Матчҳо вуҷуд надоранд.</b>",
                parse_mode="HTML"
            )

            return

        text = "📋 <b>МАТЧҲО</b>\n\n"

        for match in matches:

            match_id = match.get("id")

            home = escape(match.get("home_team"))
            away = escape(match.get("away_team"))
            date = escape(match.get("match_date"))
            time = escape(match.get("match_time"))
            competition = escape(match.get("competition"))
            status = escape(match.get("status"))

            text += (
                f"🆔 <code>{match_id}</code>\n"
                f"🏠 {home}\n"
                f"✈️ {away}\n"
                f"📅 {date} | ⏰ {time}\n"
                f"🏆 {competition}\n"
                f"📌 {status}\n"
                "━━━━━━━━━━━━━━\n"
            )

        await update.message.reply_text(
            text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.exception("SHOW MATCHES ERROR")

        await update.message.reply_text(
            "❌ Хатогӣ ҳангоми гирифтани матчҳо."
        )


# =========================================================
# GET PREDICTION DETAILS
# =========================================================

async def get_prediction_details(prediction):

    prediction_id = prediction.get("id")
    user_id = prediction.get("user_id")
    match_id = prediction.get("match_id")

    user_data = None
    match_data = None

    try:

        user_result = (
            supabase
            .table("users")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if user_result.data:
            user_data = user_result.data[0]

    except Exception:
        pass

    try:

        match_result = (
            supabase
            .table("matches")
            .select("*")
            .eq("id", match_id)
            .limit(1)
            .execute()
        )

        if match_result.data:
            match_data = match_result.data[0]

    except Exception:
        pass

    return user_data, match_data


# =========================================================
# SHOW NEW PREDICTIONS
# =========================================================

async def show_predictions(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:

        result = (
            supabase
            .table("predictions")
            .select("*")
            .is_("points", "null")
            .order("created_at", desc=False)
            .execute()
        )

        predictions = result.data or []

        if not predictions:

            await update.message.reply_text(
                "🎯 Пешгӯӣ ҳоло вуҷуд надоранд."
            )

            return

        await update.message.reply_text(
            f"🎯 Пешгӯиҳои нав: <b>{len(predictions)}</b>",
            parse_mode="HTML"
        )

        for prediction in predictions:

            user_data, match_data = await get_prediction_details(
                prediction
            )

            prediction_id = prediction.get("id")

            if user_data:

                first_name = escape(
                    user_data.get("first_name") or "Истифодабаранда"
                )

                username = user_data.get("username")

                if username:
                    username_text = f"@{escape(username)}"
                else:
                    username_text = "username нест"

            else:

                first_name = "Номаълум"
                username_text = "номаълум"

            if match_data:

                home = escape(match_data.get("home_team"))
                away = escape(match_data.get("away_team"))

                match_text = (
                    f"🏠 {home} — ✈️ {away}"
                )

            else:

                match_text = "Матч ёфт нашуд"

            predicted_home = prediction.get("predicted_home")
            predicted_away = prediction.get("predicted_away")
            predicted_scorer = prediction.get("predicted_scorer")

            scorer_text = (
                escape(predicted_scorer)
                if predicted_scorer
                else "—"
            )

            text = (
                "🎯 <b>ПЕШГӮӢ</b>\n\n"
                f"👤 {first_name}\n"
                f"📱 {username_text}\n\n"
                f"⚽️ {match_text}\n\n"
                f"🔮 Пешгӯӣ: "
                f"<b>{predicted_home} : {predicted_away}</b>\n"
                f"🥅 Голзан: {scorer_text}\n\n"
                f"🆔 Prediction ID: <code>{prediction_id}</code>"
            )

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Дуруст +1",
                        callback_data=f"correct:{prediction_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Нодуруст 0",
                        callback_data=f"wrong:{prediction_id}"
                    ),
                ]
            ])

            await update.message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:

        logger.exception("SHOW PREDICTIONS ERROR")

        await update.message.reply_text(
            "❌ Хатогӣ ҳангоми гирифтани пешгӯиҳо."
        )


# =========================================================
# USERS
# =========================================================

async def show_users(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:

        result = (
            supabase
            .table("users")
            .select("*")
            .order("points", desc=True)
            .execute()
        )

        users = result.data or []

        if not users:

            await update.message.reply_text(
                "👥 Истифодабарандагон вуҷуд надоранд."
            )

            return

        text = "👥 <b>ИСТИФОДАБАРАНДАГОН</b>\n\n"

        for index, item in enumerate(users, start=1):

            first_name = escape(
                item.get("first_name") or "Номаълум"
            )

            username = item.get("username")

            if username:
                username_text = f"@{escape(username)}"
            else:
                username_text = "—"

            points = item.get("points") or 0

            text += (
                f"{index}. {first_name} "
                f"({username_text}) — "
                f"<b>{points}</b> хол\n"
            )

        await update.message.reply_text(
            text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.exception("SHOW USERS ERROR")

        await update.message.reply_text(
            "❌ Хатогӣ ҳангоми гирифтани истифодабарандагон."
        )


# =========================================================
# RATING
# =========================================================

async def show_rating(update: Update):

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:

        result = (
            supabase
            .table("users")
            .select("*")
            .order("points", desc=True)
            .limit(20)
            .execute()
        )

        users = result.data or []

        if not users:

            await update.message.reply_text(
                "🏆 Рейтинг ҳоло холӣ аст."
            )

            return

        text = "🏆 <b>РЕЙТИНГ</b>\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for index, item in enumerate(users, start=1):

            first_name = escape(
                item.get("first_name") or "Номаълум"
            )

            points = item.get("points") or 0

            if index <= 3:
                prefix = medals[index - 1]
            else:
                prefix = f"{index}."

            text += (
                f"{prefix} {first_name} — "
                f"<b>{points}</b> хол\n"
            )

        await update.message.reply_text(
            text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.exception("SHOW RATING ERROR")

        await update.message.reply_text(
            "❌ Хатогӣ ҳангоми гирифтани рейтинг."
        )


# =========================================================
# AWARD POINTS
# =========================================================

async def award_points(
    query,
    prediction_id: int,
    correct: bool
):

    try:

        # Get prediction
        prediction_result = (
            supabase
            .table("predictions")
            .select("*")
            .eq("id", prediction_id)
            .limit(1)
            .execute()
        )

        if not prediction_result.data:

            await query.answer(
                "❌ Пешгӯӣ ёфт нашуд.",
                show_alert=True
            )

            return

        prediction = prediction_result.data[0]

        # Already processed
        if prediction.get("points") is not None:

            await query.answer(
                "⚠️ Ин пешгӯӣ аллакай коркард шудааст.",
                show_alert=True
            )

            return

        user_id = prediction.get("user_id")

        points = 1 if correct else 0

        # Update prediction
        (
            supabase
            .table("predictions")
            .update({
                "points": points
            })
            .eq("id", prediction_id)
            .execute()
        )

        # Add points only when correct
        if correct:

            user_result = (
                supabase
                .table("users")
                .select("points")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )

            if user_result.data:

                current_points = (
                    user_result.data[0].get("points") or 0
                )

                new_points = current_points + 1

                (
                    supabase
                    .table("users")
                    .update({
                        "points": new_points
                    })
                    .eq("id", user_id)
                    .execute()
                )

        # Notify player
        try:

            telegram_result = (
                supabase
                .table("users")
                .select("telegram_id, first_name")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )

            if telegram_result.data:

                telegram_id = telegram_result.data[0].get(
                    "telegram_id"
                )

                if telegram_id:

                    if correct:

                        message = (
                            "🎉 <b>Пешгӯии шумо дуруст баромад!</b>\n\n"
                            "✅ Шумо <b>+1 хол</b> гирифтед."
                        )

                    else:

                        message = (
                            "📊 <b>Натиҷаи пешгӯӣ</b>\n\n"
                            "❌ Ин пешгӯӣ дуруст набуд.\n"
                            "Хол: <b>0</b>"
                        )

                    await application.bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode="HTML"
                    )

        except Exception:

            logger.exception(
                "PLAYER NOTIFICATION ERROR"
            )

        # Update admin message
        try:

            old_text = query.message.text or ""

            result_text = (
                "\n\n"
                "━━━━━━━━━━━━━━\n"
                f"{'✅ ДУРУСТ +1' if correct else '❌ НОДУРУСТ 0'}"
            )

            await query.edit_message_text(
                old_text + result_text,
                parse_mode="HTML"
            )

        except Exception:

            pass

        await query.answer(
            "✅ Хол сабт шуд."
        )

    except Exception as e:

        logger.exception("AWARD POINTS ERROR")

        await query.answer(
            "❌ Хатогӣ.",
            show_alert=True
        )


# =========================================================
# CALLBACKS
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    user = query.from_user

    if not is_admin(user.id):

        await query.answer(
            "⛔ Доступ запрещён.",
            show_alert=True
        )

        return

    data = query.data or ""

    if data.startswith("correct:"):

        try:

            prediction_id = int(
                data.split(":")[1]
            )

            await award_points(
                query,
                prediction_id,
                True
            )

        except Exception:

            await query.answer(
                "❌ Хатогӣ.",
                show_alert=True
            )

        return

    if data.startswith("wrong:"):

        try:

            prediction_id = int(
                data.split(":")[1]
            )

            await award_points(
                query,
                prediction_id,
                False
            )

        except Exception:

            await query.answer(
                "❌ Хатогӣ.",
                show_alert=True
            )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    text = (update.message.text or "").strip()

    # ---------------------------------------------
    # ADD MATCH STATE
    # ---------------------------------------------

    if user.id in add_match_state:

        await process_add_match(update)

        return

    # ---------------------------------------------
    # ADMIN ONLY
    # ---------------------------------------------

    if not is_admin(user.id):

        return

    if text == "➕ Добавить матч":

        await start_add_match(update)
        return

    if text == "📋 Матчи":

        await show_matches(update)
        return

    if text == "🎯 Пешгӯиҳои нав":

        await show_predictions(update)
        return

    if text == "👥 Истифодабарандагон":

        await show_users(update)
        return

    if text == "🏆 Рейтинг":

        await show_rating(update)
        return

    if text == "🔄 Навсозӣ":

        await update.message.reply_text(
            "🔄 Маълумот нав карда шуд.",
            reply_markup=admin_keyboard()
        )

        await show_matches(update)

        return


# =========================================================
# WEBHOOK
# =========================================================

async def telegram_webhook(request: Request):

    try:

        data = await request.json()

        update = Update.de_json(
            data,
            application.bot
        )

        await application.process_update(update)

        return PlainTextResponse("OK")

    except Exception as e:

        logger.exception("WEBHOOK ERROR")

        return PlainTextResponse(
            "ERROR",
            status_code=500
        )


# =========================================================
# HEALTH WEB
# =========================================================

async def web_health(request: Request):

    return PlainTextResponse(
        "MaydoniSabz bot is running"
    )


# =========================================================
# STARLETTE APP
# =========================================================

web_app = Starlette(
    routes=[
        Route("/", web_health, methods=["GET"]),
        Route("/health", web_health, methods=["GET"]),
        Route("/telegram", telegram_webhook, methods=["POST"]),
    ]
)


# =========================================================
# MAIN
# =========================================================

async def setup_bot():

    await application.initialize()

    await application.bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=Update.ALL_TYPES
    )

    await application.start()

    logger.info(
        "Bot started. Webhook: %s",
        WEBHOOK_URL
    )


async def shutdown_bot():

    await application.stop()
    await application.shutdown()


if __name__ == "__main__":

    import asyncio

    async def runner():

        await setup_bot()

        config = uvicorn.Config(
            web_app,
            host="0.0.0.0",
            port=PORT,
            log_level="info"
        )

        server = uvicorn.Server(config)

        try:

            await server.serve()

        finally:

            await shutdown_bot()

    asyncio.run(runner())
