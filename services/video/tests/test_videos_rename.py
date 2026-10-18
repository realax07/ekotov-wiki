"""Тесты переименования видео (tasks 7.1, video-hosting волна 7).

Паритет rename изображений (services/images, FR-97): PATCH
/api/videos/{id} с телом {"title"} — 200 {id, title}; границы 1–255
символов юникода включительно; 422-негативы (пустой/пробелы/без поля/не
строка/256//,\\, ctrl); 404 (_require_video); 401 без сессии (middleware,
NFR-36/38 — новых exempt нет). Меняется ТОЛЬКО filename в video_videos:
том videos-data (файлы uuid) побайтно не тронут, поиск/сортировка видят
новое имя.

Фикстуры/хелперы — общие волны 1 (test_videos_service): та же схема БД,
тот же временный том, тот же TestClient-каркас (конвенция сьюта).

Трассировка: сценарии дельты specs/video-service «Переименование видео»
(9 сценариев) — TC-vid-090…099 (продолжение нумерации сьюта: 001…034
кусок A, 040…058 кусок D, 080…086 кусок C).
"""

import os
import sqlite3
import uuid

import pytest

# Общие фикстуры/хелперы волны 1 (пакет tests, __init__.py на месте).
from tests.test_videos_service import (  # noqa: F401
    _insert_row,
    _upload,
    anon_client,
    client,
    db_path,
    videos_dir,
)


def _rename(client, video_id, payload, **kwargs):
    return client.patch(
        f"/api/videos/{video_id}", json=payload, **kwargs
    )


def _filename_of(db_path, video_id):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT filename FROM video_videos WHERE id = ?", (video_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _volume_snapshot(root):
    """(относительный путь, размер, mtime_ns) всех файлов тома."""
    snapshot = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            snapshot.append((rel, os.path.getsize(full), os.stat(full).st_mtime_ns))
    return sorted(snapshot)


def _make_ready(db_path, video_id):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE video_videos SET status = 'ready' WHERE id = ?", (video_id,)
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Успешное переименование (Scenario «Успешное переименование»)
# --------------------------------------------------------------------------


def test_rename_happy_path(client, db_path, videos_dir):
    """TC-vid-090. 200 {id, title}; в БД новый filename, статус и остальные
    колонки не тронуты; запись видна в списке под новым именем."""
    video_id = _insert_row(db_path, filename="clip_001.mp4")

    resp = _rename(client, video_id, {"title": "Отпуск 2026"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": video_id, "title": "Отпуск 2026"}

    assert _filename_of(db_path, video_id) == "Отпуск 2026"

    # Остальные колонки записи не изменились.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status, size_bytes, mime, uploaded_by FROM video_videos"
            " WHERE id = ?",
            (video_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("ready", 10, "video/x-matroska", 1)

    # Список показывает новое имя.
    items = client.get("/api/videos").json()["videos"]
    assert [v["filename"] for v in items] == ["Отпуск 2026"]


def test_rename_trims_surrounding_spaces(client, db_path):
    """TC-vid-090b. Пробелы по краям обрезаются (паритет images: value =
    name.strip()); в БД — trim-значение."""
    video_id = _insert_row(db_path)
    resp = _rename(client, video_id, {"title": "  Новое имя  "})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": video_id, "title": "Новое имя"}
    assert _filename_of(db_path, video_id) == "Новое имя"


# --------------------------------------------------------------------------
# Границы длины (Scenario «Границы длины имени включены»)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("length", [1, 255])
def test_rename_boundaries_unicode_ok(client, db_path, length):
    """TC-vid-091. 1 и 255 символов юникода (кириллица) — 200, границы
    включительно."""
    video_id = _insert_row(db_path)
    title = "и" * length
    resp = _rename(client, video_id, {"title": title})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"id": video_id, "title": title}
    assert _filename_of(db_path, video_id) == title


# --------------------------------------------------------------------------
# Негативы 422 (Scenario «Негативный: пустой или отсутствующий title»,
# «Негативный: превышение длины», «Негативный: недопустимые символы»)
# --------------------------------------------------------------------------


def test_rename_256_chars_422(client, db_path):
    """TC-vid-092. 256 символов — 422, имя не изменено."""
    video_id = _insert_row(db_path, filename="старое.mkv")
    resp = _rename(client, video_id, {"title": "и" * 256})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "validation error"
    assert _filename_of(db_path, video_id) == "старое.mkv"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "   "},
        {},
        {"title": 123},
        {"title": None},
    ],
    ids=["empty", "spaces", "no-field", "not-a-string", "null"],
)
def test_rename_invalid_title_422(client, db_path, payload):
    """TC-vid-093. Пустой/пробелы/без поля/не строка — 422, имя не изменено
    (Scenario «Негативный: пустой или отсутствующий title»)."""
    video_id = _insert_row(db_path, filename="старое.mkv")
    resp = _rename(client, video_id, payload)
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"
    assert _filename_of(db_path, video_id) == "старое.mkv"


@pytest.mark.parametrize(
    "title",
    ["a/b", "a\\b", "строка\nс-переносом", "таб\tуляция", "term\x00"],
    ids=["slash", "backslash", "newline", "tab", "nul"],
)
def test_rename_forbidden_chars_422(client, db_path, title):
    """TC-vid-094. «/», «\\», управляющие символы — 422, имя не изменено
    (Scenario «Негативный: недопустимые символы», паритет images)."""
    video_id = _insert_row(db_path, filename="старое.mkv")
    resp = _rename(client, video_id, {"title": title})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation error"
    assert _filename_of(db_path, video_id) == "старое.mkv"


def test_rename_non_dict_body_422(client, db_path):
    """TC-vid-094b. Тело не JSON-объект — 422 (FastAPI-схема payload: dict),
    имя не изменено."""
    video_id = _insert_row(db_path, filename="старое.mkv")
    resp = client.patch(f"/api/videos/{video_id}", json="не-объект")
    assert resp.status_code == 422
    assert _filename_of(db_path, video_id) == "старое.mkv"


# --------------------------------------------------------------------------
# 404 (Scenario «Негативный: несуществующее видео»)
# --------------------------------------------------------------------------


def test_rename_missing_video_404(client, db_path):
    """TC-vid-095. Несуществующий id — 404; состояние сервиса не изменилось
    (чужая запись с тем же именем не появилась)."""
    before = client.get("/api/videos").json()["videos"]
    resp = _rename(client, uuid.uuid4().hex, {"title": "Отпуск 2026"})
    assert resp.status_code == 404
    assert client.get("/api/videos").json()["videos"] == before


def test_rename_bad_id_format_404(client):
    """TC-vid-095b. Не-uuid id — 404 (_require_video: is_video_id strict,
    защита от path traversal, design §8)."""
    resp = _rename(client, "not-a-uuid", {"title": "x"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# 401 (Scenario «Негативный: без сессии», NFR-36/38)
# --------------------------------------------------------------------------


def test_rename_no_session_401(anon_client, db_path):
    """TC-vid-096. Без сессии — 401 {"error": "unauthorized"}, имя видео
    не изменено; новых exempt для PATCH в middleware нет."""
    video_id = _insert_row(db_path, filename="старое.mkv")
    resp = _rename(anon_client, video_id, {"title": "Отпуск 2026"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}
    assert _filename_of(db_path, video_id) == "старое.mkv"


# --------------------------------------------------------------------------
# Том не изменился (Requirement: файлы тома uuid MUST NOT меняться)
# --------------------------------------------------------------------------


def test_rename_volume_untouched(client, db_path, videos_dir):
    """TC-vid-097. Снапшот тома (пути/размеры/mtimes) до и после —
    идентичен: изменилась ТОЛЬКО запись БД filename."""
    content = b"\x1aE\xdf\xa3-fake-mp4-payload"
    resp = _upload(client, name="clip_001.mp4", content=content,
                   content_type="video/mp4")
    assert resp.status_code == 201, resp.text
    video_id = resp.json()["id"]
    _make_ready(db_path, video_id)

    before = _volume_snapshot(videos_dir)
    assert before  # файл в томе есть

    resp = _rename(client, video_id, {"title": "Отпуск 2026"})
    assert resp.status_code == 200, resp.text
    assert _filename_of(db_path, video_id) == "Отпуск 2026"

    assert _volume_snapshot(videos_dir) == before

    # Playback/preview по прежним ссылкам работают (готовое видео — 200).
    assert client.get(f"/api/videos/{video_id}/preview").status_code in (200, 409)
    assert client.get(f"/api/videos/{video_id}/file").status_code == 200


# --------------------------------------------------------------------------
# Поиск/сортировка видят новое имя (Scenario «Успешное переименование»:
# «в списке… — новое имя» + Requirement «Сортировка и поиск по имени»)
# --------------------------------------------------------------------------


def test_rename_visible_to_search_and_sort(client, db_path):
    """TC-vid-098. После переименования: ?query= по новому имени находит,
    по старому — нет (регистр не учитывается); сортировка по имени
    переставляет записи по новому имени."""
    id_a = _insert_row(db_path, filename="ааа.mkv")
    id_b = _insert_row(db_path, filename="яяя.mkv")
    _rename(client, id_a, {"title": "Отпуск 2026"})

    found = client.get("/api/videos", params={"query": "отпуск"}).json()["videos"]
    assert [v["id"] for v in found] == [id_a]

    not_found = client.get("/api/videos", params={"query": "ааа"}).json()["videos"]
    assert [v["id"] for v in not_found] == []

    asc = client.get("/api/videos", params={"order": "asc"}).json()["videos"]
    assert [v["id"] for v in asc] == [id_a, id_b]
    desc = client.get("/api/videos", params={"order": "desc"}).json()["videos"]
    assert [v["id"] for v in desc] == [id_b, id_a]


def test_rename_openapi_no_new_path(client):
    """TC-vid-099. PATCH живет на существующем пути /api/videos/{video_id} —
    множество путей схемы не расширилось (exempt-ов новых нет)."""
    paths = set(client.get("/openapi.json").json()["paths"].keys())
    assert "/api/videos/{video_id}" in paths
    assert len(paths) == 10
