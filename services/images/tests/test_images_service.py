"""Юнит-тесты images-сервиса (задачи 1.2/1.6, add-gallery-service).

По конвенции services/search/tests: TestClient над app.main, БД —
временная sqlite в фикстуре (EKOTOV_WIKI_DB_PATH на время теста); для
images дополнительно том файлов — временный каталог
(EKOTOV_WIKI_IMAGES_DIR на время теста).

Запуск (из services/images/): python3 -m pytest tests/ -v

Схема БД — дословно design.md §2 (6 таблиц gallery + users/sessions ядра).
Миграцию ядра (задача 1.3) тесты не исполняют — таблицы создаются
фикстурой по той же схеме (сверка — задача 1.3/ревью).

Трассировка: сценарии дельты specs/gallery (FR-79…FR-82); новые проверки
задачи 1.6 (Э-3, tags в списке) — TC-gal-104/105 (нумерация по образцу
TC-openapi-203+: TC-ID в docstring юнитов сервиса, 1 сценарий = 1 тест).
"""

import io
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

AUTH = {"error": "unauthorized"}

# --------------------------------------------------------------------------
# Фикстуры: временная БД (схема design §2) + временный том + клиенты
# --------------------------------------------------------------------------

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
-- ===== Таблицы gallery (design §2 — дословно; создает миграция 1.3) =====
CREATE TABLE image_categories (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);
CREATE TABLE images (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  thumb_name TEXT NOT NULL,
  original_name TEXT NOT NULL,
  mime TEXT NOT NULL,
  size INTEGER NOT NULL,
  category_id INTEGER REFERENCES image_categories(id),
  uploaded_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_images_category ON images(category_id);
CREATE INDEX idx_images_created_at ON images(created_at);
CREATE TABLE gallery_tags (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);
CREATE TABLE image_tags (
  image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES gallery_tags(id),
  PRIMARY KEY (image_id, tag_id)
);
CREATE INDEX idx_image_tags_tag ON image_tags(tag_id);
CREATE TABLE image_reactions (
  image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  value INTEGER NOT NULL CHECK (value IN (1, -1)),
  PRIMARY KEY (image_id, user_id)
);
CREATE TABLE image_comments (
  id INTEGER PRIMARY KEY,
  image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_image_comments_image ON image_comments(image_id);
"""


def _png_bytes(size=(1200, 900), color=(200, 60, 60)) -> bytes:
    """Валидный PNG (по умолчанию длинная сторона 1200 — проверка превью)."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Временная sqlite с users/sessions; env сервиса на нее переключен."""
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
def images_dir(tmp_path, monkeypatch):
    """Временный том изображений (env EKOTOV_WIKI_IMAGES_DIR)."""
    d = str(tmp_path / "images-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_IMAGES_DIR", d)
    return d


@pytest.fixture()
def anon_client(db_path, images_dir):
    with TestClient(app) as client:
        yield client


def _client(db_path, images_dir, token):
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, token)
        yield client


@pytest.fixture()
def client(db_path, images_dir):
    """Клиент-owner (сессия test-token-1)."""
    yield from _client(db_path, images_dir, "test-token-1")


@pytest.fixture()
def client2(db_path, images_dir):
    """Клиент-PE (сессия test-token-2) — сценарии второй стороны."""
    yield from _client(db_path, images_dir, "test-token-2")


def _upload(client, name="test.png", content=None, category=None, tags=None):
    data = {}
    if category is not None:
        data["category"] = category
    if tags is not None:
        data["tags"] = tags
    return client.post(
        "/api/images",
        files={"file": (name, content if content is not None else _png_bytes(), "image/png")},
        data=data,
    )


# --------------------------------------------------------------------------
# 401 без сессии (scenario «Негативный: без сессии API недоступен»)
# --------------------------------------------------------------------------


def test_health_no_session(anon_client):
    """GET /api/health без сессии → 200 (exempt, паритет search)."""
    resp = anon_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_endpoints_require_session(anon_client):
    """Все эндпоинты изображений без сессии → 401 {"error": "unauthorized"}."""
    assert anon_client.get("/api/images").status_code == 401
    assert anon_client.post("/api/images").status_code == 401
    assert anon_client.get("/api/images/1").status_code == 401
    assert anon_client.put("/api/images/1/like").status_code == 401
    assert anon_client.delete("/api/images/1/like").status_code == 401
    assert anon_client.put("/api/images/1/dislike").status_code == 401
    assert anon_client.delete("/api/images/1/dislike").status_code == 401
    assert anon_client.post("/api/images/1/comments").status_code == 401
    assert anon_client.delete("/api/images/1/comments/1").status_code == 401
    assert anon_client.get("/openapi.json").status_code == 401
    for r in anon_client.get("/api/images").status_code,:
        pass
    assert anon_client.get("/api/images").json() == AUTH


def test_openapi_paths(client):
    """Схема (под сессией) содержит ровно маршруты design §3."""
    paths = set(client.get("/openapi.json").json()["paths"].keys())
    assert paths == {
        "/api/images",
        "/api/images/{image_id}",
        "/api/images/{image_id}/like",
        "/api/images/{image_id}/dislike",
        "/api/images/{image_id}/comments",
        "/api/images/{image_id}/comments/{comment_id}",
        "/api/health",
    }


# --------------------------------------------------------------------------
# Загрузка (FR-79; scenarios «Валидная загрузка», «Негативные»)
# --------------------------------------------------------------------------


def test_upload_png_happy_path(client, images_dir):
    """Валидный PNG → 201; оригинал+превью в томе, метаданные в БД; превью ≤800px."""
    resp = _upload(client, category="семья", tags="лето, дача")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # Файлы в томе (не BLOB), имена генерирует сервер.
    orig = os.path.join(images_dir, body["filename"])
    thumb = os.path.join(images_dir, body["thumb_name"])
    assert os.path.isfile(orig) and os.path.isfile(thumb)
    assert body["filename"].endswith(".png")
    assert body["thumb_name"].endswith(".jpg")
    assert body["original_name"] == "test.png"
    assert body["url"] == f"/images/{body['filename']}"

    # Превью — JPEG с длинной стороной ≤ 800.
    with Image.open(thumb) as im:
        assert im.format == "JPEG"
        assert max(im.size) <= 800

    # Метаданные в БД.
    conn = sqlite3.connect(db_path := os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        row = conn.execute(
            "SELECT mime, size, category_id, uploaded_by FROM images WHERE id = ?",
            (body["id"],),
        ).fetchone()
        assert row[0] == "image/png"
        assert row[2] is not None  # категория «семья» создана
        assert row[3] == 1
        tags = conn.execute(
            "SELECT g.name FROM image_tags it JOIN gallery_tags g ON g.id = it.tag_id"
            " WHERE it.image_id = ? ORDER BY g.name",
            (body["id"],),
        ).fetchall()
        assert [t[0] for t in tags] == ["дача", "лето"]
    finally:
        conn.close()


def test_upload_small_image_no_upscale(client, images_dir):
    """Изображение меньше 800px сохраняется без апскейла (длинная сторона та же)."""
    resp = _upload(client, content=_png_bytes(size=(400, 300)))
    assert resp.status_code == 201
    thumb = os.path.join(images_dir, resp.json()["thumb_name"])
    with Image.open(thumb) as im:
        assert max(im.size) <= 400


def test_upload_jpeg_and_gif_and_webp(client):
    """Остальные три разрешенных типа принимаются; mime по magic-байтам."""
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (10, 120, 200)).save(buf, "JPEG")
    assert _upload(client, name="a.jpg", content=buf.getvalue()).status_code == 201
    assert _upload(client, name="a.gif", content=_gif_bytes()).status_code == 201
    assert _upload(client, name="a.webp", content=_webp_bytes()).status_code == 201
    listing = client.get("/api/images").json()["images"]
    mimes = {i["mime"] for i in listing}
    # png из предыдущих тестов изолирован (своя БД) — здесь ровно 3 записи.
    assert mimes == {"image/jpeg", "image/gif", "image/webp"}
    assert len(listing) == 3


def _gif_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("P", (50, 50), 3).save(buf, "GIF")
    return buf.getvalue()


def _webp_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), (5, 5, 5)).save(buf, "WEBP")
    return buf.getvalue()


def test_upload_too_large_422(client, images_dir, db_path):
    """Файл > 10 МБ → 422; в томе и БД ничего не сохранено (до записи)."""
    png = _png_bytes()
    big = png + b"\0" * (10 * 1024 * 1024 + 1)
    resp = _upload(client, content=big)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"
    assert os.listdir(images_dir) == []
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM images").fetchone()[0] == 0
    finally:
        conn.close()


def test_upload_bad_type_422(client, images_dir, db_path):
    """PDF, переименованный в .jpg → 422 (проверка по содержимому)."""
    pdf = b"%PDF-1.4 fake pdf content" + b"\0" * 1024
    resp = _upload(client, name="photo.jpg", content=pdf)
    assert resp.status_code == 422
    assert os.listdir(images_dir) == []
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM images").fetchone()[0] == 0
    finally:
        conn.close()


def test_upload_corrupted_image_422(client, images_dir):
    """Сигнатура PNG есть, содержимое битое → 422 (не сохранен)."""
    broken = b"\x89PNG\r\n\x1a\n" + b"garbage" * 100
    assert _upload(client, content=broken).status_code == 422
    assert os.listdir(images_dir) == []


def test_upload_no_file_422(client):
    """multipart без файла → 422 (валидация FastAPI, форма ядра)."""
    resp = client.post("/api/images", data={})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"


def test_upload_unknown_category_id_422(client):
    """category=<несуществующий id> → 422; файл не сохранен не требуется —
    запись не создается, но валидация справочника срабатывает до файлов."""
    resp = _upload(client, category="999")
    assert resp.status_code == 422


def test_upload_without_category_tags(client):
    """Загрузка без категории и тегов допустима (scenario спеки)."""
    resp = _upload(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["category_id"] is None
    assert body["tags"] == []
    # Видна в общем списке.
    assert [i["id"] for i in client.get("/api/images").json()["images"]] == [body["id"]]


def test_upload_reuses_existing_category_and_tag(client):
    """Существующие категория/тег переиспользуются (не дублируются)."""
    r1 = _upload(client, category="семья", tags="лето")
    assert r1.status_code == 201
    r2 = _upload(client, category="семья", tags="лето,зима")
    assert r2.status_code == 201
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        cats = conn.execute("SELECT count(*) FROM image_categories").fetchone()[0]
        tags = conn.execute("SELECT count(*) FROM gallery_tags").fetchone()[0]
        assert cats == 1  # «семья» одна
        assert tags == 2  # лето, зима
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Список и фильтры (FR-80)
# --------------------------------------------------------------------------


@pytest.fixture()
def seeded_gallery(client):
    """Три изображения: семья/лето, семья/зима, дом/лето (+ created_at)."""
    ids = []
    # png_bytes различаются цветом, чтобы размеры/файлы не совпадали.
    for i, (cat, tags) in enumerate(
        [("семья", "лето"), ("семья", "зима"), ("дом", "лето")]
    ):
        r = _upload(client, content=_png_bytes(color=(i * 50, 100, 100)),
                    category=cat, tags=tags)
        assert r.status_code == 201
        ids.append(r.json()["id"])
    # Принудительно разносим created_at DESC-порядок (uploads в одну секунду).
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        for n, image_id in enumerate(ids):
            conn.execute(
                "UPDATE images SET created_at = ? WHERE id = ?",
                (f"2026-10-0{n + 1}T00:00:00+00:00", image_id),
            )
        conn.commit()
    finally:
        conn.close()
    return ids


def test_list_order_and_fields(client, seeded_gallery):
    """Пустой фильтр = все; сортировка created_at DESC; счетчики и мой голос."""
    body = client.get("/api/images").json()["images"]
    assert [i["id"] for i in body] == [seeded_gallery[2], seeded_gallery[1], seeded_gallery[0]]
    item = body[-1]
    assert set(item.keys()) == {
        "id", "filename", "thumb_name", "original_name", "mime", "size",
        "uploaded_by", "created_at", "category", "tags", "likes", "dislikes",
        "comments", "my_reaction", "url", "thumb_url",
    }
    assert item["category"] == "семья"
    assert item["likes"] == 0 and item["dislikes"] == 0 and item["comments"] == 0
    assert item["my_reaction"] is None


def test_list_filters_combine(client, seeded_gallery):
    """category+tag комбинируются (AND); по отдельности — свои множества."""
    ids = seeded_gallery  # [семья/лето, семья/зима, дом/лето]
    # category=семья → 1, 2.
    r = client.get("/api/images", params={"category": "семья"})
    assert {i["id"] for i in r.json()["images"]} == {ids[0], ids[1]}
    # tag=лето → 1, 3.
    r = client.get("/api/images", params={"tag": "лето"})
    assert {i["id"] for i in r.json()["images"]} == {ids[0], ids[2]}
    # Комбинация семья+лето → только 1.
    r = client.get("/api/images", params={"category": "семья", "tag": "лето"})
    assert [i["id"] for i in r.json()["images"]] == [ids[0]]
    # Несуществующие значения → пустой список.
    r = client.get("/api/images", params={"category": "нет"})
    assert r.status_code == 200 and r.json()["images"] == []


def test_list_shows_my_reaction(client, client2, seeded_gallery):
    """«Мой голос» в списке — персональный (у owner лайк, у PE — нет)."""
    target = seeded_gallery[0]
    assert client.put(f"/api/images/{target}/like").status_code == 200
    mine = {i["id"]: i["my_reaction"] for i in client.get("/api/images").json()["images"]}
    theirs = {i["id"]: i["my_reaction"] for i in client2.get("/api/images").json()["images"]}
    assert mine[target] == 1
    assert theirs[target] is None


def test_list_includes_tags_of_each_image(client):
    """TC-gal-104 (1.6, Э-3): список возвращает теги каждого изображения —
    upload с 2 тегами → элемент списка содержит оба (паритет с detail)."""
    r = _upload(client, category="семья", tags="лето, дача")
    assert r.status_code == 201
    image_id = r.json()["id"]
    items = client.get("/api/images").json()["images"]
    assert [i["id"] for i in items] == [image_id]
    # Порядок тегов — алфавитный (agregat image_tags+gallery_tags).
    assert items[0]["tags"] == ["дача", "лето"]
    # Паритет с detail-ответом (тот же SELECT).
    detail = client.get(f"/api/images/{image_id}").json()
    assert detail["tags"] == items[0]["tags"]
    # Фильтр по одному из тегов не меняет состав поля tags.
    r = client.get("/api/images", params={"tag": "лето"})
    assert r.json()["images"][0]["tags"] == ["дача", "лето"]


def test_list_tags_empty_when_no_tags(client):
    """TC-gal-105 (1.6, Э-3): изображение без тегов — tags: [] в списке
    (пустой массив, не null/отсутствующее поле) — и в detail."""
    r = _upload(client)
    assert r.status_code == 201
    image_id = r.json()["id"]
    items = client.get("/api/images").json()["images"]
    assert items[0]["id"] == image_id
    assert items[0]["tags"] == []
    assert client.get(f"/api/images/{image_id}").json()["tags"] == []


# --------------------------------------------------------------------------
# Получение одного изображения
# --------------------------------------------------------------------------


def test_get_image_details(client, client2, seeded_gallery):
    """GET /api/images/{id} — метаданные + реакции + комментарии (автор)."""
    target = seeded_gallery[0]
    client.put(f"/api/images/{target}/like")
    client2.post(f"/api/images/{target}/comments", json={"body": "Отличный кадр"})
    body = client.get(f"/api/images/{target}").json()
    assert body["id"] == target
    assert body["likes"] == 1
    assert body["my_reaction"] == 1
    assert len(body["comments"]) == 1
    c = body["comments"][0]
    assert c["body"] == "Отличный кадр"
    assert c["author"] == "PE"  # display_name
    assert c["created_at"]


def test_get_missing_image_404(client):
    assert client.get("/api/images/9999").status_code == 404
    assert client.put("/api/images/9999/like").status_code == 404
    assert client.post("/api/images/9999/comments", json={"body": "x"}).status_code == 404


# --------------------------------------------------------------------------
# Реакции (FR-81): один голос, смена, снятие, негатив 401
# --------------------------------------------------------------------------


def test_reaction_flow(client, client2, seeded_gallery):
    """Полный сценарий FR-81: постановка → смена → снятие; счетчики точные."""
    img = seeded_gallery[1]
    # Предыстория: owner уже ставил дизлайк ранее (шаг 2), PE — нет.
    # (состояние к шагу 4: 0 лайков / 1 дизлайк owner)
    assert client2.put(f"/api/images/{img}/dislike").json() == {
        "likes": 0, "dislikes": 1, "my_reaction": -1,
    }

    # 1) owner ставит лайк → 1/1.
    r = client.put(f"/api/images/{img}/like")
    assert r.status_code == 200
    assert r.json() == {"likes": 1, "dislikes": 1, "my_reaction": 1}

    # 2) Смена голоса: owner ставит дизлайк → лайк снят, дизлайк учтен (ровно один голос).
    r = client.put(f"/api/images/{img}/dislike")
    assert r.json() == {"likes": 0, "dislikes": 2, "my_reaction": -1}

    # 3) Повторное действие того же знака снимает голос.
    r = client.put(f"/api/images/{img}/dislike")
    assert r.json() == {"likes": 0, "dislikes": 1, "my_reaction": None}

    # 4) Явное снятие: PE переносит голос на лайк и снимает DELETE-ом.
    #    К этому шагу голос owner снят (шаг 3), у PE — дизлайк; его перенос
    #    на лайк и удаление оставляют 0/0.
    assert client2.put(f"/api/images/{img}/like").json() == {
        "likes": 1, "dislikes": 0, "my_reaction": 1,
    }
    r = client2.delete(f"/api/images/{img}/like")
    assert r.status_code == 200
    assert r.json() == {"likes": 0, "dislikes": 0, "my_reaction": None}

    # 5) DELETE противоположного знака голос не трогает.
    client.put(f"/api/images/{img}/like")
    client2.put(f"/api/images/{img}/dislike")
    r = client.delete(f"/api/images/{img}/dislike")
    assert r.json() == {"likes": 1, "dislikes": 1, "my_reaction": 1}

    # В БД ровно по одной строке голоса на пользователя (PK-инвариант).
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        n = conn.execute(
            "SELECT count(*) FROM image_reactions WHERE image_id = ?", (img,)
        ).fetchone()[0]
        assert n == 2  # owner + PE
    finally:
        conn.close()


def test_reaction_no_session_401(anon_client, seeded_gallery):
    """Scenario «Негативный: без сессии реакция недоступна» → 401."""
    img = seeded_gallery[0]
    assert anon_client.put(f"/api/images/{img}/like").status_code == 401
    # Голос не учтен.
    assert client_seeded_reaction_state(anon_client, img)["likes"] == 0


def client_seeded_reaction_state(anon_client, img):
    import sqlite3
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        return {
            "likes": conn.execute(
                "SELECT count(*) FROM image_reactions WHERE image_id=? AND value=1",
                (img,)).fetchone()[0]
        }
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Комментарии (FR-82)
# --------------------------------------------------------------------------


def test_comment_add_and_visible_to_both(client, client2, seeded_gallery):
    """Добавление; оба пользователя видят текст/автора/время."""
    img = seeded_gallery[0]
    r = client.post(f"/api/images/{img}/comments", json={"body": "Отличный кадр"})
    assert r.status_code == 201
    c = r.json()
    assert c["body"] == "Отличный кадр"
    assert c["author"] == "Owner"
    # Виден второму пользователю.
    body = client2.get(f"/api/images/{img}").json()
    assert [x["id"] for x in body["comments"]] == [c["id"]]


def test_comment_empty_422(client, seeded_gallery):
    """Scenario «Негативный: пустой комментарий» — пробелы тоже 422."""
    img = seeded_gallery[0]
    for payload in ({"body": ""}, {"body": "   "}, {}, {"body": None}):
        r = client.post(f"/api/images/{img}/comments", json=payload)
        assert r.status_code == 422, payload
    conn = sqlite3.connect(os.environ["EKOTOV_WIKI_DB_PATH"])
    try:
        assert conn.execute("SELECT count(*) FROM image_comments").fetchone()[0] == 0
    finally:
        conn.close()


def test_comment_delete_own(client, seeded_gallery):
    img = seeded_gallery[0]
    cid = client.post(f"/api/images/{img}/comments", json={"body": "мой"}).json()["id"]
    r = client.delete(f"/api/images/{img}/comments/{cid}")
    assert r.status_code == 200
    body = client.get(f"/api/images/{img}").json()
    assert body["comments"] == []


def test_comment_delete_foreign_403(client, client2, seeded_gallery):
    """Scenario «Негативный: чужой комментарий удалить нельзя» → 403; остался."""
    img = seeded_gallery[0]
    cid = client2.post(f"/api/images/{img}/comments", json={"body": "чужой"}).json()["id"]
    r = client.delete(f"/api/images/{img}/comments/{cid}")
    assert r.status_code == 403
    body = client.get(f"/api/images/{img}").json()
    assert [x["id"] for x in body["comments"]] == [cid]


def test_comment_delete_missing_404(client, seeded_gallery):
    img = seeded_gallery[0]
    assert client.delete(f"/api/images/{img}/comments/9999").status_code == 404


# --------------------------------------------------------------------------
# Границы RW-профиля (спека services: «Границы записи»)
# --------------------------------------------------------------------------


def test_core_tables_untouched(client, client2, db_path, seeded_gallery):
    """После нагрузочной последовательности таблицы ядра не изменены."""
    conn = sqlite3.connect(db_path)
    try:
        before = {
            t: conn.execute(f"SELECT * FROM {t}").fetchall()
            for t in ("users", "sessions")
        }
    finally:
        conn.close()

    img = seeded_gallery[0]
    client.put(f"/api/images/{img}/like")
    client2.post(f"/api/images/{img}/comments", json={"body": "ok"})
    _upload(client, tags="новыйтег")

    conn = sqlite3.connect(db_path)
    try:
        for t, rows in before.items():
            assert conn.execute(f"SELECT * FROM {t}").fetchall() == rows, t
        # users читался (display_name в комментариях) — но не менялся: above.
    finally:
        conn.close()
