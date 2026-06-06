import os
import logging
from datetime import datetime
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

import database as db
import openai_client as ai
from keyboards import (
    main_menu_keyboard, result_type_keyboard, output_type_keyboard,
    style_keyboard, lighting_keyboard, tool_keyboard, prompt_ready_keyboard,
    after_image_keyboard, save_category_keyboard, saved_items_keyboard,
    saved_item_actions_keyboard,
)
from config import (
    STATE_MAIN_MENU, STATE_AWAIT_INPUT, STATE_QUESTIONS_RESULT_TYPE,
    STATE_QUESTIONS_OUTPUT_TYPE, STATE_QUESTIONS_PRESERVE, STATE_QUESTIONS_STYLE,
    STATE_QUESTIONS_TOOL, STATE_QUESTIONS_LIGHTING, STATE_PROMPT_READY,
    STATE_AWAIT_CORRECTION, STATE_SAVED_MENU, STATE_SAVE_CATEGORY,
    DOWNLOADS_DIR, SAVED_IMAGES_DIR, STYLE_OPTIONS, LIGHTING_OPTIONS, TOOL_OPTIONS,
    SAVE_CATEGORIES,
)

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 *Привет! Я ваш AI-ассистент для создания профессиональных промптов и изображений.*\n\n"
    "Я помогу вам:\n"
    "• Создать детальный промпт для AI-генерации\n"
    "• Сгенерировать финальное изображение\n"
    "• Работать с текстом, голосом и фотографиями\n\n"
    "Выберите действие в меню ниже 👇"
)

HELP_TEXT = (
    "❓ *Как пользоваться ботом:*\n\n"
    "1️⃣ *Создать новый промпт* — начните с описания того, что хотите создать.\n"
    "2️⃣ *Загрузить фото* — отправьте референс-фото, бот его проанализирует.\n"
    "3️⃣ *Голосовое описание* — запишите голосовое, бот его расшифрует.\n"
    "4️⃣ *Сгенерировать изображение* — получите готовое AI-изображение по промпту.\n"
    "5️⃣ *Сохранённые* — ваши сохранённые промпты и изображения.\n\n"
    "💡 *Промпты генерируются на английском* — так AI-инструменты работают лучше.\n"
    "💡 *Бот сохраняет важные детали* (лица, логотипы, текст, архитектура) и не меняет их без вашего разрешения."
)


def get_user_data(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {}
    return context.user_data["session"]


def reset_session(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["session"] = {}


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    reset_session(context)
    context.user_data["state"] = STATE_MAIN_MENU
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ─── Main menu text handler ───────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get("state", STATE_MAIN_MENU)

    # Main menu buttons
    if text == "✨ Создать новый промпт":
        reset_session(context)
        context.user_data["state"] = STATE_AWAIT_INPUT
        await update.message.reply_text(
            "📝 *Опишите, что вы хотите создать.*\n\n"
            "Можно написать текстом, отправить голосовое сообщение или загрузить фото-референс.\n\n"
            "Например: _«Рекламное фото нашего крема на фоне летней веранды, стиль люкс»_",
            parse_mode="Markdown",
        )
        return

    if text == "🖼 Загрузить фото":
        reset_session(context)
        context.user_data["state"] = STATE_AWAIT_INPUT
        await update.message.reply_text(
            "📤 *Отправьте фото-референс.*\n\n"
            "После загрузки я проанализирую его и задам уточняющие вопросы.",
            parse_mode="Markdown",
        )
        return

    if text == "🎤 Голосовое описание":
        reset_session(context)
        context.user_data["state"] = STATE_AWAIT_INPUT
        await update.message.reply_text(
            "🎤 *Запишите голосовое сообщение* с описанием того, что вы хотите создать.\n\n"
            "Я расшифрую его и начну работу.",
            parse_mode="Markdown",
        )
        return

    if text == "🤖 Сгенерировать изображение":
        session = get_user_data(context)
        if not session.get("prompt"):
            await update.message.reply_text(
                "⚠️ Сначала создайте промпт через *«Создать новый промпт»*.",
                parse_mode="Markdown",
            )
            return
        await _generate_and_send_image(update, context)
        return

    if text == "💾 Сохранённые промпты и фото":
        await show_saved_list(update, context)
        return

    if text == "❓ Помощь":
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
        return

    # State-based handlers
    if state == STATE_AWAIT_INPUT:
        session = get_user_data(context)
        session["description"] = text
        context.user_data["state"] = STATE_QUESTIONS_RESULT_TYPE
        await update.message.reply_text(
            "📌 *Что вы хотите создать?*",
            parse_mode="Markdown",
            reply_markup=result_type_keyboard(),
        )
        return

    if state == STATE_QUESTIONS_PRESERVE:
        session = get_user_data(context)
        session["preserve"] = text
        context.user_data["state"] = STATE_QUESTIONS_STYLE
        await update.message.reply_text(
            "🎨 *Выберите стиль:*",
            parse_mode="Markdown",
            reply_markup=style_keyboard(),
        )
        return

    if state == STATE_AWAIT_CORRECTION:
        session = get_user_data(context)
        original_prompt = session.get("prompt", "")
        await update.message.reply_chat_action(ChatAction.TYPING)
        updated_prompt = await ai.refine_prompt(original_prompt, text)
        session["prompt"] = updated_prompt

        output_type = session.get("output_type", "both")
        await update.message.reply_text(
            f"✅ *Промпт обновлён:*\n\n```\n{updated_prompt}\n```",
            parse_mode="Markdown",
            reply_markup=prompt_ready_keyboard(has_image_option=(output_type != "prompt")),
        )

        if output_type == "image" or output_type == "both":
            await _generate_and_send_image(update, context)
        return

    # Fallback
    if state == STATE_MAIN_MENU:
        await update.message.reply_text(
            "Выберите действие из меню 👇",
            reply_markup=main_menu_keyboard(),
        )


# ─── Voice handler ────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Расшифровываю голосовое сообщение...")
    await update.message.reply_chat_action(ChatAction.TYPING)

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_voice.ogg")
    await file.download_to_drive(file_path)

    try:
        text = await ai.transcribe_voice(file_path)
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        await update.message.reply_text("❌ Не удалось расшифровать голосовое. Попробуйте ещё раз или напишите текстом.")
        return
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    await update.message.reply_text(f"📝 *Расшифровано:*\n_{text}_", parse_mode="Markdown")

    session = get_user_data(context)
    session["description"] = text
    context.user_data["state"] = STATE_QUESTIONS_RESULT_TYPE

    await update.message.reply_text(
        "📌 *Что вы хотите создать?*",
        parse_mode="Markdown",
        reply_markup=result_type_keyboard(),
    )


# ─── Photo handler ────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼 Анализирую фото...")
    await update.message.reply_chat_action(ChatAction.TYPING)

    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    file_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_ref.jpg")
    await file.download_to_drive(file_path)

    try:
        analysis = await ai.analyze_image(file_path)
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await update.message.reply_text("❌ Не удалось проанализировать фото. Попробуйте ещё раз.")
        return

    session = get_user_data(context)
    session["image_analysis"] = analysis
    session["ref_image_path"] = file_path

    caption = update.message.caption or ""
    if caption:
        session["description"] = caption

    await update.message.reply_text(
        f"✅ *Фото проанализировано:*\n\n_{analysis}_\n\n"
        "Теперь опишите, что вы хотите создать (или перейдите к следующему шагу):",
        parse_mode="Markdown",
    )

    if caption:
        context.user_data["state"] = STATE_QUESTIONS_RESULT_TYPE
        await update.message.reply_text(
            "📌 *Что вы хотите создать?*",
            parse_mode="Markdown",
            reply_markup=result_type_keyboard(),
        )
    else:
        context.user_data["state"] = STATE_AWAIT_INPUT


# ─── Document/file handler ────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        file = await context.bot.get_file(doc.file_id)
        file_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_ref_doc.jpg")
        await file.download_to_drive(file_path)

        # Reuse photo handler logic
        update.message.photo = [type('obj', (object,), {'file_id': doc.file_id})()]
        await handle_photo(update, context)
    else:
        await update.message.reply_text("⚠️ Пожалуйста, отправьте изображение (JPG, PNG, WEBP).")


# ─── Callback query handler ───────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    session = get_user_data(context)

    # ── Result type ──
    if data.startswith("result_"):
        session["result_type"] = "image" if data == "result_image" else "video"
        context.user_data["state"] = STATE_QUESTIONS_OUTPUT_TYPE
        await query.edit_message_text(
            "📤 *Что вы хотите получить?*",
            parse_mode="Markdown",
            reply_markup=output_type_keyboard(),
        )
        return

    # ── Output type ──
    if data.startswith("output_"):
        mapping = {"output_prompt": "prompt", "output_image": "image", "output_both": "both"}
        session["output_type"] = mapping.get(data, "both")
        context.user_data["state"] = STATE_QUESTIONS_PRESERVE
        await query.edit_message_text(
            "🔒 *Что должно остаться без изменений?*\n\n"
            "Напишите: лица, логотипы, текст, архитектура, упаковка, цвета...\n"
            "Или напишите *«ничего»* если изменения разрешены.",
            parse_mode="Markdown",
        )
        return

    # ── Style ──
    if data.startswith("style_"):
        if data == "style_custom":
            await query.edit_message_text(
                "✏️ Напишите свой стиль:",
                parse_mode="Markdown",
            )
            context.user_data["state"] = STATE_QUESTIONS_STYLE
            context.user_data["awaiting_custom_style"] = True
            return
        else:
            idx = int(data.split("_")[1])
            session["style"] = STYLE_OPTIONS[idx]
        context.user_data["state"] = STATE_QUESTIONS_LIGHTING
        await query.edit_message_text(
            "💡 *Выберите освещение:*",
            parse_mode="Markdown",
            reply_markup=lighting_keyboard(),
        )
        return

    # ── Lighting ──
    if data.startswith("lighting_"):
        if data == "lighting_skip":
            session["lighting"] = "natural"
        else:
            idx = int(data.split("_")[1])
            session["lighting"] = LIGHTING_OPTIONS[idx]
        context.user_data["state"] = STATE_QUESTIONS_TOOL
        await query.edit_message_text(
            "🛠 *Для какого инструмента создать промпт?*",
            parse_mode="Markdown",
            reply_markup=tool_keyboard(),
        )
        return

    # ── Tool ──
    if data.startswith("tool_"):
        idx = int(data.split("_")[1])
        session["tool"] = TOOL_OPTIONS[idx]
        await _generate_prompt_flow(query, context, session)
        return

    # ── Prompt actions ──
    if data == "action_copy":
        prompt = session.get("prompt", "")
        await query.message.reply_text(
            f"📋 *Промпт для копирования:*\n\n```\n{prompt}\n```",
            parse_mode="Markdown",
        )
        return

    if data == "action_generate_image":
        await _generate_and_send_image_callback(query, context)
        return

    if data == "action_edit":
        context.user_data["state"] = STATE_AWAIT_CORRECTION
        await query.message.reply_text(
            "✏️ *Напишите, что нужно изменить или улучшить в промпте/изображении:*",
            parse_mode="Markdown",
        )
        return

    if data == "action_another":
        await _generate_prompt_flow(query, context, session)
        return

    if data == "action_save_prompt":
        session["saving_what"] = "prompt"
        context.user_data["state"] = STATE_SAVE_CATEGORY
        await query.message.reply_text(
            "📂 *Выберите категорию для сохранения:*",
            parse_mode="Markdown",
            reply_markup=save_category_keyboard(),
        )
        return

    if data == "action_save_image":
        image_path = session.get("generated_image_path")
        if not image_path:
            await query.message.reply_text("⚠️ Изображение ещё не сгенерировано.")
            return
        session["saving_what"] = "image"
        context.user_data["state"] = STATE_SAVE_CATEGORY
        await query.message.reply_text(
            "📂 *Выберите категорию для сохранения:*",
            parse_mode="Markdown",
            reply_markup=save_category_keyboard(),
        )
        return

    if data == "action_restart":
        reset_session(context)
        context.user_data["state"] = STATE_MAIN_MENU
        await query.message.reply_text(
            "🆕 Начинаем заново. Выберите действие:",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "action_finish":
        reset_session(context)
        context.user_data["state"] = STATE_MAIN_MENU
        await query.message.reply_text(
            "✅ *Готово! Работа завершена.*\n\nЕсли захотите создать ещё — выберите действие в меню.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── Save category ──
    if data.startswith("savecat_"):
        idx = int(data.split("_")[1])
        category = SAVE_CATEGORIES[idx]
        prompt = session.get("prompt", "")
        image_path = session.get("generated_image_path") if session.get("saving_what") == "image" else None
        title = (session.get("description", "") or "Без названия")[:50]
        user_id = query.from_user.id

        # Copy image to saved dir
        saved_img = None
        if image_path and os.path.exists(image_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_img = os.path.join(SAVED_IMAGES_DIR, f"{user_id}_{ts}.jpg")
            import shutil
            shutil.copy2(image_path, saved_img)

        db.save_item(user_id, title, category, prompt, saved_img)
        await query.message.reply_text(
            f"✅ Сохранено в категорию *{category}*.",
            parse_mode="Markdown",
            reply_markup=prompt_ready_keyboard(has_image_option=bool(session.get("output_type") != "prompt")),
        )
        return

    # ── Saved list ──
    if data == "go_saved_list":
        await show_saved_list_callback(query, context)
        return

    if data.startswith("view_saved_"):
        item_id = int(data.split("_")[2])
        item = db.get_saved_item(item_id, query.from_user.id)
        if not item:
            await query.message.reply_text("❌ Элемент не найден.")
            return
        text = (
            f"📁 *{item['title']}*\n"
            f"🗂 Категория: {item['category']}\n"
            f"📅 {item['created_at']}\n"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=saved_item_actions_keyboard(item_id, bool(item["image_path"])),
        )
        return

    if data.startswith("saved_prompt_"):
        item_id = int(data.split("_")[2])
        item = db.get_saved_item(item_id, query.from_user.id)
        if item:
            await query.message.reply_text(
                f"📋 *Промпт:*\n\n```\n{item['prompt_text']}\n```",
                parse_mode="Markdown",
            )
        return

    if data.startswith("saved_img_"):
        item_id = int(data.split("_")[2])
        item = db.get_saved_item(item_id, query.from_user.id)
        if item and item["image_path"] and os.path.exists(item["image_path"]):
            with open(item["image_path"], "rb") as f:
                await query.message.reply_photo(photo=f, caption="🖼 Сохранённое изображение")
        else:
            await query.message.reply_text("❌ Изображение не найдено.")
        return

    if data.startswith("saved_del_"):
        item_id = int(data.split("_")[2])
        db.delete_saved_item(item_id, query.from_user.id)
        await query.edit_message_text("🗑 Удалено.")
        return


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _generate_prompt_flow(query, context, session):
    """Generate prompt and send it."""
    msg = await query.message.reply_text("⏳ *Генерирую профессиональный промпт...*", parse_mode="Markdown")
    try:
        prompt = await ai.generate_prompt(session)
    except Exception as e:
        logger.error(f"Prompt generation error: {e}")
        await msg.edit_text("❌ Ошибка при генерации промпта. Попробуйте ещё раз.")
        return

    session["prompt"] = prompt
    context.user_data["state"] = STATE_PROMPT_READY
    output_type = session.get("output_type", "both")

    await msg.edit_text(
        f"✅ *Готовый промпт:*\n\n```\n{prompt}\n```",
        parse_mode="Markdown",
        reply_markup=prompt_ready_keyboard(has_image_option=(output_type != "prompt")),
    )

    # Auto-generate image if requested
    if output_type in ("image", "both"):
        await _generate_and_send_image_callback(query, context)


async def _generate_and_send_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate image from message context."""
    session = get_user_data(context)
    prompt = session.get("prompt", "")
    if not prompt:
        await update.message.reply_text("⚠️ Нет промпта для генерации. Сначала создайте промпт.")
        return

    msg = await update.message.reply_text("🎨 *Генерирую изображение... Это может занять до 30 секунд.*", parse_mode="Markdown")
    await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

    try:
        image_bytes = await ai.generate_image(prompt)
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await msg.edit_text(f"❌ Ошибка генерации изображения: {str(e)[:200]}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_{ts}.jpg")
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    session["generated_image_path"] = image_path

    await msg.delete()
    await update.message.reply_photo(
        photo=image_bytes,
        caption="🖼 *Сгенерированное изображение*\n\nПромпт использован выше.",
        parse_mode="Markdown",
        reply_markup=after_image_keyboard(),
    )


async def _generate_and_send_image_callback(query, context):
    """Generate image from callback context."""
    session = get_user_data(context)
    prompt = session.get("prompt", "")
    if not prompt:
        await query.message.reply_text("⚠️ Нет промпта для генерации.")
        return

    msg = await query.message.reply_text("🎨 *Генерирую изображение... До 30 секунд.*", parse_mode="Markdown")

    try:
        image_bytes = await ai.generate_image(prompt)
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await msg.edit_text(f"❌ Ошибка: {str(e)[:200]}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(DOWNLOADS_DIR, f"{query.from_user.id}_{ts}.jpg")
    with open(image_path, "wb") as f:
        f.write(image_bytes)
    session["generated_image_path"] = image_path

    await msg.delete()
    await query.message.reply_photo(
        photo=image_bytes,
        caption="🖼 *Готовое изображение*",
        parse_mode="Markdown",
        reply_markup=after_image_keyboard(),
    )


async def show_saved_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = db.get_saved_items(update.effective_user.id)
    if not items:
        await update.message.reply_text(
            "💾 *Сохранённых элементов нет.*\n\nСоздайте промпт или изображение и сохраните его.",
            parse_mode="Markdown",
        )
        return
    await update.message.reply_text(
        f"💾 *Сохранённые промпты и изображения ({len(items)}):*",
        parse_mode="Markdown",
        reply_markup=saved_items_keyboard(items),
    )


async def show_saved_list_callback(query, context):
    items = db.get_saved_items(query.from_user.id)
    if not items:
        await query.edit_message_text("💾 Нет сохранённых элементов.")
        return
    await query.edit_message_text(
        f"💾 *Сохранённые ({len(items)}):*",
        parse_mode="Markdown",
        reply_markup=saved_items_keyboard(items),
    )
