"""
Generate a calendar image for the current month with tasks marked.
Uses Pillow only — no external APIs needed.
"""
import calendar
import io
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont

# Colors
BG_COLOR = (18, 18, 30)           # Dark background
HEADER_BG = (40, 40, 70)          # Header background
HEADER_TEXT = (255, 255, 255)      # White
WEEKDAY_COLOR = (160, 160, 200)    # Muted purple-white
WEEKEND_COLOR = (255, 120, 120)    # Red for weekend
TODAY_BG = (80, 130, 255)          # Blue highlight for today
TODAY_TEXT = (255, 255, 255)
TASK_DAY_BG = (60, 200, 120)       # Green for days with tasks
TASK_DAY_TEXT = (255, 255, 255)
NORMAL_TEXT = (220, 220, 240)
GRID_LINE = (40, 40, 60)
TASK_TEXT_COLOR = (180, 230, 180)
EMPTY_COLOR = (35, 35, 55)


def _load_font(size: int):
    """Try to load a nice font, fall back to default."""
    try:
        # Try common system fonts
        for font_path in [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    except Exception:
        pass
    return ImageFont.load_default()


def generate_calendar_image(tasks: list, year: int = None, month: int = None) -> bytes:
    """
    Generate a monthly calendar image.
    tasks: list of dicts with keys: title, date (YYYY-MM-DD), time
    Returns PNG bytes.
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # Build task map: {day: [task_strings]}
    task_map = {}
    for task in tasks:
        try:
            td = datetime.strptime(task["date"], "%Y-%m-%d").date()
            if td.year == year and td.month == month:
                time_prefix = f"{task['time']} " if task.get("time") else ""
                label = f"{time_prefix}{task['title']}"
                task_map.setdefault(td.day, []).append(label)
        except Exception:
            continue

    # Dimensions
    CELL_W = 160
    CELL_H = 110
    COLS = 7
    cal = calendar.monthcalendar(year, month)
    ROWS = len(cal)
    HEADER_H = 80
    WEEKDAY_H = 40
    PADDING = 20

    IMG_W = CELL_W * COLS + PADDING * 2
    IMG_H = HEADER_H + WEEKDAY_H + CELL_H * ROWS + PADDING * 2

    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = _load_font(28)
    font_weekday = _load_font(16)
    font_day = _load_font(22)
    font_task = _load_font(13)

    # ── Header ──
    MONTH_NAMES = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    draw.rectangle([(0, 0), (IMG_W, HEADER_H)], fill=HEADER_BG)
    title_text = f"{MONTH_NAMES[month]} {year}"
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) // 2, 22), title_text, font=font_title, fill=HEADER_TEXT)

    # ── Weekday headers ──
    WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    y_wd = HEADER_H
    draw.rectangle([(0, y_wd), (IMG_W, y_wd + WEEKDAY_H)], fill=(28, 28, 50))
    for col, wd in enumerate(WEEKDAYS):
        x = PADDING + col * CELL_W
        color = WEEKEND_COLOR if col >= 5 else WEEKDAY_COLOR
        bbox = draw.textbbox((0, 0), wd, font=font_weekday)
        tw = bbox[2] - bbox[0]
        draw.text((x + (CELL_W - tw) // 2, y_wd + 10), wd, font=font_weekday, fill=color)

    # ── Calendar cells ──
    y_start = HEADER_H + WEEKDAY_H + PADDING

    for row_i, week in enumerate(cal):
        for col_i, day in enumerate(week):
            x = PADDING + col_i * CELL_W
            y = y_start + row_i * CELL_H

            # Cell background
            if day == 0:
                cell_bg = EMPTY_COLOR
            elif day == today.day and year == today.year and month == today.month:
                cell_bg = TODAY_BG
            elif day in task_map:
                cell_bg = (30, 80, 50)
            else:
                cell_bg = (25, 25, 45)

            # Draw cell
            draw.rectangle(
                [(x + 2, y + 2), (x + CELL_W - 2, y + CELL_H - 2)],
                fill=cell_bg, outline=GRID_LINE, width=1
            )

            if day == 0:
                continue

            # Day number
            is_weekend = col_i >= 5
            if day == today.day and year == today.year and month == today.month:
                day_color = TODAY_TEXT
            elif is_weekend:
                day_color = WEEKEND_COLOR
            else:
                day_color = NORMAL_TEXT

            draw.text((x + 8, y + 6), str(day), font=font_day, fill=day_color)

            # Task labels
            if day in task_map:
                max_tasks = 3
                for ti, task_label in enumerate(task_map[day][:max_tasks]):
                    label = task_label[:20] + ("…" if len(task_label) > 20 else "")
                    ty = y + 36 + ti * 22
                    # Task background pill
                    tb = draw.textbbox((0, 0), label, font=font_task)
                    tw = tb[2] - tb[0]
                    draw.rectangle(
                        [(x + 5, ty - 2), (x + 5 + tw + 6, ty + 16)],
                        fill=(40, 160, 90), outline=None
                    )
                    draw.text((x + 8, ty), label, font=font_task, fill=(255, 255, 255))
                if len(task_map[day]) > max_tasks:
                    more = f"+{len(task_map[day]) - max_tasks} ещё"
                    draw.text((x + 8, y + CELL_H - 20), more, font=font_task, fill=TASK_TEXT_COLOR)

    # ── Legend ──
    # (add a small legend at the bottom if space allows)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def generate_today_image(tasks_today: list, today_date: date = None) -> bytes:
    """Generate a simple image showing today's tasks."""
    if today_date is None:
        today_date = date.today()

    MONTH_NAMES = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    WEEKDAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    W = 700
    TASK_H = 60
    HEADER_H = 120
    PADDING = 30
    H = HEADER_H + max(len(tasks_today), 1) * TASK_H + PADDING * 2

    img = Image.new("RGB", (W, H), (18, 18, 30))
    draw = ImageDraw.Draw(img)

    font_big = _load_font(30)
    font_med = _load_font(20)
    font_small = _load_font(16)

    # Header
    draw.rectangle([(0, 0), (W, HEADER_H)], fill=(40, 40, 70))
    weekday_str = WEEKDAYS_FULL[today_date.weekday()]
    date_str = f"{weekday_str}, {today_date.day} {MONTH_NAMES[today_date.month]} {today_date.year}"
    draw.text((PADDING, 20), "📅 Сегодня:", font=font_med, fill=(180, 180, 255))
    draw.text((PADDING, 55), date_str, font=font_big, fill=(255, 255, 255))

    if not tasks_today:
        draw.text((PADDING, HEADER_H + PADDING), "✅ Задач на сегодня нет!", font=font_med, fill=(100, 220, 130))
    else:
        for i, task in enumerate(tasks_today):
            y = HEADER_H + PADDING + i * TASK_H
            time_str = task.get("time") or "  —  "
            title = task["title"]

            # Time badge
            draw.rectangle([(PADDING, y + 8), (PADDING + 80, y + 38)], fill=(60, 100, 200))
            draw.text((PADDING + 8, y + 12), time_str, font=font_small, fill=(255, 255, 255))

            # Task title
            draw.text((PADDING + 95, y + 12), title[:50], font=font_med, fill=(220, 220, 255))

            # Divider
            draw.line([(PADDING, y + TASK_H - 2), (W - PADDING, y + TASK_H - 2)], fill=(40, 40, 60), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
