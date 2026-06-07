import logging
from datetime import datetime, date
from telegram import Update
from telegram.ext import ContextTypes

import database as db
import parser as p
from calendar_image import generate_calendar_image, generate_today_image
from keyboards import main_menu, tasks_list_keyboard, confirm_delete_keyboard
from config import STATE_IDLE, STATE_ADD_SINGLE, STATE_ADD_LIST, STATE_DELETE

logger = logging.getLogger(__name__)

WELCOME = (
    "👋 *Привет! Я ваш личный календарь-напоминалка.*\n\n"
    "Я умею:\n"
    "• Принимать задачи с датой и временем\n"
    "• Напоминать утром о задачах на день\n"
    "• Напоминать за 1 час до каждой задачи\n"
    "• Показывать красивый календарь месяца\n\n"
    "Выберите действие 👇"
)

HELP_ADD = (
    "✍️ *Как добавить задачу:*\n\n"
    "Напишите дату и задачу в любом формате:\n\n"
    "• `15 июня 10:00 Встреча с клиентом`\n"
    "• `20.06 14:30 Звонок партнёру`\n"
    "• `сегодня 18:00 Тренировка`\n"
    "• `завтра 09:00 Планёрка`\n"
    "• `15/07/2025 Конференция`\n\n"
    "Время необязательно — если не укажете, напомню только утром."
)

HELP_LIST = (
    "📋 *Как добавить список задач:*\n\n"
    "Отправьте несколько задач, каждую на новой строке:\n\n"
    "`15 июня 10:00 Встреча`\n"
    "`16 июня 14:00 Презентация`\n"
    "`20 июня Дедлайн проекта`\n"
    "`завтра 09:00 Планёрка`"
)


def get_state(context):
    return context.user_data.get("state", STATE_IDLE)


def set_state(context, state):
    context.user_data["state"] = state


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    set_state(context, STATE_IDLE)
    await update.message.reply_text(WELCOME, parse_mode="Markdown", reply_markup=main_menu())


# ─── Text handler ─────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = get_state(context)

    # ── Menu buttons ──
    if text == "➕ Добавить задачу":
        set_state(context, STATE_ADD_SINGLE)
        await update.message.reply_text(HELP_ADD, parse_mode="Markdown")
        return

    if text == "📋 Добавить список":
        set_state(context, STATE_ADD_LIST)
        await update.message.reply_text(HELP_LIST, parse_mode="Markdown")
        return

    if text == "📅 Сегодня":
        await show_today(update, context)
        return

    if text == "🗓 Календарь месяца":
        await show_month_calendar(update, context)
        return

    if text == "📆 Ближайшие задачи":
        await show_upcoming(update, context)
        return

    if text == "🗑 Удалить задачу":
        await start_delete(update, context)
        return

    # ── State: adding single task ──
    if state == STATE_ADD_SINGLE:
        tasks = p.parse_tasks(text)
        if not tasks:
            await update.message.reply_text(
                "❌ Не смог распознать дату. Попробуйте так:\n\n"
                "`15 июня 10:00 Встреча с клиентом`\n"
                "`завтра 14:00 Звонок`\n"
                "`20.06 09:00 Встреча`",
                parse_mode="Markdown",
            )
            return

        task = tasks[0]
        user_id = update.effective_user.id
        task_id = db.add_task(user_id, task["title"], task["date"], task["time"])

        # Schedule reminder if bot has scheduler
        if "scheduler" in context.bot_data:
            _schedule_task_reminder(context.bot_data["scheduler"], task, task_id, user_id, context.bot)

        date_ru = p.format_date_ru(task["date"])
        time_str = f" в {task['time']}" if task["time"] else ""
        await update.message.reply_text(
            f"✅ *Задача добавлена!*\n\n"
            f"📅 {date_ru}{time_str}\n"
            f"📌 {task['title']}\n\n"
            f"{'🔔 Напомню за 1 час до начала.' if task['time'] else '🔔 Напомню утром в 9:00.'}",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        set_state(context, STATE_IDLE)
        return

    # ── State: adding list ──
    if state == STATE_ADD_LIST:
        tasks = p.parse_tasks(text)
        if not tasks:
            await update.message.reply_text(
                "❌ Не нашёл задач с датами. Каждая строка должна начинаться с даты:\n\n"
                "`15 июня 10:00 Встреча`\n"
                "`16 июня 14:00 Звонок`",
                parse_mode="Markdown",
            )
            return

        user_id = update.effective_user.id
        added = []
        for task in tasks:
            task_id = db.add_task(user_id, task["title"], task["date"], task["time"])
            if "scheduler" in context.bot_data:
                _schedule_task_reminder(context.bot_data["scheduler"], task, task_id, user_id, context.bot)
            date_ru = p.format_date_ru(task["date"])
            time_str = f" {task['time']}" if task["time"] else ""
            added.append(f"• {date_ru}{time_str} — {task['title']}")

        msg = f"✅ *Добавлено задач: {len(added)}*\n\n" + "\n".join(added)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
        set_state(context, STATE_IDLE)
        return

    # Fallback
    set_state(context, STATE_IDLE)
    await update.message.reply_text("Выберите действие из меню 👇", reply_markup=main_menu())


# ─── Callback handler ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "del_cancel":
        await query.edit_message_text("Отмена.")
        set_state(context, STATE_IDLE)
        return

    if data.startswith("del_"):
        task_id = int(data.split("_")[1])
        task = db.get_task_by_id(task_id, user_id)
        if not task:
            await query.edit_message_text("❌ Задача не найдена.")
            return
        date_ru = p.format_date_ru(task["task_date"])
        time_str = f" в {task['task_time']}" if task["task_time"] else ""
        await query.edit_message_text(
            f"🗑 Удалить задачу?\n\n📅 {date_ru}{time_str}\n📌 {task['title']}",
            reply_markup=confirm_delete_keyboard(task_id),
        )
        return

    if data.startswith("confirm_del_"):
        task_id = int(data.split("_")[2])
        db.delete_task(task_id, user_id)
        await query.edit_message_text("✅ Задача удалена.")
        return


# ─── Today ────────────────────────────────────────────────────────────────────

async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = date.today()
    tasks = db.get_tasks_for_date(user_id, today.strftime("%Y-%m-%d"))
    tasks = [dict(t) for t in tasks]

    if not tasks:
        text = f"📅 *Сегодня, {p.format_date_ru(today.strftime('%Y-%m-%d'))}*\n\n✅ Задач нет — свободный день!"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())
    else:
        # Send calendar image for today
        img_bytes = generate_today_image(tasks, today)
        lines = [f"📅 *Сегодня — {p.format_date_ru(today.strftime('%Y-%m-%d'))}*\n"]
        for t in tasks:
            time_str = f"🕐 {t['task_time']} " if t["task_time"] else "• "
            lines.append(f"{time_str}{t['title']}")
        await update.message.reply_photo(
            photo=img_bytes,
            caption="\n".join(lines),
            parse_mode="Markdown",
        )


# ─── Month calendar ───────────────────────────────────────────────────────────

async def show_month_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    tasks = db.get_month_tasks(user_id, now.year, now.month)
    tasks = [dict(t) for t in tasks]

    task_count = len(tasks)
    img_bytes = generate_calendar_image(tasks, now.year, now.month)

    MONTH_NAMES = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    caption = (
        f"🗓 *{MONTH_NAMES[now.month]} {now.year}*\n"
        f"Задач в месяце: {task_count}"
    )
    await update.message.reply_photo(
        photo=img_bytes,
        caption=caption,
        parse_mode="Markdown",
    )


# ─── Upcoming tasks ───────────────────────────────────────────────────────────

async def show_upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = date.today().strftime("%Y-%m-%d")
    tasks = db.get_upcoming_tasks(user_id, today, days=30)

    if not tasks:
        await update.message.reply_text(
            "📆 *Ближайших задач нет.*\n\nДобавьте задачу через ➕",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return

    lines = ["📆 *Ближайшие задачи:*\n"]
    prev_date = None
    for task in tasks:
        if task["task_date"] != prev_date:
            day_str = p.format_weekday_ru(task["task_date"])
            lines.append(f"\n📅 *{p.format_date_ru(task['task_date'])} ({day_str})*")
            prev_date = task["task_date"]
        time_str = f"🕐 {task['task_time']}  " if task["task_time"] else "• "
        lines.append(f"  {time_str}{task['title']}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

async def start_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = date.today().strftime("%Y-%m-%d")
    tasks = db.get_upcoming_tasks(user_id, today)

    if not tasks:
        await update.message.reply_text(
            "📭 Нет задач для удаления.",
            reply_markup=main_menu(),
        )
        return

    await update.message.reply_text(
        "🗑 *Выберите задачу для удаления:*",
        parse_mode="Markdown",
        reply_markup=tasks_list_keyboard([dict(t) for t in tasks[:20]]),
    )
    set_state(context, STATE_DELETE)


# ─── Scheduler helper ─────────────────────────────────────────────────────────

def _schedule_task_reminder(scheduler, task: dict, task_id: int, user_id: int, bot):
    """Schedule a 1-hour-before reminder for a task with time."""
    from datetime import datetime, timedelta
    import pytz
    from config import TIMEZONE

    if not task.get("time"):
        return

    tz = pytz.timezone(TIMEZONE)
    task_dt_str = f"{task['date']} {task['time']}"
    try:
        task_dt = tz.localize(datetime.strptime(task_dt_str, "%Y-%m-%d %H:%M"))
    except Exception:
        return

    remind_at = task_dt - timedelta(hours=1)
    now = datetime.now(tz)

    if remind_at <= now:
        return

    job_id = f"task_{task_id}_user_{user_id}"

    async def send_reminder(bot=bot, user_id=user_id, title=task["title"], time_str=task["time"], date_str=task["date"]):
        date_ru = p.format_date_ru(date_str)
        await bot.send_message(
            chat_id=user_id,
            text=f"⏰ *Напоминание!*\n\nЧерез 1 час:\n📌 {title}\n🕐 {time_str} | {date_ru}",
            parse_mode="Markdown",
        )

    try:
        scheduler.add_job(
            send_reminder,
            trigger="date",
            run_date=remind_at,
            id=job_id,
            replace_existing=True,
        )
    except Exception as e:
        logger.error(f"Scheduling error: {e}")
