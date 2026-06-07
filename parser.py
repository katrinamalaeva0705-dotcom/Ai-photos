"""
Parse tasks from Russian text.
Supports formats like:
  - "15 июня 10:00 - Встреча с клиентом"
  - "15.06 10:00 Встреча с клиентом"
  - "15/06/2025 Встреча с клиентом"
  - "завтра 10:00 Встреча"
  - "сегодня 15:00 Звонок"
  - Multi-line list of the above
"""
import re
from datetime import datetime, timedelta

MONTHS_RU = {
    "января": 1, "январе": 1, "январь": 1,
    "февраля": 2, "феврале": 2, "февраль": 2,
    "марта": 3, "марте": 3, "март": 3,
    "апреля": 4, "апреле": 4, "апрель": 4,
    "мая": 5, "мае": 5, "май": 5,
    "июня": 6, "июне": 6, "июнь": 6,
    "июля": 7, "июле": 7, "июль": 7,
    "августа": 8, "августе": 8, "август": 8,
    "сентября": 9, "сентябре": 9, "сентябрь": 9,
    "октября": 10, "октябре": 10, "октябрь": 10,
    "ноября": 11, "ноябре": 11, "ноябрь": 11,
    "декабря": 12, "декабре": 12, "декабрь": 12,
}


def parse_tasks(text: str):
    """
    Parse one or multiple tasks from text.
    Returns list of dicts: {title, date (YYYY-MM-DD), time (HH:MM or None)}
    """
    results = []
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # If single line, treat whole text as one task attempt
    if len(lines) == 1:
        task = _parse_line(lines[0])
        if task:
            results.append(task)
    else:
        for line in lines:
            task = _parse_line(line)
            if task:
                results.append(task)

    return results


def _parse_line(line: str):
    """Parse a single line into a task dict."""
    now = datetime.now()
    today = now.date()

    line_lower = line.lower()

    # ── Detect date ──
    date = None
    time_val = None
    title = line

    # "сегодня" / "today"
    if line_lower.startswith("сегодня"):
        date = today
        title = re.sub(r'^сегодня\s*', '', line, flags=re.IGNORECASE).strip()

    # "завтра" / "tomorrow"
    elif line_lower.startswith("завтра"):
        date = today + timedelta(days=1)
        title = re.sub(r'^завтра\s*', '', line, flags=re.IGNORECASE).strip()

    else:
        # Try "DD месяц" or "DD месяц YYYY"
        m = re.match(
            r'^(\d{1,2})\s+(' + '|'.join(MONTHS_RU.keys()) + r')(?:\s+(\d{4}))?(.*)$',
            line, re.IGNORECASE
        )
        if m:
            day = int(m.group(1))
            month = MONTHS_RU[m.group(2).lower()]
            year = int(m.group(3)) if m.group(3) else today.year
            try:
                date = datetime(year, month, day).date()
                # If date is in the past (same month), push to next year
                if date < today and not m.group(3):
                    date = datetime(year + 1, month, day).date()
            except ValueError:
                return None
            title = m.group(4).strip()

        else:
            # Try DD.MM or DD.MM.YYYY or DD/MM/YYYY
            m = re.match(
                r'^(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?(.*)$', line
            )
            if m:
                day, month = int(m.group(1)), int(m.group(2))
                year = int(m.group(3)) if m.group(3) else today.year
                try:
                    date = datetime(year, month, day).date()
                    if date < today and not m.group(3):
                        date = datetime(year + 1, month, day).date()
                except ValueError:
                    return None
                title = m.group(4).strip()

    if date is None:
        return None

    # ── Detect time in title ──
    time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', title)
    if time_match:
        h, mn = int(time_match.group(1)), int(time_match.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            time_val = f"{h:02d}:{mn:02d}"
            title = title[:time_match.start()] + title[time_match.end():]

    # Clean title: remove leading dashes, commas, etc.
    title = re.sub(r'^[\s\-–—,:]+', '', title).strip()
    title = re.sub(r'[\s\-–—,:]+$', '', title).strip()

    if not title:
        return None

    return {
        "title": title,
        "date": date.strftime("%Y-%m-%d"),
        "time": time_val,
    }


def format_date_ru(date_str: str) -> str:
    """Format YYYY-MM-DD to Russian readable: '15 июня 2025'"""
    MONTHS_GEN = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day} {MONTHS_GEN[dt.month]} {dt.year}"
    except Exception:
        return date_str


def format_weekday_ru(date_str: str) -> str:
    DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return DAYS[dt.weekday()]
    except Exception:
        return ""
