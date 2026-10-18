"""Тесты социального слоя video-сервиса (задача 2.5, video-hosting волна 2,
кусок D).

По конвенции services/video/tests (паритет test_videos_service.py — кусок A,
задача 1.6): TestClient над app.main, БД — временная sqlite в фикстуре,
том — временный каталог; без сети и внешних сервисов.

Трассировка: сценарии дельты specs/video-service (кусок D) —
Requirement/Scenario в docstring каждого теста; нумерация TC-vid-0xx
продолжает кусок A:
TC-vid-040…043 — NFR-38: 401 без сессии на ВСЕ D-эндпоинты (comments
  GET/POST/DELETE, reaction PUT, categories GET) — состояние не меняется;
TC-vid-044…048 — комментарии: 201+автор в списке / 422 пустой и
  whitespace / 404 видео / удаление СВОЕГО 200 / ЧУЖОГО 403 / 404;
TC-vid-049…052 — реакции: постановка (счетчик +1) / повторный клик
  снимает (ровно -1, my_reaction=null) / перенос на вторую кнопку
  (лайк → дизлайк, счетчики ровно на единицу) / два пользователя
  независимо, ровно одна строка на пару (PK) / value не 1|-1 → 422;
TC-vid-053…057 — категории: справочник = image_categories (RO) /
  upload с валидным category_id / 422 на несуществующий / NULL = «Без
  категории» / фильтр ?category=<id> и ?category=none;
TC-vid-058 — CASCADE: удаление видео чистит комментарии и реакции.
"""

import io
import os
import threading
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

AUTH = {"error": "unauthorized"}

# Схема — дословно как в test_videos_service.py (куски A + D): users/
# sessions ядра + image_categories + таблицы сервиса по DDL миграции.
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
    """Временная sqlite: users/sessions + image_categories (2 шт.) + сессии
    двух пользователей; env сервиса на нее переключен."""
    path = str(tmp_path / "wiki.db")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (1, 'owner', 'x', 'Owner')"
        )
        conn.execute(
            "INSERT INTO users (id, login, password_hash, display_name)"
            " VALUES (2, 'pe', 'x', 'PE')"
        )
        conn.executemany(
            "INSERT INTO image_categories (id, name) VALUES (?, ?)",
            ((10, "семья"), (20, "дом")),
        )
        for token, user in (("test-token-1", 1), ("test-token-2", 2)):
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    token,
                    user,
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


def _client(db_path, videos_dir, token):
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        yield client


@pytest.fixture()
def client(db_path, videos_dir):
    """Клиент-owner (сессия test-token-1)."""
    yield from _client(db_path, videos_dir, "test-token-1")


@pytest.fixture()
def client2(db_path, videos_dir):
    """Клиент-PE (сессия test-token-2) — второй пользователь."""
    yield from _client(db_path, videos_dir, "test-token-2")


@pytest.fixture()
def anon_client(db_path, videos_dir):
    with TestClient(app) as client:
        yield client


def _upload(client, name="clip.mkv", content=b"fake-video-bytes-0123456789",
            content_type="video/x-matroska", category_id=None):
    data = {}
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post(
        "/api/videos",
        files={"file": (name, content, content_type)},
        data=data,
    )


def _insert_video(db_path, video_id=None, category_id=None):
    """Прямая вставка видео (для тестов поверх готовой записи)."""
    video_id = video_id or uuid.uuid4().hex
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
            " uploaded_by, created_at, convert_attempts, category_id)"
            " VALUES (?, 'row.mkv', 'ready', 10, 'video/x-matroska', 1, ?, 0, ?)",
            (video_id, "2026-10-17T00:00:00+00:00", category_id),
        )
        conn.commit()
    finally:
        conn.close()
    return video_id


# --------------------------------------------------------------------------
# NFR-38: все D-эндпоинты — только авторизованные
# --------------------------------------------------------------------------


def test_social_endpoints_unauthorized_401(anon_client, client, db_path):
    """NFR-38, Scenario «Комментарий и реакция без сессии» + «Список
    категорий без сессии»: без валидной сессии каждый D-эндпоинт —
    401 {error: unauthorized}; состояние комментариев и счетчиков
    НЕ изменилось.
    Трассировка approved-кейса: TC-vid-040 (социальные операции и
    категории без сессии — 401, состояние не изменилось)."""
    video_id = _insert_video(db_path)
    checks = [
        anon_client.get(f"/api/videos/{video_id}/comments"),
        anon_client.post(f"/api/videos/{video_id}/comments", json={"text": "х"}),
        anon_client.delete(f"/api/videos/{video_id}/comments/cid"),
        anon_client.put(f"/api/videos/{video_id}/reaction", json={"value": 1}),
        anon_client.get("/api/videos/categories"),
        anon_client.get("/api/videos"),  # фильтр категории — тоже за сессией
        anon_client.get("/api/videos?category=none"),
    ]
    for resp in checks:
        assert resp.status_code == 401, resp.request.url
        assert resp.json() == AUTH

    # Состояние не изменилось (проверено авторизованным клиентом).
    assert client.get(f"/api/videos/{video_id}/comments").json() == {"comments": []}
    assert client.get("/api/videos").json()["videos"][0]["likes"] == 0


# --------------------------------------------------------------------------
# Комментарии (Requirement «Комментарии к видео»)
# --------------------------------------------------------------------------


def test_comment_add_list_author(client, client2, db_path):
    """Scenario «Добавление комментария» + «Видимость»: 201; в списке —
    автор (display_name), время, текст; пользователь_id — для рендера
    «удалить» только у своих.
    Трассировка approved-кейса: TC-vid-025 (два пользователя: pe видит
    комментарий owner — автор, время, текст)."""
    video_id = _insert_video(db_path)
    resp = client.post(
        f"/api/videos/{video_id}/comments", json={"text": "Отличный обзор!"}
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["text"] == "Отличный обзор!"
    assert created["user"] == "Owner"  # COALESCE(display_name, login)
    assert created["user_id"] == 1
    assert created["id"]
    assert created["created_at"]

    listing = client2.get(f"/api/videos/{video_id}/comments")
    assert listing.status_code == 200
    comments = listing.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["user"] == "Owner"
    assert comments[0]["text"] == "Отличный обзор!"


def test_comment_empty_and_whitespace_422(client, db_path):
    """Scenario «Пустой комментарий отклоняется»: пустой,
    whitespace-текст и тело без поля text — 422; записей нет.
    Трассировка approved-кейса: TC-vid-026."""
    video_id = _insert_video(db_path)
    for body in ({"text": ""}, {"text": "   \n\t "}, {}):
        resp = client.post(f"/api/videos/{video_id}/comments", json=body)
        assert resp.status_code == 422, body
    assert client.get(f"/api/videos/{video_id}/comments").json() == {"comments": []}


def test_comment_video_not_found_404(client, db_path):
    """Комментарии несуществующего видео — 404 (list/add/delete)."""
    for method, kwargs in (
        ("get", {}), ("post", {"json": {"text": "х"}}),
    ):
        resp = getattr(client, method)("/api/videos/no-such/comments", **kwargs)
        assert resp.status_code == 404


def test_comment_delete_only_own(client, client2, db_path):
    """Scenario «Удаление только своего комментария»: свой — 200 и строка
    удалена; чужой — 403 и строка на месте; неизвестный — 404.
    Трассировка approved-кейсов: TC-vid-027 (удаление своего),
    TC-vid-028 (чужой удалить нельзя — 403 по эскалации E-3)."""
    video_id = _insert_video(db_path)
    mine = client.post(
        f"/api/videos/{video_id}/comments", json={"text": "мой"}
    ).json()
    foreign = client2.post(
        f"/api/videos/{video_id}/comments", json={"text": "чужой"}
    ).json()

    # Чужой комментарий нельзя удалить (PE удаляет комментарий owner).
    forbidden = client2.delete(
        f"/api/videos/{video_id}/comments/{mine['id']}"
    )
    assert forbidden.status_code == 403

    # Свой — можно (PE удаляет свой).
    ok = client2.delete(f"/api/videos/{video_id}/comments/{foreign['id']}")
    assert ok.status_code == 200

    # Неизвестный cid — 404.
    assert (
        client.delete(f"/api/videos/{video_id}/comments/{uuid.uuid4().hex}").status_code
        == 404
    )

    remaining = client.get(f"/api/videos/{video_id}/comments").json()["comments"]
    assert [c["text"] for c in remaining] == ["мой"]


# --------------------------------------------------------------------------
# Реакции (Requirement «Лайки и дизлайки — один голос на пользователя»)
# --------------------------------------------------------------------------


def test_reaction_put_toggle_move(client, db_path):
    """Сценарии реакций: постановка (+1 ровно), повторный клик снимает
    (my_reaction=null), клик по второй переносит (лайк → дизлайк) —
    счетчики меняются ровно на единицу.
    Трассировка approved-кейсов: TC-vid-030 (перенос голоса),
    TC-vid-031 (повторный клик снимает голос)."""
    video_id = _insert_video(db_path)
    url = f"/api/videos/{video_id}/reaction"

    # Постановка лайка.
    r = client.put(url, json={"value": 1})
    assert r.status_code == 200
    assert r.json() == {"my_reaction": 1, "likes": 1, "dislikes": 0}

    # Повторный клик — снятие.
    r = client.put(url, json={"value": 1})
    assert r.json() == {"my_reaction": None, "likes": 0, "dislikes": 0}

    # Перенос: лайк → дизлайк одной строкой (UPDATE).
    client.put(url, json={"value": 1})
    r = client.put(url, json={"value": -1})
    assert r.json() == {"my_reaction": -1, "likes": 0, "dislikes": 1}

    # Ровно одна строка на пару видео+пользователь (PK(video_id,user_id)).
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT value FROM video_reactions WHERE video_id = ?", (video_id,)
        ).fetchall()
    finally:
        conn.close()
    assert rows == [(-1,)]


def test_reaction_two_users_independent(client, client2, db_path):
    """Два пользователя голосуют независимо; счетчики — сумма голосов.
    Трассировка approved-кейса: TC-vid-029 (с нулевых счетчиков; инвариант
    ≤ 1 голоса на пару — ровно одна строка, test_reaction_put_toggle_move)."""
    video_id = _insert_video(db_path)
    url = f"/api/videos/{video_id}/reaction"
    assert client.put(url, json={"value": 1}).json()["likes"] == 1
    state = client2.put(url, json={"value": 1}).json()
    assert state == {"my_reaction": 1, "likes": 2, "dislikes": 0}
    # Второй снимает — счетчик ровно -1.
    assert client2.put(url, json={"value": 1}).json()["likes"] == 1


def test_reaction_invalid_value_422(client, db_path):
    """value не 1|-1 — 422; записи нет."""
    video_id = _insert_video(db_path)
    resp = client.put(f"/api/videos/{video_id}/reaction", json={"value": 0})
    assert resp.status_code == 422
    resp = client.put(f"/api/videos/{video_id}/reaction", json={})
    assert resp.status_code == 422
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM video_reactions").fetchone()[0] == 0
    finally:
        conn.close()


def test_reaction_video_not_found_404(client, db_path):
    resp = client.put("/api/videos/no-such/reaction", json={"value": 1})
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# Категории (Requirement «Категории видео — общий справочник с галереей»)
# --------------------------------------------------------------------------


def test_categories_list_is_gallery_catalog(client, db_path):
    """GET /api/videos/categories — SELECT из СУЩЕСТВУЮЩЕГО image_categories
    (RO; справочник галереи, фикстура создала «семья»/«дом»)."""
    resp = client.get("/api/videos/categories")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()["categories"]}
    assert names == {"семья", "дом"}


def test_upload_with_valid_category(client, db_path):
    """Scenario «Выбор при загрузке»: с категорией — видео имеет категорию;
    ответ 201 несет category_id; в списке — имя категории.
    Трассировка approved-кейса: TC-vid-033 (по умолчанию «Без категории»
    — test_upload_without_category_defaults_none)."""
    resp = _upload(client, category_id=10)
    assert resp.status_code == 201
    assert resp.json()["category_id"] == 10
    item = client.get("/api/videos").json()["videos"][0]
    assert item["category_id"] == 10
    assert item["category_name"] == "семья"
    assert item["likes"] == 0 and item["dislikes"] == 0 and item["my_reaction"] is None


def test_upload_without_category_defaults_none(client, db_path):
    """Scenario «Выбор при загрузке» (без выбора): NULL = «Без категории»
    (category_id None; пустая строка формы — то же)."""
    resp = _upload(client)
    assert resp.status_code == 201
    assert resp.json()["category_id"] is None
    item = client.get("/api/videos").json()["videos"][0]
    assert item["category_id"] is None
    assert item["category_name"] is None
    resp = _upload(client, category_id="")
    assert resp.status_code == 201
    assert resp.json()["category_id"] is None


def test_upload_unknown_category_422(client, db_path):
    """Валидация существования: несуществующий/нечисловой category_id —
    422, видео не создано (Scenario «Значения — только из справочника»).
    Трассировка approved-кейса: TC-vid-035 (контракт по решению ПМ в
    review-002, E-4: значение вне справочника галереи — 422; «work» из
    задач в справочнике отсутствует — test_categories_list_is_gallery_catalog)."""
    before = len(client.get("/api/videos").json()["videos"])
    for bad in ("999", "abc"):
        resp = _upload(client, category_id=bad)
        assert resp.status_code == 422
    assert len(client.get("/api/videos").json()["videos"]) == before


def test_list_filter_by_category(client, db_path):
    """Scenario «Фильтр по категории в списке»: по id — только видео
    категории; none — только «Без категории»; без фильтра — все.
    Трассировка approved-кейса: TC-vid-034 (UI-фильтр тулбара —
    tests/web/test_video_social_ui.py, TC-vid-104)."""
    _insert_video(db_path, category_id=10)
    _insert_video(db_path, category_id=20)
    _insert_video(db_path, category_id=None)

    by_id = client.get("/api/videos?category=10").json()["videos"]
    assert [v["category_name"] for v in by_id] == ["семья"]
    by_none = client.get("/api/videos?category=none").json()["videos"]
    assert len(by_none) == 1 and by_none[0]["category_id"] is None
    everything = client.get("/api/videos").json()["videos"]
    assert len(everything) == 3
    # Неверное значение фильтра — 422.
    assert client.get("/api/videos?category=bogus").status_code == 422


# --------------------------------------------------------------------------
# TC-vid-032 — гонка реакций: уникальность голоса при конкурентных PUT
# --------------------------------------------------------------------------


def test_reaction_race_single_vote(client, db_path):
    """TC-vid-032 (Scenario «Постановка лайка (конкурентность)»): два
    параллельных PUT reaction (value 1 и -1) с одной сессии — у
    пользователя ровно один голос (суммарные счетчики изменились не
    более чем на 1), двойного голоса нет; 5 повторов гонки."""
    video_id = _insert_video(db_path)
    url = f"/api/videos/{video_id}/reaction"

    def put(value, results, i):
        results[i] = client.put(url, json={"value": value})

    for race_no in range(5):
        results = {}
        threads = [
            threading.Thread(target=put, args=(v, results, i))
            for i, v in enumerate((1, -1))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        responses = [results[0].json(), results[1].json()]
        assert all(r["my_reaction"] in (1, -1, None) for r in responses)
        state = responses[-1]
        assert state["likes"] + state["dislikes"] <= 1, (race_no, responses)

        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT user_id, value FROM video_reactions WHERE video_id = ?",
                (video_id,),
            ).fetchall()
        finally:
            conn.close()
        # Инвариант: у owner ровно одна строка (PK), суммарно ≤ 1 голоса.
        assert len(rows) <= 1, (race_no, rows)
        assert sum(abs(v) for _u, v in rows) <= 1, (race_no, rows)


def test_delete_video_cascades_social(client, db_path):
    """CASCADE: удаление видео чистит его комментарии и реакции
    (FK ON DELETE CASCADE, foreign_keys=ON в db.get_connection)."""
    video_id = _insert_video(db_path)
    assert (
        client.post(f"/api/videos/{video_id}/comments", json={"text": "текст"}).status_code
        == 201
    )
    assert (
        client.put(f"/api/videos/{video_id}/reaction", json={"value": 1}).status_code
        == 200
    )
    assert client.delete(f"/api/videos/{video_id}").status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM video_comments").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM video_reactions").fetchone()[0] == 0
    finally:
        conn.close()
