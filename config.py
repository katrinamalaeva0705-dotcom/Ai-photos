import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")

# Timezone (change to your timezone if needed)
TIMEZONE = "Europe/Moscow"

# Morning reminder time
MORNING_HOUR = 9
MORNING_MINUTE = 0

# States
(
    STATE_IDLE,
    STATE_ADD_SINGLE,
    STATE_ADD_LIST,
    STATE_DELETE,
) = range(4)
