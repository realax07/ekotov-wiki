"""Схема SQLite: инициализация БД (миграция/seed-init, sdd.md §4).

Запуск как скрипта:  python -m app.db   (из каталога backend/, DB_PATH из окружения —
см. app/config.py; локально: `DB_PATH=/tmp/app.db SECRET_KEY=x python -m app.db`).

Идемпотентность: CREATE TABLE/INDEX IF NOT EXISTS — повторный запуск не меняет
существующую схему и не дублирует объекты. WAL включается при каждом запуске
(PRAGMA journal_mode=WAL идемпотентен сам по себе).
"""

import sqlite3

from app.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  login         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL            -- bcrypt/argon2, не открытый пароль (NFR-7)
);

CREATE TABLE IF NOT EXISTS sessions (
  token       TEXT PRIMARY KEY,          -- криптостойкий случайный
  user_id     INTEGER NOT NULL REFERENCES users(id),
  created_at  TEXT NOT NULL,
  expires_at  TEXT NOT NULL              -- скользящий TTL
);

CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,             -- обязательно (FR-5)
  description TEXT,
  priority    TEXT CHECK(priority IN ('low','medium','high') OR priority IS NULL),
  category    TEXT,
  due_date    TEXT,                      -- YYYY-MM-DD
  is_fast     INTEGER NOT NULL DEFAULT 0,-- fast line (FR-3)
  status      TEXT NOT NULL DEFAULT 'todo'
              CHECK(status IN ('todo','in_progress','done')),  -- Ожидает/В работе/Выполнено (ОГР-3)
  archived_at TEXT,                      -- NOT NULL <=> в архиве (FR-4)
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
  id    INTEGER PRIMARY KEY,
  name  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS task_tags (
  task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL REFERENCES tags(id),
  PRIMARY KEY (task_id, tag_id)
);

CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY,
  task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  author_id  INTEGER NOT NULL REFERENCES users(id),
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_is_fast ON tasks(status, is_fast);
CREATE INDEX IF NOT EXISTS idx_tasks_archived_at ON tasks(archived_at);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_task_tags_tag_id ON task_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_comments_task_id ON comments(task_id);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Соединение с БД в WAL-режиме (NFR-5/§5); FK-контроль включен."""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Создает схему, если ее еще нет. Безопасен при повторном запуске."""
    path = db_path or settings.db_path
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Схема применена: {settings.db_path}")
