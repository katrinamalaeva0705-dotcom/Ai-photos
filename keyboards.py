from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    keyboard = [
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("📋 Добавить список")],
        [KeyboardButton("📅 Сегодня"), KeyboardButton("🗓 Календарь месяца")],
        [KeyboardButton("📆 Ближайшие задачи"), KeyboardButton("🗑 Удалить задачу")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def tasks_list_keyboard(tasks):
    """Inline keyboard with tasks for deletion."""
    buttons = []
    for task in tasks:
        time_str = f" {task['task_time']}" if task["task_time"] else ""
        label = f"🗑 {task['task_date']}{time_str} — {task['title'][:30]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_{task['id']}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(task_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_del_{task_id}"),
         InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")],
    ])
