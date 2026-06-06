import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в переменных окружения.")

# Directories
DOWNLOADS_DIR = "downloads"
SAVED_IMAGES_DIR = "saved_images"

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(SAVED_IMAGES_DIR, exist_ok=True)

# Conversation states
(
    STATE_MAIN_MENU,
    STATE_AWAIT_INPUT,
    STATE_QUESTIONS_RESULT_TYPE,
    STATE_QUESTIONS_OUTPUT_TYPE,
    STATE_QUESTIONS_PRESERVE,
    STATE_QUESTIONS_STYLE,
    STATE_QUESTIONS_TOOL,
    STATE_QUESTIONS_LIGHTING,
    STATE_PROMPT_READY,
    STATE_AWAIT_CORRECTION,
    STATE_SAVED_MENU,
    STATE_SAVE_CATEGORY,
) = range(12)

STYLE_OPTIONS = [
    "Реалистичный",
    "Кинематографический",
    "Люкс / Премиум",
    "Предметная съёмка",
    "Недвижимость",
    "Instagram контент",
    "Коммерческая реклама",
    "Минимализм",
]

LIGHTING_OPTIONS = [
    "Дневной свет",
    "Золотой час",
    "Студийный свет",
    "Мягкий свет",
    "Тёмный люкс-муд",
    "Драматическое освещение",
]

TOOL_OPTIONS = [
    "Midjourney",
    "DALL-E",
    "Stable Diffusion",
    "Kling",
    "Veo",
    "Runway",
    "Sora",
    "Другой",
]

SAVE_CATEGORIES = [
    "Недвижимость",
    "Предметная съёмка",
    "Instagram",
    "Видео",
    "Личное",
    "Другое",
]
