import sqlite3
import os
from datetime import datetime

DB_PATH = "ai_photos.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS saved_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            category TEXT,
            prompt_text TEXT,
            image_path TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_item(user_id: int, title: str, category: str, prompt_text: str, image_path: str = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO saved_items (user_id, title, category, prompt_text, image_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, title, category, prompt_text, image_path, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()
    item_id = c.lastrowid
    conn.close()
    return item_id


def get_saved_items(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM saved_items WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_saved_item(item_id: int, user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM saved_items WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return row


def delete_saved_item(item_id: int, user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM saved_items WHERE id = ? AND user_id = ?", (item_id, user_id))
    conn.commit()
    conn.close()
