import logging
import pytz
from datetime import datetime, date, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import parser as p
from handlers import cmd_start, handle_text, handle_callback
from calendar_image import generate_today_image
from config import TELEGRAM_BOT_TOKEN, TIMEZONE, MORNING_HOUR, MORNING_MINUTE

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def send_morning_reminder(bot, user_id: int):
    """Send morning summary of today's tasks to a user."""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    tasks = db.get_tasks_for_date(user_id, today_str)
    tasks = [dict(t) for t in tasks]

    if not tasks:
        await bot.send_message(
            chat_id=user_id,
            text=f"☀️ *Доброе утро!*\n\nСегодня задач нет. Хорошего дня! 🌟",
            parse_mode="Markdown",
        )
        return

    img_bytes = generate_today_image(tasks, today)
    lines = [f"☀️ *Доброе утро! Задачи на сегодня:*\n"]
    for t in tasks:
        time_str = f"🕐 {t['task_time']}  " if t["task_time"] else "• "
        lines.append(f"{time_str}{t['title']}")

    await bot.send_photo(
        chat_id=user_id,
        photo=img_bytes,
        caption="\n".join(lines),
        parse_mode="Markdown",
    )


async def morning_job(bot):
    """Run morning reminders for all users."""
    users = db.get_all_users()
    for user_id in users:
        try:
            await send_morning_reminder(bot, user_id)
        except Exception as e:
            logger.error(f"Morning reminder error for {user_id}: {e}")


async def schedule_existing_reminders(scheduler, bot):
    """On startup, reschedule any future task reminders."""
    from handlers import _schedule_task_reminder
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")
    tasks = db.get_all_future_tasks_with_time(now_str)
    count = 0
    for task in tasks:
        task_dict = {
            "title": task["title"],
            "date": task["task_date"],
            "time": task["task_time"],
        }
        _schedule_task_reminder(scheduler, task_dict, task["id"], task["user_id"], bot)
        count += 1
    if count:
        logger.info(f"Rescheduled {count} task reminders.")


def main():
    db.init_db()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ── Scheduler ──
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Morning reminder every day
    scheduler.add_job(
        morning_job,
        trigger="cron",
        hour=MORNING_HOUR,
        minute=MORNING_MINUTE,
        id="morning_reminder",
        kwargs={"bot": app.bot},
    )

    # Store scheduler in bot_data so handlers can access it
    app.bot_data["scheduler"] = scheduler

    # ── Handlers ──
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # ── Post-init: start scheduler and reschedule reminders ──
    async def post_init(application):
        scheduler.start()
        await schedule_existing_reminders(scheduler, application.bot)
        logger.info(f"Scheduler started. Morning reminder at {MORNING_HOUR:02d}:{MORNING_MINUTE:02d} {TIMEZONE}")

    app.post_init = post_init

    logger.info("Бот-календарь запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
