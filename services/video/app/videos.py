"""API видео — роутер video-сервиса (tasks 1.3, video-hosting волна 1).

Источник правды: openspec/changes/video-hosting/sdd.md §2/§3, design.md
§4/§5/§8. Пути и коды:

- POST   /api/videos                — загрузка multipart, ЛЮБОЙ формат;
                                        лимит 500 МБ ДО записи в том
                                        (Content-Length pre-check + потоковый
                                        счетчик-страховка); 201; 401; 422
                                        (кусок D: опц. category_id —
                                        валидация существования в
                                        image_categories, иначе 422;
                                        NULL = «Без категории»)
- GET    /api/videos                — список; 200; 401 (кусок D: фильтр
                                        ?category=<id|none>, none = без
                                        категории; в элементах — category_id,
                                        category_name, likes, dislikes,
                                        my_reaction)
- DELETE /api/videos/{id}           — том <id>/ целиком + метаданные
                                        (+ CASCADE комментариев/реакций —
                                        FK ON DELETE CASCADE, кусок D);
                                        200; 401; 404
- GET    /api/videos/{id}/file      — файл для playback/скачивания;
                                        200; 401; 404; 409 (не ready)
- GET    /api/videos/{id}/preview   — превью-кадр; 200; 401; 404; 409
                                        (не ready / кадра еще нет)
- GET    /api/videos/authcheck      — стык nginx auth_request (design §5);
                                        200 {} / 401 по cookie, без тяжелых
                                        БД-чтений; exempt middleware

Кусок A (без конвертации — tasks 3.1 придет волной 3): загруженный файл
сразу «готово» (status ready) и отдается как есть, в любом формате —
плеер и список работают уже на приемке куска A (решение оркестратора
2026-10-17; в sdd §3 форма ответа «uploaded» — вернется в куске B вместе
с реальной постановкой в очередь: см. enqueue_conversion ниже).

Файлы — в томе videos-data (storage.py — единственный владелец путей),
НЕ в БД (design §5). Имя каталога — uuid сервиса; из имени пользователя
пути не строятся (design §8). Загрузка НЕ блокируется фоновой
конвертацией: чтение тела — в основном потоке uvicorn (design §4).
"""

import os
import sqlite3
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from starlette.responses import FileResponse, JSONResponse

from app import storage
from app.db import get_connection
from app.middleware import SESSION_COOKIE_NAME, _user_id

router = APIRouter()

# ОВ-1: до 500 МБ включительно (паритет images: МБ = МиБ).
MAX_FILE_BYTES = 500 * 1024 * 1024

# Multipart-обвязка (~20 МБ, design §4): Content-Length pre-check режет
# заведомо большие тела ДО чтения (nginx-лимит локации 520m согласован).
MULTIPART_OVERHEAD_BYTES = 20 * 1024 * 1024

# Потоковое чтение тела: чанк 1 МиБ — память запроса не зависит от размера.
STREAM_CHUNK_BYTES = 1024 * 1024


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _user_id_of(request: Request) -> int:
    """id пользователя из сессии (кладет middleware в request.state)."""
    return int(request.state.user_id)


def _validation_error(loc: str, msg: str) -> RequestValidationError:
    """422 в форме ядра: {"error": "validation error", "details": [...]} —
    маппится exception_handler'ом в app/main.py (паритет images)."""
    return RequestValidationError(
        [{"loc": [loc], "msg": msg, "type": "value_error"}], body=b""
    )


def enqueue_conversion(video_id: str) -> None:
    """Заглушка-интерфейс очереди конвертации ДО волны 3 (tasks 1.3:
    «converter.enqueue — заглушка-интерфейс до волны 2»).

    Задача 3.1 (кусок B) заменит этот вызов на converter.enqueue и
    жизненный цикл статусов uploaded → converting → ready; в куске A
    файл сразу ready (см. докстринг модуля) — вызов сохранен как шов,
    чтобы смена свелась к одному файлу (videos.py — зона 1.3/2.3/4.1).
    """
    return None


# --------------------------------------------------------------------------
# Загрузка (Requirement «Загрузка видео — любой формат, ≤ 500 МБ»)
# --------------------------------------------------------------------------


def check_content_length(content_length: int | None) -> None:
    """Content-Length pre-check: тело больше файла+обвязки — 422 ДО чтения.

    Ровно на файле лимит считает потоковый счетчик (Content-Length может
    отсутствовать/лгать) — здесь только дешевый отсев заведомо больших.
    """
    if content_length is not None and content_length > (
        MAX_FILE_BYTES + MULTIPART_OVERHEAD_BYTES
    ):
        raise _validation_error("file", "file is larger than 500 MB")


async def spool_to_temp(file: UploadFile, spool) -> int:
    """Потоковое чтение тела в системный temp с лимитом-страховкой.

    Ничего не пишет в том: spool — tempfile вне тома videos-data; при
    превышении лимита или обрыве чтения бросает UploadTooLarge /
    UploadAborted — вызывающий код чистит spool, каталог в томе НЕ
    создается (Scenario «Отказ при превышении лимита»).
    """
    total = 0
    while True:
        try:
            chunk = await file.read(STREAM_CHUNK_BYTES)
        except Exception as exc:  # обрыв тела (клиент отключился и т.п.)
            raise UploadAborted() from exc
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise UploadTooLarge()
        spool.write(chunk)
    if total == 0:
        raise UploadEmpty()
    return total


class UploadTooLarge(Exception):
    """Тело превысило 500 МБ при потоковом чтении (422)."""


class UploadEmpty(Exception):
    """Пустое тело загрузки (422)."""


class UploadAborted(Exception):
    """Обрыв тела при чтении (клиент отключился; 422, диск не расходуется)."""


def _require_category_id(conn: sqlite3.Connection, raw: str | None) -> int | None:
    """Кусок D: опц. category_id из формы загрузки — валидация существования
    в image_categories (Scenario «Значения — только из справочника галереи»):
    не указан/пустой → None («Без категории»); не существует → 422."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        category_id = int(raw)
    except (TypeError, ValueError):
        raise _validation_error("category_id", "category_id must be an integer")
    row = conn.execute(
        "SELECT id FROM image_categories WHERE id = ?", (category_id,)
    ).fetchone()
    if row is None:
        raise _validation_error("category_id", "category_id not found")
    return category_id


@router.post("/api/videos", status_code=201)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    category_id: str | None = Form(default=None),
):
    """multipart: file (любой формат, ≤ 500 МБ, ОВ-1/ОВ-4) + опц.
    category_id (кусок D; валидация существования в image_categories —
    иначе 422; NULL = «Без категории»).

    Лимит проверяется ДО записи в том: pre-check по Content-Length +
    потоковый счетчик (диск под файл расходуется только под temp вне
    тома и только в пределах лимита; при отказе — чистится). Scenario
    «Отказ при превышении лимита»: 422, файл не сохранен, записи нет.
    """
    user_id = _user_id_of(request)

    # 0) Категория (кусок D): до чтения тела — дешевый SELECT справочника.
    conn = get_connection()
    try:
        resolved_category_id = _require_category_id(conn, category_id)
    finally:
        conn.close()

    # 1) Pre-check ДО чтения тела (design §4).
    raw_cl = request.headers.get("content-length")
    try:
        check_content_length(int(raw_cl) if raw_cl is not None else None)
    except ValueError:
        raise _validation_error("file", "invalid content-length")

    # 2) Потоковое чтение в temp (вне тома) со счетчиком-страховкой.
    spool = tempfile.NamedTemporaryFile(delete=False, suffix=".upload")
    tmp_path = spool.name
    try:
        try:
            size = await spool_to_temp(file, spool)
        except (UploadTooLarge, UploadAborted):
            raise _validation_error("file", "file is larger than 500 MB")
        except UploadEmpty:
            raise _validation_error("file", "empty upload")
        spool.close()

        # 3) Каталог и путь — ТОЛЬКО из uuid сервиса (storage; design §8).
        video_id = storage.new_video_id()
        ext = storage.normalize_ext(file.filename)
        mime = file.content_type or None

        conn = get_connection()
        try:
            storage.create_video_dir(video_id)
            try:
                # Атомарный перенос temp → том (после этого temp
                # отсутствует); сбой переноса — сирот в томе не оставляем.
                storage.store_original(video_id, ext, tmp_path)
            except Exception:
                storage.delete_video_dir(video_id)
                raise
            try:
                # Кусок A: сразу ready (файл отдается как есть). Кусок B
                # (3.1) вернет статус «uploaded» + enqueue_conversion().
                # category_id — кусок D (NULL = «Без категории»).
                conn.execute(
                    "INSERT INTO video_videos (id, filename, status, size_bytes,"
                    " mime, uploaded_by, created_at, convert_attempts, category_id)"
                    " VALUES (?, ?, 'ready', ?, ?, ?, ?, 0, ?)",
                    (
                        video_id,
                        file.filename or f"original.{ext}",
                        size,
                        mime,
                        user_id,
                        _utcnow_iso(),
                        resolved_category_id,
                    ),
                )
                conn.commit()
            except Exception:
                # Метаданные не легли — файлов в томе не оставляем (без сирот).
                storage.delete_video_dir(video_id)
                raise
        except sqlite3.Error:
            conn.rollback()
            raise HTTPException(status_code=500, detail="database error")
        finally:
            conn.close()
    finally:
        spool.close()
        # Остаток temp чистится всегда: после отказа/обрыва — весь файл,
        # после успеха store_original — уже пустой путь (no-op).
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Заглушка-интерфейс очереди (до волны 3; см. enqueue_conversion).
    enqueue_conversion(video_id)

    return {
        "id": video_id,
        "filename": file.filename or f"original.{ext}",
        "status": "ready",
        "size": size,
        "category_id": resolved_category_id,
    }


# --------------------------------------------------------------------------
# Список (Requirement «Список видео и playback»)
# --------------------------------------------------------------------------


@router.get("/api/videos")
def list_videos(request: Request, category: str | None = None):
    """Список: имя, статус, размер, дата + playback/preview URL.

    Кусок D: фильтр ?category=<id|none> (none = «Без категории»,
    category_id IS NULL; неверный id — 422); в элементах — category_id/
    category_name (COALESCE имени справочника галереи), likes/dislikes/
    my_reaction (агрегаты video_reactions; мой голос — по сессии).
    preview_url — API-эндпоинт (409 = плейсхолдер по макету);
    file_url — nginx-отдача из тома /videos/<id>/… (design §5,
    auth_request-сессия, Range для <video>).
    """
    viewer_id = _user_id_of(request)

    where = ""
    params: list = []
    if category is not None and category != "":
        if category == "none":
            where = " WHERE v.category_id IS NULL"
        else:
            try:
                cat_id = int(category)
            except ValueError:
                raise _validation_error("category", "category must be an id or 'none'")
            where = " WHERE v.category_id = ?"
            params = [cat_id]

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT v.id, v.filename, v.status, v.size_bytes, v.uploaded_by,"
            " v.created_at, v.category_id,"
            " COALESCE(c.name, '') AS category_name,"
            " (SELECT count(*) FROM video_reactions r"
            "   WHERE r.video_id = v.id AND r.value = 1) AS likes,"
            " (SELECT count(*) FROM video_reactions r"
            "   WHERE r.video_id = v.id AND r.value = -1) AS dislikes,"
            " (SELECT r.value FROM video_reactions r"
            "   WHERE r.video_id = v.id AND r.user_id = ?) AS my_reaction"
            " FROM video_videos v"
            " LEFT JOIN image_categories c ON c.id = v.category_id"
            + where
            + " ORDER BY v.created_at DESC, v.id DESC",
            [viewer_id] + params,
        ).fetchall()
        videos = []
        for row in rows:
            videos.append(
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "status": row["status"],
                    "size_bytes": row["size_bytes"],
                    "created_at": row["created_at"],
                    "preview_url": f"/api/videos/{row['id']}/preview",
                    "file_url": storage.playable_url(row["id"]),
                    "category_id": row["category_id"],
                    "category_name": row["category_name"] or None,
                    "likes": row["likes"],
                    "dislikes": row["dislikes"],
                    "my_reaction": row["my_reaction"],
                }
            )
        return {"videos": videos}
    finally:
        conn.close()


def _require_video(conn: sqlite3.Connection, video_id: str) -> sqlite3.Row:
    if not storage.is_video_id(video_id):
        raise HTTPException(status_code=404, detail="video not found")
    row = conn.execute(
        "SELECT * FROM video_videos WHERE id = ?", (video_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="video not found")
    return row


# --------------------------------------------------------------------------
# Playback / превью (Requirements «Список видео и playback»)
# --------------------------------------------------------------------------


@router.get("/api/videos/{video_id}/file")
def get_video_file(request: Request, video_id: str):
    """Файл видео: 200 (готовое) / 401 / 404 / 409 (не ready — плеер не
    запускается). Кусок A: исходник в исходном формате (как есть);
    после куска B storage.playable_path переключит на video.mp4."""
    conn = get_connection()
    try:
        row = _require_video(conn, video_id)
        if row["status"] != "ready":
            raise HTTPException(status_code=409, detail="video is not ready")
        path = storage.playable_path(video_id)
        if path is None:
            raise HTTPException(status_code=404, detail="video file not found")
        return FileResponse(
            path,
            media_type=row["mime"] or "application/octet-stream",
            filename=row["filename"],
        )
    finally:
        conn.close()


@router.get("/api/videos/{video_id}/preview")
def get_video_preview(request: Request, video_id: str):
    """Превью-кадр: 200 (jpeg) / 401 / 404 / 409 (не ready или кадра еще
    нет — плейсхолдер по макету; кадр генерит конвертер — кусок B, 3.1)."""
    conn = get_connection()
    try:
        row = _require_video(conn, video_id)
        if row["status"] != "ready":
            raise HTTPException(status_code=409, detail="video is not ready")
        path = storage.preview_path(video_id)
        if not os.path.isfile(path):
            raise HTTPException(status_code=409, detail="preview is not ready")
        return FileResponse(path, media_type="image/jpeg")
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Удаление (Requirement «Удаление видео»)
# --------------------------------------------------------------------------


@router.delete("/api/videos/{video_id}")
def delete_video(request: Request, video_id: str):
    """Удаление: том <id>/ целиком + метаданные. Равноправное — БЕЗ
    разделения прав (паритет галереи FR-84); несуществующее — 404.
    Комментарии/реакции удаляются CASCADE'ом FK (PRAGMA foreign_keys=ON
    в db.get_connection, кусок D). Отмена идущей конвертации — кусок B
    (флаг воркера, design §3)."""
    conn = get_connection()
    try:
        _require_video(conn, video_id)
        conn.execute("DELETE FROM video_videos WHERE id = ?", (video_id,))
        conn.commit()
        storage.delete_video_dir(video_id)
        return {"ok": True}
    except sqlite3.Error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="database error")
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Стык nginx auth_request (design §5; exempt middleware)
# --------------------------------------------------------------------------


@router.get("/api/videos/authcheck")
def authcheck(request: Request):
    """200 {} при валидной сессии / 401 — по cookie subrequest'а.

    Вызывается nginx'ом на каждый запрос /videos/*: только SELECT
    sessions (O(мс)), никаких чтений video_videos (sdd §3 «без чтения
    БД тяжелее проверки сессии»)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        conn = get_connection()
        try:
            if _user_id(conn, token) is not None:
                return {}
        finally:
            conn.close()
    return JSONResponse(status_code=401, content={"error": "unauthorized"})
