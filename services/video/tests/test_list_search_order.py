"""Тесты поиска и сортировки списка video-сервиса (задача 4.1, волна 4,
кусок C).

По конвенции services/video/tests (паритет test_videos_service.py — кусок A,
test_social.py — кусок D): TestClient над app.main, БД — временная sqlite в
фикстуре, том — временный каталог; без сети и внешних сервисов.

Трассировка: Requirement «Сортировка и поиск по имени» / Scenario «Поиск и
сортировка» дельты specs/video-service (≥ 3 видео, кириллица, регистр);
нумерация TC-vid-0xx продолжает кусок B (TC-vid-060…074):
TC-vid-080 — поиск по подстроке имени без учета регистра (латиница);
TC-vid-081 — поиск по подстроке без учета регистра (КИРИЛЛИЦА: встроенный
  lower() SQLite ASCII-only, unicode-lower db.py);
TC-vid-082 — сортировка по имени в обе стороны (asc/desc, регистр);
TC-vid-083 — комбинирование ?query= с фильтром категории ?category=;
TC-vid-084 — % и _ в query — литералы, не wildcard'ы LIKE (ESCAPE '\');
TC-vid-085 — пустой/whitespace query — все видео; неверный order — 422;
TC-vid-086 — совпадений нет: 200 с пустым списком; порядок без order не
  изменился (новые сверху — паритет test_list_order_newest_first).
"""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

# Схема — дословно как в test_videos_service.py (куски A + D).
SCHEMA_SQL = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  login TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  role TEXT,
  bio TEXT,
  avatar_path TEXT,
  avatar_updated_at TEXT
);
CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE image_categories (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);
CREATE TABLE video_videos (
  id               TEXT NOT NULL PRIMARY KEY,
  filename         TEXT NOT NULL,
  status           TEXT NOT NULL,
  size_bytes       INTEGER NOT NULL,
  mime             TEXT,
  uploaded_by      INTEGER NOT NULL REFERENCES users(id),
  created_at       TEXT NOT NULL,
  convert_attempts INTEGER NOT NULL DEFAULT 0,
  category_id      INTEGER REFERENCES image_categories(id)
);
CREATE TABLE video_comments (
  id         TEXT NOT NULL PRIMARY KEY,
  video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  text       TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE video_reactions (
  video_id   TEXT NOT NULL REFERENCES video_videos(id) ON DELETE CASCADE,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  value      INTEGER NOT NULL CHECK (value IN (1, -1)),
  created_at TEXT NOT NULL,
  PRIMARY KEY (video_id, user_id)
);
"""


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite: users/sessions + image_categories + сессия owner."""
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Owner')"
        )
        conn.executemany(
            "INSERT INTO image_categories (id, name) VALUES (?, ?)",
            ((10, "семья"), (20, "дом")),
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES ('test-token-1', 1, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("EKOTOV_WIKI_DB_PATH", path)
    return path


@pytest.fixture()
def videos_dir(tmp_path, monkeypatch):
    d = str(tmp_path / "videos-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", d)
    return d


@pytest.fixture()
def client(db_path, videos_dir):
    """Клиент-owner (сессия test-token-1)."""
    with TestClient(app) as c:
        c.cookies.set(SESSION_COOKIE_NAME, "test-token-1")
        yield c


def _insert(db_path, filename, status="ready", category_id=None):
    """Прямая вставка записи с контролируемым именем (поиск/сортировка
    проверяют список, не загрузку; статус/категория произвольные)."""
    video_id = uuid.uuid4().hex
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
            " uploaded_by, created_at, convert_attempts, category_id)"
            " VALUES (?, ?, ?, 10, 'video/mp4', 1, ?, 0, ?)",
            (video_id, filename, status, "2026-10-17T00:00:00+00:00", category_id),
        )
        conn.commit()
    finally:
        conn.close()
    return video_id


def _names(resp):
    return [item["filename"] for item in resp.json()["videos"]]


# --------------------------------------------------------------------------
# Поиск по подстроке имени (Scenario «Поиск и сортировка»: регистр)
# --------------------------------------------------------------------------


def test_search_substring_case_insensitive_latin(client, db_path):
    """TC-vid-080: ?query=<подстрока> фильтрует по имени без учета регистра
    (латиница): «ОБЗОР», «обзор», «Обзор» находят одни и те же записи."""
    _insert(db_path, "Обзор дома.mp4")
    _insert(db_path, "обзор дачи.mkv")
    _insert(db_path, "Отпуск.mov")

    for needle in ("ОБЗОР", "обзор", "Обзор", "зоР"):
        names = _names(client.get("/api/videos", params={"query": needle}))
        assert sorted(names) == ["Обзор дома.mp4", "обзор дачи.mkv"], needle


def test_search_substring_case_insensitive_cyrillic(client, db_path):
    """TC-vid-081 (+ approved TC-vid-023: поиск по подстроке без учета
    регистра): кириллица без учета регистра (спека прямо требует
    кириллицу): встроенный lower() SQLite — ASCII-only, unicode-lower
    db.py складывает «ДОМ»/«дом»/«Дом»."""
    _insert(db_path, "Интерьер ДОМА.jpg.mp4")
    _insert(db_path, "дом у озера.mkv")
    _insert(db_path, "Дачный сезон.mp4")

    for needle in ("ДОМ", "дом", "Дом"):
        names = _names(client.get("/api/videos", params={"query": needle}))
        assert sorted(names) == ["Интерьер ДОМА.jpg.mp4", "дом у озера.mkv"], needle


# --------------------------------------------------------------------------
# Сортировка по имени в обе стороны
# --------------------------------------------------------------------------


def test_order_by_name_asc_desc(client, db_path):
    """TC-vid-082: ?order=asc|desc сортирует по имени без учета регистра
    в обе стороны; asc — «Имя А→Я» мокапа, desc — ровно обратный порядок."""
    _insert(db_path, "яблоко.mp4")
    _insert(db_path, "Банан.mkv")
    _insert(db_path, "abricot.mov")
    _insert(db_path, "Вишня.mp4")

    asc = _names(client.get("/api/videos", params={"order": "asc"}))
    assert asc == ["abricot.mov", "Банан.mkv", "Вишня.mp4", "яблоко.mp4"]

    desc = _names(client.get("/api/videos", params={"order": "desc"}))
    assert desc == list(reversed(asc))


# --------------------------------------------------------------------------
# Комбинирование с фильтром категории (кусок D)
# --------------------------------------------------------------------------


def test_query_combined_with_category_filter(client, db_path):
    """TC-vid-083: ?query= комбинируется с ?category= (И, не ИЛИ):
    «обзор» в двух категориях — с category=10 остается одна; none тоже
    комбинируется."""
    _insert(db_path, "обзор дома.mp4", category_id=10)
    _insert(db_path, "обзор дачи.mkv", category_id=20)
    _insert(db_path, "обзор сада.mov")

    names = _names(
        client.get("/api/videos", params={"query": "обзор", "category": "10"})
    )
    assert names == ["обзор дома.mp4"]

    names = _names(
        client.get("/api/videos", params={"query": "обзор", "category": "none"})
    )
    assert names == ["обзор сада.mov"]


# --------------------------------------------------------------------------
# Литеральность %/_ (ESCAPE) и негативные ветки
# --------------------------------------------------------------------------


def test_like_wildcards_are_literals(client, db_path):
    """TC-vid-084: % и _ в query — обычные символы имени, а не wildcard'ы
    LIKE: «a_b» находит только буквальное a_b.mkv, не axb.mkv."""
    _insert(db_path, "a_b.mkv")
    _insert(db_path, "axb.mkv")
    _insert(db_path, "100%.mp4")

    assert _names(client.get("/api/videos", params={"query": "a_b"})) == ["a_b.mkv"]
    assert _names(client.get("/api/videos", params={"query": "100%"})) == ["100%.mp4"]


def test_empty_query_all_and_invalid_order_422(client, db_path):
    """TC-vid-085: пустой/whitespace query — все видео; неизвестный order —
    422 в форме ядра {error: validation error}."""
    _insert(db_path, "Обзор дома.mp4")
    _insert(db_path, "обзор дачи.mkv")
    _insert(db_path, "Отпуск.mov")

    for qs in ("", "   "):
        names = _names(client.get("/api/videos", params={"query": qs}))
        assert len(names) == 3, qs

    resp = client.get("/api/videos", params={"order": "sideways"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"


def test_no_matches_and_default_order_unchanged(client, db_path):
    """TC-vid-086: без совпадений — 200 и пустой список; без order порядок
    прежний — новые сверху (паритет test_list_order_newest_first куска A)."""
    _insert(db_path, "alpha.mp4")
    beta = _insert(db_path, "beta.mp4")
    conn = sqlite3.connect(db_path)
    try:
        # beta «новее»: вставлены одинаково — двигаем alpha в прошлое.
        conn.execute(
            "UPDATE video_videos SET created_at = '2026-10-01T00:00:00+00:00'"
            " WHERE filename = 'alpha.mp4'"
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/videos", params={"query": "несуществует"})
    assert resp.status_code == 200
    assert resp.json()["videos"] == []

    names = _names(client.get("/api/videos"))
    assert names == ["beta.mp4", "alpha.mp4"]
    assert client.get("/api/videos").json()["videos"][0]["id"] == beta


# --------------------------------------------------------------------------
# TC-vid-024 — unicode-имена: загрузка, поиск, сортировка
# --------------------------------------------------------------------------


def test_unicode_names_upload_search_sort(client, db_path):
    """TC-vid-024 (граничный, Scenario «Поиск и сортировка» — unicode):
    загрузка имен с кавычками/дефисом/№, emoji и 255-байтного UTF-8 имени
    — 201 без искажений; поиск находит по unicode-подстроке и emoji;
    сортировка в обе стороны стабильна, без дублей."""
    names = [
        "видео №1 — «тест».mkv",
        "🎬emoji.mp4",
        "а" * 127 + "я" * 128 + ".mp4",  # 255 байт UTF-8 (2-байтные коды)
    ]
    for name in names:
        resp = client.post(
            "/api/videos",
            files={"file": (name, b"unicode-bytes", "video/x-matroska")},
        )
        assert resp.status_code == 201, (name, resp.text)
        assert resp.json()["filename"] == name

    listed = _names(client.get("/api/videos"))
    assert sorted(listed) == sorted(names)
    assert len(set(listed)) == 3  # без дублей и искажений

    for needle, expected in (("№1", [names[0]]), ("🎬", [names[1]])):
        found = _names(client.get("/api/videos", params={"query": needle}))
        assert found == expected, (needle, found)

    asc = _names(client.get("/api/videos", params={"order": "asc"}))
    desc = _names(client.get("/api/videos", params={"order": "desc"}))
    assert asc == list(reversed(desc))  # стабильность в обе стороны
