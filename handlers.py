import os
import logging
import shutil
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

import database as db
import openai_client as ai
from keyboards import (
    main_menu_keyboard, style_keyboard, prompt_ready_keyboard,
    generate_choice_keyboard, after_image_keyboard,
    save_category_keyboard, saved_items_keyboard, saved_item_actions_keyboard,
)
from config import (
    STATE_MAIN_MENU, STATE_AWAIT_PHOTO, STATE_AWAIT_DESCRIPTION,
    STATE_QUESTIONS_STYLE, STATE_QUESTIONS_STYLE_CUSTOM,
    STATE_PROMPT_READY, STATE_AWAIT_CORRECTION, STATE_SAVE_CATEGORY,
    DOWNLOADS_DIR, SAVED_IMAGES_DIR, STYLE_OPTIONS, SAVE_CATEGORIES,
)

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 *Привет! Я ваш AI-ассистент для создания промптов и изображений.*\n\n"
    "Выберите с чего начать:"
)

HELP_TEXT = (
    "❓ *Как пользоваться ботом:*\n\n"
    "📷 *По фото* — загрузите фото, бот его проанализирует и создаст готовый промпт.\n\n"
    "✍️ *По описанию* — опишите текстом или голосом что хотите создать.\n\n"
    "После создания промпта вы можете:\n"
    "• Скопировать его и вставить в любой AI-инструмент\n"
    "• Сгенерировать изображение прямо в боте через DALL-E или Gemini\n"
    "• Исправить промпт если что-то не так\n"
    "• Сохранить в личную библиотеку\n\n"
    "💡 *Промпты создаются на английском* — так AI работает точнее."
)


def get_session(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "session" not in context.user_data:
        context.user_data["session"] = {}
    return context.user_data["session"]


def reset_session(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["session"] = {}
    context.user_data["state"] = STATE_MAIN_MENU


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.init_db()
    reset_session(context)
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ─── Text handler ─────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get("state", STATE_MAIN_MENU)

    # ── Main menu buttons ──
    if text == "📷 Создать промпт по фото":
        reset_session(context)
        context.user_data["state"] = STATE_AWAIT_PHOTO
        await update.message.reply_text(
            "📷 *Загрузите фото-референс.*\n\n"
            "Я его проанализирую и создам готовый промпт с сохранением всех важных деталей.",
            parse_mode="Markdown",
        )
        return

    if text == "✍️ Создать промпт по описанию":
        reset_session(context)
        context.user_data["state"] = STATE_AWAIT_DESCRIPTION
        await update.message.reply_text(
            "✍️ *Опишите что хотите создать.*\n\n"
            "Напишите текстом или отправьте голосовое сообщение 🎤\n\n"
            "Например: _«Рекламное фото крема на фоне мраморного стола, стиль люкс»_",
            parse_mode="Markdown",
        )
        return

    if text == "💾 Сохранённые":
        await show_saved_list(update, context)
        return

    if text == "❓ Помощь":
        await update.message.reply_text(HELP_TEXT, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return

    # ── State-based ──
    if state == STATE_AWAIT_DESCRIPTION:
        session = get_session(context)
        session["description"] = text
        context.user_data["state"] = STATE_QUESTIONS_STYLE
        await update.message.reply_text(
            "🎨 *Выберите стиль:*",
            parse_mode="Markdown",
            reply_markup=style_keyboard(),
        )
        return

    if state == STATE_AWAIT_PHOTO:
        # User sent text instead of photo
        session = get_session(context)
        session["description"] = text
        context.user_data["state"] = STATE_QUESTIONS_STYLE
        await update.message.reply_text(
            "✅ Описание принято.\n\n🎨 *Выберите стиль:*",
            parse_mode="Markdown",
            reply_markup=style_keyboard(),
        )
        return

    if state == STATE_QUESTIONS_STYLE_CUSTOM:
        session = get_session(context)
        session["style"] = text
        await _run_prompt_generation(update, context)
        return

    if state == STATE_AWAIT_CORRECTION:
        session = get_session(context)
        original = session.get("prompt", "")
        msg = await update.message.reply_text("⏳ Обновляю промпт...")
        try:
            updated = await ai.refine_prompt(original, text)
            session["prompt"] = updated
            await msg.edit_text(
                f"✅ *Промпт обновлён:*\n\n```\n{updated}\n```",
                parse_mode="Markdown",
                reply_markup=prompt_ready_keyboard(),
            )
        except Exception as e:
            logger.error(f"Refine error: {e}")
            await msg.edit_text(
                f"❌ Ошибка обновления промпта.\n\n*Причина:* `{str(e)[:300]}`",
                parse_mode="Markdown",
            )
        return

    # Fallback
    await update.message.reply_text(
        "Выберите действие из меню 👇",
        reply_markup=main_menu_keyboard(),
    )


# ─── Voice handler ────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state", STATE_MAIN_MENU)

    if state not in (STATE_AWAIT_DESCRIPTION, STATE_AWAIT_PHOTO, STATE_MAIN_MENU):
        await update.message.reply_text("Сначала выберите действие из меню 👇", reply_markup=main_menu_keyboard())
        return

    msg = await update.message.reply_text("🎤 Расшифровываю голосовое сообщение...")

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_voice.ogg")
    await file.download_to_drive(file_path)

    try:
        text = await ai.transcribe_voice(file_path)
    except Exception as e:
        logger.error(f"Voice error: {e}")
        await msg.edit_text(
            f"❌ *Не удалось расшифровать голосовое.*\n\n"
            f"Причина: `{str(e)[:300]}`\n\n"
            "Попробуйте написать текстом.",
            parse_mode="Markdown",
        )
        return
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    session = get_session(context)
    session["description"] = text
    context.user_data["state"] = STATE_QUESTIONS_STYLE

    await msg.edit_text(
        f"✅ *Расшифровано:*\n_{text}_\n\n🎨 *Выберите стиль:*",
        parse_mode="Markdown",
        reply_markup=style_keyboard(),
    )


# ─── Photo handler ────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state", STATE_MAIN_MENU)

    if state == STATE_MAIN_MENU:
        # Auto-start photo flow
        context.user_data["state"] = STATE_AWAIT_PHOTO

    msg = await update.message.reply_text("🔍 Анализирую фото...")
    await update.message.reply_chat_action(ChatAction.TYPING)

    # Download photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = os.path.join(DOWNLOADS_DIR, f"{update.effective_user.id}_ref.jpg")

    try:
        await file.download_to_drive(file_path)
    except Exception as e:
        await msg.edit_text(f"❌ Не удалось скачать фото: `{e}`", parse_mode="Markdown")
        return

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        await msg.edit_text("❌ Фото пустое или не загрузилось. Попробуйте ещё раз.")
        return

    # Analyze photo
    try:
        analysis = await ai.analyze_image(file_path)
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await msg.edit_text(
            f"❌ *Не удалось проанализировать фото.*\n\n"
            f"*Причина:* `{str(e)[:400]}`\n\n"
            "Проверьте что ключ OpenAI активен и имеет доступ к GPT-4o.",
            parse_mode="Markdown",
        )
        return

    session = get_session(context)
    session["image_analysis"] = analysis
    session["ref_image_path"] = file_path

    # If caption, use as description
    if update.message.caption:
        session["description"] = update.message.caption

    await msg.edit_text(
        f"✅ *Фото проанализировано:*\n\n_{analysis[:600]}_\n\n"
        "🎨 *Выберите стиль для промпта:*",
        parse_mode="Markdown",
        reply_markup=style_keyboard(),
    )
    context.user_data["state"] = STATE_QUESTIONS_STYLE


# ─── Callback handler ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    session = get_session(context)

    # ── Style ──
    if data.startswith("style_"):
        if data == "style_custom":
            context.user_data["state"] = STATE_QUESTIONS_STYLE_CUSTOM
            await query.edit_message_text("✏️ Напишите свой стиль:", parse_mode="Markdown")
            return
        idx = int(data.split("_")[1])
        session["style"] = STYLE_OPTIONS[idx]
        await query.edit_message_text(
            f"✅ Стиль: *{session['style']}*\n\n⏳ Генерирую промпт...",
            parse_mode="Markdown",
        )
        await _run_prompt_generation_callback(query, context)
        return

    # ── Prompt approved → offer generation ──
    if data == "action_approve":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🎨 *Хотите сгенерировать изображение?*\n\n"
            "Выберите инструмент или просто скопируйте промпт:",
            parse_mode="Markdown",
            reply_markup=generate_choice_keyboard(),
        )
        return

    # ── Copy prompt ──
    if data == "action_copy":
        prompt = session.get("prompt", "")
        await query.message.reply_text(
            f"📋 *Готовый промпт — скопируйте:*\n\n```\n{prompt}\n```",
            parse_mode="Markdown",
        )
        return

    # ── Edit prompt ──
    if data == "action_edit":
        context.user_data["state"] = STATE_AWAIT_CORRECTION
        await query.message.reply_text(
            "✏️ *Напишите что нужно изменить:*\n\n"
            "Например: «сделай освещение мягче», «добавь закат», «убери людей»",
            parse_mode="Markdown",
        )
        return

    # ── Generate DALL-E ──
    if data == "gen_dalle":
        await query.edit_message_reply_markup(reply_markup=None)
        msg = await query.message.reply_text("🤖 Генерирую через DALL-E... (~20-30 сек)")
        prompt = session.get("prompt", "")
        try:
            image_bytes = await ai.generate_image_dalle(prompt)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(DOWNLOADS_DIR, f"{query.from_user.id}_{ts}.jpg")
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            session["generated_image_path"] = image_path
            await msg.delete()
            await query.message.reply_photo(
                photo=image_bytes,
                caption="🖼 *Готово! Изображение сгенерировано через DALL-E 3.*",
                parse_mode="Markdown",
                reply_markup=after_image_keyboard(),
            )
        except Exception as e:
            logger.error(f"DALL-E error: {e}")
            await msg.edit_text(
                f"❌ *Ошибка генерации через DALL-E.*\n\n"
                f"`{str(e)[:400]}`\n\n"
                "Попробуйте скопировать промпт и вставить в ChatGPT вручную.",
                parse_mode="Markdown",
            )
        return

    # ── Generate Gemini ──
    if data == "gen_gemini":
        await query.edit_message_reply_markup(reply_markup=None)
        from config import GOOGLE_API_KEY
        if not GOOGLE_API_KEY:
            prompt = session.get("prompt", "")
            await query.message.reply_text(
                "⚠️ *Ключ Google API не настроен.*\n\n"
                "Чтобы генерировать через Gemini, добавьте `GOOGLE_API_KEY` в файл `.env`.\n\n"
                "📋 *Пока что — вот промпт для ручного использования в Gemini:*\n\n"
                f"```\n{prompt}\n```\n\n"
                "Откройте [gemini.google.com](https://gemini.google.com), вставьте промпт и попросите создать изображение.",
                parse_mode="Markdown",
            )
            return

        msg = await query.message.reply_text("✨ Генерирую через Gemini... (~20-30 сек)")
        prompt = session.get("prompt", "")
        try:
            image_bytes = await ai.generate_image_gemini(prompt)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(DOWNLOADS_DIR, f"{query.from_user.id}_{ts}.jpg")
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            session["generated_image_path"] = image_path
            await msg.delete()
            await query.message.reply_photo(
                photo=image_bytes,
                caption="🖼 *Готово! Изображение сгенерировано через Gemini.*",
                parse_mode="Markdown",
                reply_markup=after_image_keyboard(),
            )
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            await msg.edit_text(
                f"❌ *Ошибка генерации через Gemini.*\n\n`{str(e)[:300]}`",
                parse_mode="Markdown",
            )
        return

    # ── Copy only ──
    if data == "gen_copy":
        prompt = session.get("prompt", "")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"📋 *Промпт готов — скопируйте и вставьте в нужный инструмент:*\n\n"
            f"```\n{prompt}\n```\n\n"
            "💡 Вставьте в ChatGPT, Midjourney, Gemini, Kling или другой инструмент.",
            parse_mode="Markdown",
        )
        return

    # ── Save prompt ──
    if data == "action_save_prompt":
        session["saving_what"] = "prompt"
        context.user_data["state"] = STATE_SAVE_CATEGORY
        await query.message.reply_text(
            "📂 *Выберите категорию:*",
            parse_mode="Markdown",
            reply_markup=save_category_keyboard(),
        )
        return

    # ── Save image ──
    if data == "action_save_image":
        image_path = session.get("generated_image_path")
        if not image_path:
            await query.message.reply_text("⚠️ Изображение ещё не сгенерировано.")
            return
        session["saving_what"] = "image"
        context.user_data["state"] = STATE_SAVE_CATEGORY
        await query.message.reply_text(
            "📂 *Выберите категорию:*",
            parse_mode="Markdown",
            reply_markup=save_category_keyboard(),
        )
        return

    # ── Save category chosen ──
    if data.startswith("savecat_"):
        idx = int(data.split("_")[1])
        category = SAVE_CATEGORIES[idx]
        prompt = session.get("prompt", "")
        title = (session.get("description") or session.get("image_analysis") or "Без названия")[:50]
        user_id = query.from_user.id

        saved_img = None
        if session.get("saving_what") == "image":
            image_path = session.get("generated_image_path")
            if image_path and os.path.exists(image_path):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                saved_img = os.path.join(SAVED_IMAGES_DIR, f"{user_id}_{ts}.jpg")
                shutil.copy2(image_path, saved_img)

        db.save_item(user_id, title, category, prompt, saved_img)
        await query.message.reply_text(
            f"✅ Сохранено в категорию *{category}*!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── Restart ──
    if data == "action_restart":
        reset_session(context)
        await query.message.reply_text(
            "🆕 Начинаем заново!\n\nВыберите действие:",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── Saved list ──
    if data == "go_saved_list":
        items = db.get_saved_items(query.from_user.id)
        if not items:
            await query.edit_message_text("💾 Нет сохранённых элементов.")
            return
        await query.edit_message_text(
            f"💾 *Сохранённые ({len(items)}):*",
            parse_mode="Markdown",
            reply_markup=saved_items_keyboard(items),
        )
        return

    if data.startswith("view_saved_"):
        item_id = int(data.split("_")[2])
        item = db.get_saved_item(item_id, query.from_user.id)
        if not item:
            await query.message.reply_text("❌ Не найдено.")
            return
        await query.edit_message_text(
            f"📁 *{item['title']}*\n🗂 {item['category']} | 📅 {item['created_at']}",
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
                await query.message.reply_photo(photo=f)
        else:
            await query.message.reply_text("❌ Изображение не найдено.")
        return

    if data.startswith("saved_del_"):
        item_id = int(data.split("_")[2])
        db.delete_saved_item(item_id, query.from_user.id)
        await query.edit_message_text("🗑 Удалено.")
        return


# ─── Prompt generation helpers ────────────────────────────────────────────────

async def _run_prompt_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user typed custom style."""
    session = get_session(context)
    msg = await update.message.reply_text("⏳ Генерирую профессиональный промпт...")
    try:
        prompt = await ai.generate_prompt(session)
        session["prompt"] = prompt
        context.user_data["state"] = STATE_PROMPT_READY
        await msg.edit_text(
            f"✅ *Готовый промпт:*\n\n```\n{prompt}\n```",
            parse_mode="Markdown",
            reply_markup=prompt_ready_keyboard(),
        )
    except Exception as e:
        logger.error(f"Prompt gen error: {e}")
        await msg.edit_text(
            f"❌ *Ошибка генерации промпта.*\n\n"
            f"`{str(e)[:400]}`\n\n"
            "Возможные причины:\n"
            "• Недостаточно средств на аккаунте OpenAI\n"
            "• Неверный API ключ\n"
            "• Нет доступа к модели GPT-4o\n\n"
            "Проверьте ключ на [platform.openai.com](https://platform.openai.com/api-keys)",
            parse_mode="Markdown",
        )


async def _run_prompt_generation_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Called after style selected via inline button."""
    session = get_session(context)
    try:
        prompt = await ai.generate_prompt(session)
        session["prompt"] = prompt
        context.user_data["state"] = STATE_PROMPT_READY
        await query.edit_message_text(
            f"✅ *Готовый промпт:*\n\n```\n{prompt}\n```",
            parse_mode="Markdown",
            reply_markup=prompt_ready_keyboard(),
        )
    except Exception as e:
        logger.error(f"Prompt gen error: {e}")
        await query.edit_message_text(
            f"❌ *Ошибка генерации промпта.*\n\n"
            f"`{str(e)[:400]}`\n\n"
            "Возможные причины:\n"
            "• Недостаточно средств на аккаунте OpenAI\n"
            "• Неверный API ключ\n"
            "• Нет доступа к модели GPT-4o\n\n"
            "Проверьте: [platform.openai.com](https://platform.openai.com)",
            parse_mode="Markdown",
        )


# ─── Saved list ───────────────────────────────────────────────────────────────

async def show_saved_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = db.get_saved_items(update.effective_user.id)
    if not items:
        await update.message.reply_text(
            "💾 *Пока ничего не сохранено.*\n\nСоздайте промпт и сохраните его!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return
    await update.message.reply_text(
        f"💾 *Сохранённые промпты и изображения ({len(items)}):*",
        parse_mode="Markdown",
        reply_markup=saved_items_keyboard(items),
    )
