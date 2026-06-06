from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import STYLE_OPTIONS, SAVE_CATEGORIES


def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📷 Создать промпт по фото")],
        [KeyboardButton("✍️ Создать промпт по описанию")],
        [KeyboardButton("💾 Сохранённые"), KeyboardButton("❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def style_keyboard():
    buttons = []
    for i in range(0, len(STYLE_OPTIONS), 2):
        row = [InlineKeyboardButton(STYLE_OPTIONS[i], callback_data=f"style_{i}")]
        if i + 1 < len(STYLE_OPTIONS):
            row.append(InlineKeyboardButton(STYLE_OPTIONS[i + 1], callback_data=f"style_{i+1}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой стиль (напишу сам)", callback_data="style_custom")])
    return InlineKeyboardMarkup(buttons)


def prompt_ready_keyboard():
    buttons = [
        [InlineKeyboardButton("✅ Всё верно", callback_data="action_approve"),
         InlineKeyboardButton("✏️ Изменить", callback_data="action_edit")],
        [InlineKeyboardButton("📋 Скопировать промпт", callback_data="action_copy")],
        [InlineKeyboardButton("💾 Сохранить промпт", callback_data="action_save_prompt")],
        [InlineKeyboardButton("🆕 Начать заново", callback_data="action_restart")],
    ]
    return InlineKeyboardMarkup(buttons)


def generate_choice_keyboard():
    buttons = [
        [InlineKeyboardButton("🤖 Сгенерировать через DALL-E", callback_data="gen_dalle")],
        [InlineKeyboardButton("✨ Сгенерировать через Gemini", callback_data="gen_gemini")],
        [InlineKeyboardButton("📋 Только скопировать промпт", callback_data="gen_copy")],
        [InlineKeyboardButton("🆕 Начать заново", callback_data="action_restart")],
    ]
    return InlineKeyboardMarkup(buttons)


def after_image_keyboard():
    buttons = [
        [InlineKeyboardButton("💾 Сохранить изображение", callback_data="action_save_image")],
        [InlineKeyboardButton("✏️ Исправить и перегенерировать", callback_data="action_edit")],
        [InlineKeyboardButton("🆕 Начать заново", callback_data="action_restart")],
    ]
    return InlineKeyboardMarkup(buttons)


def save_category_keyboard():
    buttons = []
    for i, cat in enumerate(SAVE_CATEGORIES):
        buttons.append([InlineKeyboardButton(cat, callback_data=f"savecat_{i}")])
    return InlineKeyboardMarkup(buttons)


def saved_items_keyboard(items):
    buttons = []
    for item in items[:10]:
        label = f"[{item['category']}] {item['title'][:30]} — {item['created_at'][:10]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view_saved_{item['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Главное меню", callback_data="action_restart")])
    return InlineKeyboardMarkup(buttons)


def saved_item_actions_keyboard(item_id: int, has_image: bool):
    buttons = [
        [InlineKeyboardButton("📋 Показать промпт", callback_data=f"saved_prompt_{item_id}")],
    ]
    if has_image:
        buttons.append([InlineKeyboardButton("🖼 Показать изображение", callback_data=f"saved_img_{item_id}")])
    buttons.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"saved_del_{item_id}")])
    buttons.append([InlineKeyboardButton("🔙 К списку", callback_data="go_saved_list")])
    return InlineKeyboardMarkup(buttons)
