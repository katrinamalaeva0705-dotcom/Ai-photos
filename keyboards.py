from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import STYLE_OPTIONS, LIGHTING_OPTIONS, TOOL_OPTIONS, SAVE_CATEGORIES


def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("✨ Создать новый промпт")],
        [KeyboardButton("🖼 Загрузить фото"), KeyboardButton("🎤 Голосовое описание")],
        [KeyboardButton("🤖 Сгенерировать изображение")],
        [KeyboardButton("💾 Сохранённые промпты и фото")],
        [KeyboardButton("❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def result_type_keyboard():
    buttons = [
        [InlineKeyboardButton("📸 Изображение", callback_data="result_image"),
         InlineKeyboardButton("🎬 Видео", callback_data="result_video")],
    ]
    return InlineKeyboardMarkup(buttons)


def output_type_keyboard():
    buttons = [
        [InlineKeyboardButton("📝 Только промпт", callback_data="output_prompt")],
        [InlineKeyboardButton("🖼 Только изображение", callback_data="output_image")],
        [InlineKeyboardButton("✨ Промпт + изображение", callback_data="output_both")],
    ]
    return InlineKeyboardMarkup(buttons)


def style_keyboard():
    buttons = []
    for i in range(0, len(STYLE_OPTIONS), 2):
        row = [InlineKeyboardButton(STYLE_OPTIONS[i], callback_data=f"style_{i}")]
        if i + 1 < len(STYLE_OPTIONS):
            row.append(InlineKeyboardButton(STYLE_OPTIONS[i + 1], callback_data=f"style_{i+1}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Свой стиль", callback_data="style_custom")])
    return InlineKeyboardMarkup(buttons)


def lighting_keyboard():
    buttons = []
    for i in range(0, len(LIGHTING_OPTIONS), 2):
        row = [InlineKeyboardButton(LIGHTING_OPTIONS[i], callback_data=f"lighting_{i}")]
        if i + 1 < len(LIGHTING_OPTIONS):
            row.append(InlineKeyboardButton(LIGHTING_OPTIONS[i + 1], callback_data=f"lighting_{i+1}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⏭ Пропустить", callback_data="lighting_skip")])
    return InlineKeyboardMarkup(buttons)


def tool_keyboard():
    buttons = []
    for i in range(0, len(TOOL_OPTIONS), 2):
        row = [InlineKeyboardButton(TOOL_OPTIONS[i], callback_data=f"tool_{i}")]
        if i + 1 < len(TOOL_OPTIONS):
            row.append(InlineKeyboardButton(TOOL_OPTIONS[i + 1], callback_data=f"tool_{i+1}"))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def prompt_ready_keyboard(has_image_option: bool = True):
    buttons = [
        [InlineKeyboardButton("📋 Скопировать промпт", callback_data="action_copy")],
    ]
    if has_image_option:
        buttons.append([InlineKeyboardButton("🎨 Сгенерировать изображение", callback_data="action_generate_image")])
    buttons += [
        [InlineKeyboardButton("✏️ Исправить промпт", callback_data="action_edit"),
         InlineKeyboardButton("🔄 Другой вариант", callback_data="action_another")],
        [InlineKeyboardButton("💾 Сохранить промпт", callback_data="action_save_prompt"),
         InlineKeyboardButton("🖼 Сохранить фото", callback_data="action_save_image")],
        [InlineKeyboardButton("🆕 Начать заново", callback_data="action_restart"),
         InlineKeyboardButton("✅ Завершить", callback_data="action_finish")],
    ]
    return InlineKeyboardMarkup(buttons)


def after_image_keyboard():
    buttons = [
        [InlineKeyboardButton("💾 Сохранить изображение", callback_data="action_save_image")],
        [InlineKeyboardButton("✏️ Исправить и перегенерировать", callback_data="action_edit")],
        [InlineKeyboardButton("🆕 Начать заново", callback_data="action_restart"),
         InlineKeyboardButton("✅ Завершить", callback_data="action_finish")],
    ]
    return InlineKeyboardMarkup(buttons)


def save_category_keyboard():
    buttons = []
    for i, cat in enumerate(SAVE_CATEGORIES):
        buttons.append([InlineKeyboardButton(cat, callback_data=f"savecat_{i}")])
    return InlineKeyboardMarkup(buttons)


def saved_items_keyboard(items):
    buttons = []
    for item in items[:10]:  # Show max 10
        label = f"[{item['category']}] {item['title'][:30]} — {item['created_at'][:10]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view_saved_{item['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="action_restart")])
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
