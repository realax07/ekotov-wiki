"""Тесты video-сервиса (задача 1.6, video-hosting волна 1, кусок A).

По конвенции services/images/tests: TestClient над app.main, БД —
временная sqlite в фикстуре (EKOTOV_WIKI_DB_PATH на время теста); том
файлов — временный каталог (EKOTOV_WIKI_VIDEOS_DIR на время теста).

Запуск (из services/video/): python3 -m pytest tests/ -v
Без сети и внешних сервисов: фикстуры поднимают схему в tmp, клиент —
in-process TestClient.

Схема БД — дословно DDL миграции backend/app/migrate_video.py
(tasks 1.1, sdd §4; кусок A — без category_id, ее добавит 2.1).
Миграцию ядра тесты не исполняют — таблица создается фикстурой по той
же схеме (сверка двух представлений — задача 1.1).

Трассировка: сценарии дельты specs/video-service (кусок A) —
Requirement/Scenario указаны в docstring каждого теста; нумерация
TC-vid-NNN по образцу services/images/tests (TC-gal-NNN):
TC-vid-001…004 — 401 без сессии/authcheck/openapi (NFR-36);
TC-vid-010…016 — загрузка (happy path, 422: 501 МБ / pre-check /
обрыв тела / пустое тело / без файла / path traversal);
TC-vid-020…024 — playback/превью (200/409/404);
TC-vid-030…034 — список и удаление (200/404, равноправие, RW-профиль).
"""

import io
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware import SESSION_COOKIE_NAME

AUTH = {"error": "unauthorized"}

# ОВ-1: лимит 500 МБ (паритет app/videos.py — МиБ).
LIMIT = 500 * 1024 * 1024

# Схема: users/sessions ядра + image_categories галереи (общий справочник,
# SELECT у сервиса) + video_videos (+category_id — кусок D) + социальный
# слой video_comments/video_reactions — DDL миграции migrate_video
# (дословно; tasks 1.1 + 2.1, sdd §4).
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
        # Общий справочник галереи (кусок D): две категории.
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
    """Временный том видео (env EKOTOV_WIKI_VIDEOS_DIR)."""
    d = str(tmp_path / "videos-data")
    os.makedirs(d, exist_ok=True)
    monkeypatch.setenv("EKOTOV_WIKI_VIDEOS_DIR", d)
    return d


@pytest.fixture()
def anon_client(db_path, videos_dir):
    with TestClient(app) as client:
        yield client


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
    """Клиент-PE (сессия test-token-2) — паритет второго пользователя."""
    yield from _client(db_path, videos_dir, "test-token-2")


def _upload(client, name="clip.mkv", content=b"fake-video-bytes-0123456789",
            content_type="video/x-matroska"):
    return client.post(
        "/api/videos",
        files={"file": (name, content, content_type)},
    )


def _insert_row(db_path, video_id=None, status="ready", filename="row.mkv"):
    """Прямая вставка записи (для 409-веток и мимики чужих статусов)."""
    video_id = video_id or uuid.uuid4().hex
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO video_videos (id, filename, status, size_bytes, mime,"
            " uploaded_by, created_at, convert_attempts)"
            " VALUES (?, ?, ?, 10, 'video/x-matroska', 1, ?, 0)",
            (video_id, filename, status, "2026-10-17T00:00:00+00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    return video_id


# --------------------------------------------------------------------------
# 401 без сессии (Scenario «API без сессии», NFR-36) + authcheck
# --------------------------------------------------------------------------


def test_health_no_session(anon_client):
    """GET /api/health без сессии → 200 (exempt, паритет images/search)."""
    resp = anon_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_endpoints_require_session(anon_client):
    """Все эндпоинты видео без сессии → 401 {"error": "unauthorized"}."""
    assert anon_client.get("/api/videos").status_code == 401
    assert anon_client.post("/api/videos").status_code == 401
    assert anon_client.delete("/api/videos/" + uuid.uuid4().hex).status_code == 401
    assert anon_client.get(f"/api/videos/{uuid.uuid4().hex}/file").status_code == 401
    assert anon_client.get(f"/api/videos/{uuid.uuid4().hex}/preview").status_code == 401
    # Стык auth_request тоже требует сессии (nginx решает по 401).
    assert anon_client.get("/api/videos/authcheck").status_code == 401
    assert anon_client.get("/api/videos/authcheck").json() == AUTH
    # Схема не публикуется без сессии (паритет images).
    assert anon_client.get("/openapi.json").status_code == 401
    assert anon_client.get("/api/videos").json() == AUTH


def test_authcheck_with_session(client):
    """GET /api/videos/authcheck с валидной сессией → 200 {} (стык
    auth_request, sdd §3; эндпоинт — без чтения video_videos)."""
    resp = client.get("/api/videos/authcheck")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_openapi_paths(client):
    """Схема (под сессией) содержит ровно маршруты кусков A + D (sdd §3;
    D-эндпоинты добавлены волной 2 — comments/reaction/categories)."""
    paths = set(client.get("/openapi.json").json()["paths"].keys())
    assert paths == {
        "/api/videos",
        "/api/videos/{video_id}",
        "/api/videos/{video_id}/file",
        "/api/videos/{video_id}/preview",
        "/api/videos/{video_id}/comments",
        "/api/videos/{video_id}/comments/{comment_id}",
        "/api/videos/{video_id}/reaction",
        "/api/videos/categories",
        "/api/videos/authcheck",
        "/api/health",
    }


# --------------------------------------------------------------------------
# Загрузка (Scenario «Успешная загрузка в пределах лимита», «Отказ при
# превышении лимита»; Requirement «Загрузка видео — любой формат, ≤ 500 МБ»)
# --------------------------------------------------------------------------


def test_upload_happy_path(client, videos_dir, db_path):
    """Любой формат (mkv) → 201; файл в томе <id>/original.<ext> (НЕ BLOB,
    НЕ в репо), метаданные в БД (Scenario «Файлы в томе, метаданные в БД»).
    Кусок B: статус «uploaded» (sdd §3) — воркер (волна 3) переводит в
    converting/ready; в этих тестах воркер выключен (conftest)."""
    content = b"\x1aE\xdf\xa3" + b"matroska-fake-payload" * 10
    resp = _upload(client, name="обзор дома.mkv", content=content)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    video_id = body["id"]

    # id — uuid (имя каталога в томе), имя пользователя в путях НЕ участвует.
    assert video_id != "обзор дома.mkv"
    assert len(video_id) == 32 and int(video_id, 16) >= 0
    assert body["filename"] == "обзор дома.mkv"
    assert body["status"] == "uploaded"
    assert body["size"] == len(content)

    # Файл в томе: videos-data/<id>/original.mkv, байты как есть.
    stored = os.path.join(videos_dir, video_id, "original.mkv")
    assert os.path.isfile(stored)
    with open(stored, "rb") as f:
        assert f.read() == content

    # Метаданные в БД.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT filename, status, size_bytes, mime, uploaded_by,"
            " convert_attempts FROM video_videos WHERE id = ?",
            (video_id,),
        ).fetchone()
        assert row[0] == "обзор дома.mkv"
        assert row[1] == "uploaded"
        assert row[2] == len(content)
        assert row[3] == "video/x-matroska"
        assert row[4] == 1
        assert row[5] == 0
    finally:
        conn.close()


def test_upload_list_urls(client, videos_dir):
    """Список: file_url — nginx-путь /videos/<id>/original.<ext>
    (playback-урол), preview_url — API-эндпоинт (sdd §3, design §5)."""
    resp = _upload(client, name="clip.webm", content=b"webm-bytes",
                   content_type="video/webm")
    assert resp.status_code == 201
    items = client.get("/api/videos").json()["videos"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == resp.json()["id"]
    assert item["filename"] == "clip.webm"
    assert item["status"] == "uploaded"
    assert item["size_bytes"] == len(b"webm-bytes")
    assert item["file_url"] == f"/videos/{item['id']}/original.webm"
    assert item["preview_url"] == f"/api/videos/{item['id']}/preview"
    assert item["created_at"]


def test_upload_too_large_422_no_volume_dir(client, videos_dir, db_path):
    """501 МБ → 422 «файл больше 500 МБ»; каталог в томе НЕ появился,
    записи в БД нет (Scenario «Отказ при превышении лимита»)."""
    big = b"\0" * (LIMIT + 1024 * 1024)  # 501 МиБ нулей
    resp = _upload(client, name="big.mkv", content=big)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation error"
    assert isinstance(body["details"], list) and body["details"]
    # Том пуст, БД пуста: диск под видео не расходован.
    assert os.listdir(videos_dir) == []
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM video_videos").fetchone()[0] == 0
    finally:
        conn.close()


def test_upload_precheck_rejects_huge_content_length(client, videos_dir):
    """Content-Length pre-check: тело заведомо больше лимита+обвязки —
    422 еще до чтения (design §4); диск тома не затронут."""
    from app.videos import MULTIPART_OVERHEAD_BYTES, check_content_length

    with pytest.raises(Exception):
        check_content_length(LIMIT + MULTIPART_OVERHEAD_BYTES + 1)
    # В границах обвязки pre-check пропускает (лимит считает счетчик).
    check_content_length(LIMIT + MULTIPART_OVERHEAD_BYTES - 1)
    assert os.listdir(videos_dir) == []


def test_upload_aborted_body_leaves_nothing(client, videos_dir):
    """Обрыв тела при чтении → 422, каталог в томе не создается
    (задача 1.6: «обрыв тела»; проверка потокового счетчика)."""
    import asyncio

    from app.videos import UploadAborted, spool_to_temp

    class BrokenFile:
        def __init__(self):
            self._reads = 0

        async def read(self, n):
            self._reads += 1
            if self._reads == 1:
                return b"partial-chunk"
            raise ConnectionError("client disconnected")

    async def run():
        import tempfile

        spool = tempfile.NamedTemporaryFile(delete=False, suffix=".t")
        try:
            with pytest.raises(UploadAborted):
                await spool_to_temp(BrokenFile(), spool)
        finally:
            spool.close()
            if os.path.exists(spool.name):
                os.remove(spool.name)

    asyncio.run(run())
    assert os.listdir(videos_dir) == []


def test_upload_empty_body_422(client, videos_dir, db_path):
    """Пустое тело multipart (файл 0 байт) → 422; в томе и БД ничего."""
    resp = _upload(client, name="empty.mkv", content=b"")
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"
    assert os.listdir(videos_dir) == []
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM video_videos").fetchone()[0] == 0
    finally:
        conn.close()


def test_upload_no_file_422(client):
    """multipart без файла → 422 (валидация FastAPI, форма ядра)."""
    resp = client.post("/api/videos", data={})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"


def test_upload_avoids_path_traversal(client, videos_dir):
    """Имя пользователя со слэшами/«..» не влияет на пути: каталог —
    uuid, расширение нормализовано (design §8, path traversal)."""
    resp = _upload(client, name="../../etc/passwd.mkv", content=b"traversal")
    assert resp.status_code == 201
    video_id = resp.json()["id"]
    # В томе — ровно один каталог-uuid, внутри original.mkv.
    assert os.listdir(videos_dir) == [video_id]
    assert os.path.isfile(os.path.join(videos_dir, video_id, "original.mkv"))


# --------------------------------------------------------------------------
# Playback и превью (Requirements «Список видео и playback»)
# --------------------------------------------------------------------------


def test_file_served_for_ready(client, videos_dir, db_path):
    """«готово» → 200, байты как есть (формат любой); чужие статусы
    недоступны (Scenario «Playback готового видео»). Кусок B: ready
    ставит воркер — тест ставит его напрямую (воркер выключен)."""
    content = b"mp4-ish-bytes"
    video_id = _upload(client, name="clip.mp4", content=b"ignored").json()["id"]
    # Перезаписываем файл содержимым, чтобы сверить отдачу 1:1.
    with open(os.path.join(videos_dir, video_id, "original.mp4"), "wb") as f:
        f.write(content)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE video_videos SET status = 'ready' WHERE id = ?", (video_id,)
        )
        conn.commit()
    finally:
        conn.close()
    resp = client.get(f"/api/videos/{video_id}/file")
    assert resp.status_code == 200
    assert resp.content == content


def test_file_409_not_ready(client, videos_dir, db_path):
    """Не «готово» → 409 (плеер не запускается, Scenario «Не готовое
    видео не проигрывается»); запись есть — 409, не 404."""
    video_id = _insert_row(db_path, status="converting")
    d = os.path.join(videos_dir, video_id)
    os.makedirs(d)
    with open(os.path.join(d, "original.mkv"), "wb") as f:
        f.write(b"x")
    for status in ("uploaded", "converting", "error"):
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "UPDATE video_videos SET status = ? WHERE id = ?", (status, video_id)
            )
            conn.commit()
        finally:
            conn.close()
        assert client.get(f"/api/videos/{video_id}/file").status_code == 409
        assert client.get(f"/api/videos/{video_id}/preview").status_code == 409


def test_preview_409_until_frame_exists(client):
    """Превью: до появления preview.jpg — 409 (плейсхолдер по макету;
    кадр генерит конвертер — кусок B)."""
    video_id = _upload(client).json()["id"]
    assert client.get(f"/api/videos/{video_id}/preview").status_code == 409


def test_file_and_preview_404_missing(client):
    """Несуществующее видео → 404 на file/preview/delete."""
    missing = uuid.uuid4().hex
    assert client.get(f"/api/videos/{missing}/file").status_code == 404
    assert client.get(f"/api/videos/{missing}/preview").status_code == 404
    assert client.delete(f"/api/videos/{missing}").status_code == 404


def test_file_404_on_malformed_id(client):
    """Невалидный id (не uuid) → 404, путь не строится (path traversal)."""
    assert client.get("/api/videos/not-a-uuid/file").status_code == 404
    assert client.get("/api/videos/../../etc/file",).status_code in (404, 400)


# --------------------------------------------------------------------------
# Список и удаление (Requirements «Список видео и playback», «Удаление видео»)
# --------------------------------------------------------------------------


def test_list_order_newest_first(client, db_path):
    """Список: новые выше (created_at DESC); поля sdd §3."""
    first = _upload(client, name="a.mkv").json()["id"]
    second = _upload(client, name="b.mkv").json()["id"]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE video_videos SET created_at = '2026-10-01T00:00:00+00:00'"
            " WHERE id = ?",
            (first,),
        )
        conn.execute(
            "UPDATE video_videos SET created_at = '2026-10-02T00:00:00+00:00'"
            " WHERE id = ?",
            (second,),
        )
        conn.commit()
    finally:
        conn.close()
    items = client.get("/api/videos").json()["videos"]
    assert [i["id"] for i in items] == [second, first]
    assert set(items[0].keys()) == {
        "id", "filename", "status", "size_bytes", "created_at",
        "preview_url", "file_url",
        # Кусок D (r2): агрегаты социального слоя в элементах списка.
        "category_id", "category_name", "likes", "dislikes", "my_reaction",
    }


def test_delete_removes_volume_and_row(client, videos_dir, db_path):
    """Удаление «готового»: том <id>/ целиком + метаданные; повторный
    запрос по id — 404 (Scenario «Удаление готового видео»)."""
    video_id = _upload(client, name="bye.mkv").json()["id"]
    assert os.path.isdir(os.path.join(videos_dir, video_id))

    resp = client.delete(f"/api/videos/{video_id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert not os.path.exists(os.path.join(videos_dir, video_id))
    conn = sqlite3.connect(db_path)
    try:
        assert (
            conn.execute(
                "SELECT count(*) FROM video_videos WHERE id = ?", (video_id,)
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()
    assert client.delete(f"/api/videos/{video_id}").status_code == 404


def test_delete_of_unfinished_removes_original(client, videos_dir, db_path):
    """Удаление недоконченного: оригинал/артефакты удаляются, записи нет
    (Scenario «Удаление недоконченного видео»; отмена воркера — кусок B)."""
    video_id = _insert_row(db_path, status="converting")
    d = os.path.join(videos_dir, video_id)
    os.makedirs(d)
    with open(os.path.join(d, "original.mkv"), "wb") as f:
        f.write(b"original")
    assert client.delete(f"/api/videos/{video_id}").status_code == 200
    assert not os.path.exists(d)


def test_delete_parity_both_users(client, client2):
    """Удаление равноправно (паритет галереи FR-84): PE удаляет видео
    owner'а — 200, без 403."""
    video_id = _upload(client, name="shared.mkv").json()["id"]
    assert client2.delete(f"/api/videos/{video_id}").status_code == 200


def test_core_tables_untouched(client, db_path):
    """RW-профиль (design §7): после серии операций users/sessions не
    изменены; таблица сервиса — ровно загруженные записи."""
    conn = sqlite3.connect(db_path)
    try:
        before = {
            t: conn.execute(f"SELECT * FROM {t}").fetchall()
            for t in ("users", "sessions")
        }
    finally:
        conn.close()

    for n in range(3):
        assert _upload(client, name=f"v{n}.mkv").status_code == 201
    items = client.get("/api/videos").json()["videos"]
    assert client.delete(f"/api/videos/{items[0]['id']}").status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        for t, rows in before.items():
            assert conn.execute(f"SELECT * FROM {t}").fetchall() == rows, t
        assert (
            conn.execute("SELECT count(*) FROM video_videos").fetchone()[0] == 2
        )
    finally:
        conn.close()
