"""
SQLite persistence for users and their squads.

Owner: Member 1 (Data & Persistence)

Replaces storage.py's single-file JSON approach now that the app supports
multiple users — each user needs their own saved squad.
"""

import os
import sqlite3
import json
from contextlib import contextmanager
from models import Squad

# On a host like Railway, set FPL_DB_PATH to a path on a mounted volume (e.g. /data/fpl_advisor.db)
# so accounts and squads survive redeploys. Locally it defaults to a file next to the app.
DB_PATH = os.environ.get("FPL_DB_PATH", "fpl_advisor.db")


def init_db(db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS squads (
                user_id INTEGER PRIMARY KEY,
                squad_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()


@contextmanager
def _connect(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------- users ----------

def create_user(username: str, password_hash: str, salt: str, db_path: str = DB_PATH) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username, password_hash, salt),
        )
        conn.commit()
        return cur.lastrowid


def get_user_by_username(username: str, db_path: str = DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int, db_path: str = DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------- squads ----------

def save_squad_for_user(user_id: int, squad: Squad, db_path: str = DB_PATH) -> None:
    squad_json = json.dumps(squad.to_dict())
    with _connect(db_path) as conn:
        conn.execute("""
            INSERT INTO squads (user_id, squad_json) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET squad_json = excluded.squad_json
        """, (user_id, squad_json))
        conn.commit()


def load_squad_for_user(user_id: int, db_path: str = DB_PATH) -> Squad:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT squad_json FROM squads WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return Squad()  # empty squad, default budget
        return Squad.from_dict(json.loads(row["squad_json"]))
