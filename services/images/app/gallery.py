"""API изображений — роутер images-сервиса (задача 1.2, add-gallery-service).

Источник правды: openspec/changes/add-gallery-service/design.md §2/§3 и
дельта specs/gallery (FR-79…FR-82, NFR-21). Пути и коды ошибок:

- POST   /api/images                      — загрузка (multipart); 422 тип/размер
- GET    /api/images?category=&tag=       — список, created_at DESC, теги,
                                           счетчики + мой голос (1.6, Э-3)
- GET    /api/images/{id}                 — метаданные + теги + реакции + комментарии
- PUT    /api/images/{id}/like            — голос +1 (upsert; повторное — снятие)
- DELETE /api/images/{id}/like            — снятие голоса
- PUT    /api/images/{id}/dislike         — голос −1 (перенос противоположного)
- DELETE /api/images/{id}/dislike         — снятие голоса
- POST   /api/images/{id}/comments        — {body}; пустой после trim → 422
- DELETE /api/images/{id}/comments/{cid}  — только автор; чужой → 403

Файлы (оригинал + превью) — в томе IMAGES_DIR (env EKOTOV_WIKI_IMAGES_DIR,
дефолт /data/images — том images-data), НЕ в БД (FR-79). Имена файлов
генерирует сервер (uuid4hex + расширение по фактическому типу — паттерн
аватаров, имя клиента не доверяем); original_name хранится в БД для
скачивания.

Удаление изображения — осознанная не-цель пакета (design §8, proposal
Out of scope) — эндпоинта DELETE /api/images/{id} НЕТ.

RW-профиль (спека services): пишем только таблицы gallery; users —
SELECT id, login, display_name; короткие транзакции (commit на операцию),
busy_timeout — app/db.py.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError

from app.db import get_connection
from app.images import (
    MAX_SIZE_BYTES,
    UploadValidationError,
    make_thumbnail,
    validate_upload,
)

router = APIRouter()

# Том изображений (deploy задачи 1.3 смонтирует images-data:/data/images).
DEFAULT_IMAGES_DIR = "/data/images"


def get_images_dir() -> str:
    """Каталог тома images-data: env EKOTOV_WIKI_IMAGES_DIR или дефолт.

    Читается на каждый запрос (не на импорт): путь — конфигурация
    окружения; в тестах env переключается фикстурой на временный каталог.
    """
    return os.environ.get("EKOTOV_WIKI_IMAGES_DIR", DEFAULT_IMAGES_DIR)

# Расширения по фактическому mime (имя генерирует сервер).
_EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(request: Request) -> int:
    """id пользователя из сессии (кладет middleware в request.state)."""
    return int(request.state.user_id)


def _require_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="image not found")
    return row


# --------------------------------------------------------------------------
# Загрузка (FR-79)
# --------------------------------------------------------------------------


@router.post("/api/images", status_code=201)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    """multipart: file, category? (id | новое имя), tags? («a,b» | повторяемое).

    Валидация типа (magic-байты) и размера (≤10 МБ) — ДО записи файлов в том:
    при 422 файлы не создаются (scenario «Негативный: превышение размера»).
    Метаданные + связи (категория/теги) — одна транзакция.
    """
    user_id = _user_id(request)
    data = await file.read()

    # 1) Полная валидация содержимого ДО любых записей.
    #    UploadValidationError маппится на 422 формы ядра (handler в main).
    try:
        mime, img = validate_upload(data)
    except UploadValidationError as exc:
        raise RequestValidationError([{"loc": ["file"], "msg": f"invalid file: {exc.code}", "type": "value_error"}], body=b"")

    # 2) Подготовка справочников (короткие транзакции; может создать новые
    #    значения категории/тегов — scenario «Загрузка с категорией и тегами»).
    tag_names = [t.strip() for t in (tags or "").split(",") if t.strip()]
    conn = get_connection()
    try:
        category_id = _resolve_category(conn, category)
        tag_ids = [_resolve_tag(conn, name) for name in tag_names]

        # 3) Имена генерирует сервер (не доверяем имени клиента).
        ext = _EXT_BY_MIME[mime]
        filename = uuid.uuid4().hex + ext
        thumb_name = uuid.uuid4().hex + ".jpg"
        images_dir = get_images_dir()
        os.makedirs(images_dir, exist_ok=True)
        orig_path = os.path.join(images_dir, filename)
        thumb_path = os.path.join(images_dir, thumb_name)

        # Оригинал — исходные байты (не перекодируем; GIF/WebP анимации
        # сохраняют кадры). Превью — JPEG ≤800px по длинной стороне.
        with open(orig_path, "wb") as f:
            f.write(data)
        make_thumbnail(img).save(thumb_path, "JPEG", quality=85)

        try:
            conn.execute(
                "INSERT INTO images (filename, thumb_name, original_name, mime,"
                " size, category_id, uploaded_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    filename,
                    thumb_name,
                    file.filename or filename,
                    mime,
                    len(data),
                    category_id,
                    user_id,
                    _utcnow_iso(),
                ),
            )
            image_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.executemany(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                [(image_id, tid) for tid in tag_ids],
            )
            conn.commit()
        except Exception:
            # Метаданные не легли — файлы в томе не оставляем (без сирот).
            for p in (orig_path, thumb_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            raise
    except HTTPException:
        raise
    except sqlite3.Error:
        # Файлы на диск уже не пишутся до этой точки без валидации; ошибка БД
        # после записи файлов чистится блоком выше. Транзакция откатывается.
        conn.rollback()
        raise HTTPException(status_code=500, detail="database error")
    finally:
        conn.close()

    return {
        "id": image_id,
        "filename": filename,
        "thumb_name": thumb_name,
        "original_name": file.filename or filename,
        "mime": mime,
        "size": len(data),
        "category_id": category_id,
        "tags": tag_names,
        "url": f"/images/{filename}",
        "thumb_url": f"/images/{thumb_name}",
    }


def _resolve_category(conn: sqlite3.Connection, category: Optional[str]) -> Optional[int]:
    """category — существующий id ИЛИ новое имя (design §3)."""
    if category is None or not category.strip():
        return None
    value = category.strip()
    if value.isdigit():
        row = conn.execute(
            "SELECT id FROM image_categories WHERE id = ?", (int(value),)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=422, detail="invalid file: unknown category")
        return int(row["id"])
    row = conn.execute(
        "SELECT id FROM image_categories WHERE name = ?", (value,)
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute("INSERT INTO image_categories (name) VALUES (?)", (value,))
    return int(cur.lastrowid)


def _resolve_tag(conn: sqlite3.Connection, name: str) -> int:
    """Тег — существующий или созданный (словарь gallery_tags, research №3)."""
    row = conn.execute("SELECT id FROM gallery_tags WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute("INSERT INTO gallery_tags (name) VALUES (?)", (name,))
    return int(cur.lastrowid)


# --------------------------------------------------------------------------
# Список / получение (FR-80)
# --------------------------------------------------------------------------

# SQL общего элемента списка: метаданные + URL превью + счетчики + мой голос
# + теги (Э-3/задача 1.6: поле tags в списке, паритет с detail-ответом —
# SELECT общий для list и detail). Теги — агрегат image_tags+gallery_tags,
# имена через ',' в порядке алфавита (group_concat в скалярном подзапросе
# с ORDER BY); разделитель ',' безопасен: имена тегов не могут содержать
# запятую — ввод формы режется по запятым (tags «a,b» → два тега).
_LIST_SELECT = """
SELECT i.id, i.filename, i.thumb_name, i.original_name, i.mime, i.size,
       i.uploaded_by, i.created_at,
       c.name AS category,
       (SELECT group_concat(name, ',') FROM
          (SELECT g.name FROM image_tags it
             JOIN gallery_tags g ON g.id = it.tag_id
            WHERE it.image_id = i.id ORDER BY g.name)) AS tags_csv,
       (SELECT count(*) FROM image_reactions r
         WHERE r.image_id = i.id AND r.value = 1) AS likes,
       (SELECT count(*) FROM image_reactions r
         WHERE r.image_id = i.id AND r.value = -1) AS dislikes,
       (SELECT count(*) FROM image_comments cm WHERE cm.image_id = i.id) AS comments,
       (SELECT r.value FROM image_reactions r
         WHERE r.image_id = i.id AND r.user_id = ?) AS my_reaction
FROM images i
LEFT JOIN image_categories c ON c.id = i.category_id
"""


def _serialize_list_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["url"] = f"/images/{d['filename']}"
    d["thumb_url"] = f"/images/{d['thumb_name']}"
    # tags_csv → tags: [имена]; без тегов (NULL от group_concat) → [].
    d["tags"] = d.pop("tags_csv").split(",") if d["tags_csv"] else []
    d["my_reaction"] = d.pop("my_reaction")  # 1 / -1 / None
    return d


@router.get("/api/images")
def list_images(
    request: Request,
    category: Optional[str] = None,
    tag: Optional[str] = None,
):
    """Фильтры category/tag комбинируются; пустые — все; created_at DESC."""
    viewer_id = _user_id(request)
    conn = get_connection()
    try:
        sql = _LIST_SELECT
        where: list[str] = []
        params: list = [viewer_id]

        if category:
            where.append("c.name = ?")
            params.append(category)
        if tag:
            where.append(
                "EXISTS (SELECT 1 FROM image_tags it JOIN gallery_tags g"
                " ON g.id = it.tag_id WHERE it.image_id = i.id AND g.name = ?)"
            )
            params.append(tag)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY i.created_at DESC, i.id DESC"

        rows = conn.execute(sql, params).fetchall()
        return {"images": [_serialize_list_row(r) for r in rows]}
    finally:
        conn.close()


@router.get("/api/images/{image_id}")
def get_image(request: Request, image_id: int):
    """Полные метаданные + реакции (счетчики + мой голос) + комментарии."""
    viewer_id = _user_id(request)
    conn = get_connection()
    try:
        row = conn.execute(
            _LIST_SELECT + " WHERE i.id = ?", [viewer_id, image_id]
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="image not found")
        item = _serialize_list_row(row)
        comments = conn.execute(
            "SELECT cm.id, cm.body, cm.created_at, cm.user_id,"
            " COALESCE(u.display_name, u.login) AS author"
            " FROM image_comments cm JOIN users u ON u.id = cm.user_id"
            " WHERE cm.image_id = ? ORDER BY cm.created_at ASC, cm.id ASC",
            (image_id,),
        ).fetchall()
        item["comments"] = [dict(c) for c in comments]
        return item
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Реакции (FR-81): ровно один голос пользователя (PK image_id+user_id)
# --------------------------------------------------------------------------


def _set_reaction(conn: sqlite3.Connection, image_id: int, user_id: int, value: int) -> dict:
    """Upsert голоса по design §3/spec FR-81:

    - голоса не было / был противоположный → ставим value (смена голоса —
      «счетчики изменились ровно на один голос»);
    - голос уже value (повторное действие того же знака) → СНИМАЕМ.
    Ответ — обновленные счетчики + мой голос.
    """
    row = conn.execute(
        "SELECT value FROM image_reactions WHERE image_id = ? AND user_id = ?",
        (image_id, user_id),
    ).fetchone()
    if row is not None and int(row["value"]) == value:
        conn.execute(
            "DELETE FROM image_reactions WHERE image_id = ? AND user_id = ?",
            (image_id, user_id),
        )
    else:
        conn.execute(
            "INSERT INTO image_reactions (image_id, user_id, value) VALUES (?, ?, ?)"
            " ON CONFLICT(image_id, user_id) DO UPDATE SET value = excluded.value",
            (image_id, user_id, value),
        )
    conn.commit()
    counts = conn.execute(
        "SELECT"
        " (SELECT count(*) FROM image_reactions WHERE image_id = ? AND value = 1) AS likes,"
        " (SELECT count(*) FROM image_reactions WHERE image_id = ? AND value = -1) AS dislikes",
        (image_id, image_id),
    ).fetchone()
    my = conn.execute(
        "SELECT value FROM image_reactions WHERE image_id = ? AND user_id = ?",
        (image_id, user_id),
    ).fetchone()
    return {
        "likes": counts["likes"],
        "dislikes": counts["dislikes"],
        "my_reaction": my["value"] if my else None,
    }


@router.put("/api/images/{image_id}/like")
def put_like(request: Request, image_id: int):
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        return _set_reaction(conn, image_id, _user_id(request), 1)
    finally:
        conn.close()


@router.put("/api/images/{image_id}/dislike")
def put_dislike(request: Request, image_id: int):
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        return _set_reaction(conn, image_id, _user_id(request), -1)
    finally:
        conn.close()


@router.delete("/api/images/{image_id}/like")
def delete_like(request: Request, image_id: int):
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        conn.execute(
            "DELETE FROM image_reactions WHERE image_id = ? AND user_id = ? AND value = 1",
            (image_id, _user_id(request)),
        )
        conn.commit()
        return _reaction_state(conn, image_id, _user_id(request))
    finally:
        conn.close()


@router.delete("/api/images/{image_id}/dislike")
def delete_dislike(request: Request, image_id: int):
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        conn.execute(
            "DELETE FROM image_reactions WHERE image_id = ? AND user_id = ? AND value = -1",
            (image_id, _user_id(request)),
        )
        conn.commit()
        return _reaction_state(conn, image_id, _user_id(request))
    finally:
        conn.close()


def _reaction_state(conn: sqlite3.Connection, image_id: int, user_id: int) -> dict:
    counts = conn.execute(
        "SELECT"
        " (SELECT count(*) FROM image_reactions WHERE image_id = ? AND value = 1) AS likes,"
        " (SELECT count(*) FROM image_reactions WHERE image_id = ? AND value = -1) AS dislikes",
        (image_id, image_id),
    ).fetchone()
    my = conn.execute(
        "SELECT value FROM image_reactions WHERE image_id = ? AND user_id = ?",
        (image_id, user_id),
    ).fetchone()
    return {
        "likes": counts["likes"],
        "dislikes": counts["dislikes"],
        "my_reaction": my["value"] if my else None,
    }


# --------------------------------------------------------------------------
# Комментарии (FR-82)
# --------------------------------------------------------------------------


@router.post("/api/images/{image_id}/comments", status_code=201)
def add_comment(request: Request, image_id: int, payload: dict):
    """{body}: непустой после trim → иначе 422 (design §3)."""
    user_id = _user_id(request)
    body = (payload or {}).get("body")
    if not isinstance(body, str) or not body.strip():
        raise HTTPException(status_code=422, detail="comment body is empty")
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        cur = conn.execute(
            "INSERT INTO image_comments (image_id, user_id, body, created_at)"
            " VALUES (?, ?, ?, ?)",
            (image_id, user_id, body.strip(), _utcnow_iso()),
        )
        comment_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT cm.id, cm.body, cm.created_at, cm.user_id,"
            " COALESCE(u.display_name, u.login) AS author"
            " FROM image_comments cm JOIN users u ON u.id = cm.user_id"
            " WHERE cm.id = ?",
            (comment_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.delete("/api/images/{image_id}/comments/{comment_id}")
def delete_comment(request: Request, image_id: int, comment_id: int):
    """Только автор; чужой → 403, нет такого → 404 (design §3)."""
    user_id = _user_id(request)
    conn = get_connection()
    try:
        _require_image(conn, image_id)
        row = conn.execute(
            "SELECT user_id FROM image_comments WHERE id = ? AND image_id = ?",
            (comment_id, image_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="comment not found")
        if int(row["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="not your comment")
        conn.execute("DELETE FROM image_comments WHERE id = ?", (comment_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


# Единая форма 422 (паритет search/backend) — см. exception_handler в app/main.py.
