import sqlite3
from datetime import datetime

DB_PATH = "calendar.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            task_date TEXT NOT NULL,
            task_time TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_task(user_id: int, title: str, task_date: str, task_time: str = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (user_id, title, task_date, task_time, created_at) VALUES (?,?,?,?,?)",
        (user_id, title, task_date, task_time, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def get_tasks_for_date(user_id: int, date_str: str):
    """date_str format: YYYY-MM-DD"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND task_date=? ORDER BY task_time",
        (user_id, date_str),
    ).fetchall()
    conn.close()
    return rows


def get_upcoming_tasks(user_id: int, from_date: str, days: int = 30):
    """Get tasks for the next N days."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND task_date>=? ORDER BY task_date, task_time LIMIT 100",
        (user_id, from_date),
    ).fetchall()
    conn.close()
    return rows


def get_month_tasks(user_id: int, year: int, month: int):
    """Get all tasks for a given month."""
    month_str = f"{year}-{month:02d}"
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND task_date LIKE ? ORDER BY task_date, task_time",
        (user_id, f"{month_str}-%"),
    ).fetchall()
    conn.close()
    return rows


def get_task_by_id(task_id: int, user_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
    ).fetchone()
    conn.close()
    return row


def delete_task(task_id: int, user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
    conn.commit()
    conn.close()


def get_all_future_tasks_with_time(from_datetime_str: str):
    """Get all tasks that have a time set, for scheduling reminders."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM tasks WHERE task_time IS NOT NULL AND task_time != ''
           AND (task_date || ' ' || task_time) >= ?
           ORDER BY task_date, task_time""",
        (from_datetime_str,),
    ).fetchall()
    conn.close()
    return rows


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT user_id FROM tasks").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]
