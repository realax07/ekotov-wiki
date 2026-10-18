"""API социального слоя — роутер video-сервиса (tasks 2.2, video-hosting
волна 2, кусок D; r2).

Источник правды: openspec/changes/video-hosting/sdd.md §2/§3, design.md
§7/§8, Requirements «Комментарии…», «Лайки…», «Категории…», NFR-38.
Пути и коды:

- GET    /api/videos/{id}/comments            — список (автор, время, текст);
                                                200; 401; 404
- POST   /api/videos/{id}/comments            — {text} непустой после trim;
                                                201; 401; 404; 422
- DELETE /api/videos/{id}/comments/{cid}      — ТОЛЬКО свой (чужой = 403);
                                                200; 401; 403; 404
- PUT    /api/videos/{id}/reaction            — {value: 1|-1}: ровно один
                                                голос на пользователя
                                                (PK video_id+user_id): тот же
                                                value снимает (DELETE строки),
                                                противоположный переносит
                                                (UPDATE) — атомарно в одной
                                                транзакции; 200
                                                {my_reaction, likes, dislikes};
                                                401; 404; 422
- GET    /api/videos/categories               — справочник категорий —
                                                SELECT из СУЩЕСТВУЮЩЕЙ
                                                image_categories (RO; новый
                                                справочник НЕ создается —
                                                создание категорий остается
                                                галерее, POST /api/categories
                                                ядра); 200; 401

Все эндпоинты — за сессионным middleware (без новых exempt, NFR-38):
без валидной сессии запросы не доходят сюда (401 в middleware).

Паттерн — comments/reactions галереи (services/images/app/gallery.py,
FR-81/82); имя автора — COALESCE(display_name, login). DELETE-ветки
детерминированы по кодам: 404 — нет видео/комментария, 403 — чужой
комментарий; реакция upsert/delete — одна транзакция BEGIN IMMEDIATE
(короткая, busy_timeout — сосуществование с ядром).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from app.db import get_connection

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id_of(request: Request) -> int:
    """id пользователя из сессии (кладет middleware в request.state)."""
    return int(request.state.user_id)


def _require_video(conn, video_id: str):
    """Видео существует — иначе 404 (id — ключ БД, путь из него НЕ строится)."""
    row = conn.execute(
        "SELECT id FROM video_videos WHERE id = ?", (video_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="video not found")
    return row


# --------------------------------------------------------------------------
# Комментарии (Requirement «Комментарии к видео»)
# --------------------------------------------------------------------------


@router.get("/api/videos/{video_id}/comments")
def list_comments(request: Request, video_id: str):
    """Список комментариев: {id, user_id, user, text, created_at} — старые
    сверху (паритет галереи); user_id — фронт рендерит «удалить» только
    у СВОИХ (comment.user_id === me.id, мокап video-view.html)."""
    conn = get_connection()
    try:
        _require_video(conn, video_id)
        rows = conn.execute(
            "SELECT cm.id, cm.user_id, cm.text, cm.created_at,"
            " COALESCE(u.display_name, u.login) AS user"
            " FROM video_comments cm JOIN users u ON u.id = cm.user_id"
            " WHERE cm.video_id = ?"
            " ORDER BY cm.created_at ASC, cm.id ASC",
            (video_id,),
        ).fetchall()
        return {"comments": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/api/videos/{video_id}/comments", status_code=201)
def add_comment(request: Request, video_id: str, payload: dict):
    """{text}: непустой после trim — иначе 422 (sdd §3; паттерн галереи)."""
    user_id = _user_id_of(request)
    text = (payload or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=422, detail="comment text is empty")
    conn = get_connection()
    try:
        _require_video(conn, video_id)
        comment_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO video_comments (id, video_id, user_id, text, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (comment_id, video_id, user_id, text.strip(), _utcnow_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT cm.id, cm.user_id, cm.text, cm.created_at,"
            " COALESCE(u.display_name, u.login) AS user"
            " FROM video_comments cm JOIN users u ON u.id = cm.user_id"
            " WHERE cm.id = ?",
            (comment_id,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.delete("/api/videos/{video_id}/comments/{comment_id}")
def delete_comment(request: Request, video_id: str, comment_id: str):
    """Удаление ТОЛЬКО своего комментария: чужой — 403, нет такого — 404
    (Scenario «Удаление только своего комментария»)."""
    user_id = _user_id_of(request)
    conn = get_connection()
    try:
        _require_video(conn, video_id)
        row = conn.execute(
            "SELECT user_id FROM video_comments WHERE id = ? AND video_id = ?",
            (comment_id, video_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="comment not found")
        if int(row["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="not your comment")
        conn.execute("DELETE FROM video_comments WHERE id = ?", (comment_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Реакции (Requirement «Лайки и дизлайки — один голос на пользователя»)
# --------------------------------------------------------------------------


@router.put("/api/videos/{video_id}/reaction")
def put_reaction(request: Request, video_id: str, payload: dict):
    """Голос {value: 1|-1} — ровно один на пользователя (PK(video_id,user_id)):
    тот же value снимает (DELETE строки), противоположный переносит (UPDATE).
    Атомарно: SELECT+DELETE/UPDATE/INSERT+счетчики в ОДНОЙ транзакции
    BEGIN IMMEDIATE — повторные клики не могут оставить двух голосов.
    Ответ {my_reaction, likes, dislikes}; my_reaction=null после снятия."""
    user_id = _user_id_of(request)
    value = (payload or {}).get("value")
    if value not in (1, -1):
        raise HTTPException(
            status_code=422, detail="value must be 1 or -1"
        )
    conn = get_connection()
    try:
        _require_video(conn, video_id)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT value FROM video_reactions WHERE video_id = ? AND user_id = ?",
            (video_id, user_id),
        ).fetchone()
        if row is not None and int(row["value"]) == value:
            # Повторный клик — снятие голоса (Scenario «Повторный клик
            # снимает голос»).
            conn.execute(
                "DELETE FROM video_reactions WHERE video_id = ? AND user_id = ?",
                (video_id, user_id),
            )
        elif row is not None:
            # Клик по второй кнопке — перенос голоса (UPDATE той же строки).
            conn.execute(
                "UPDATE video_reactions SET value = ?, created_at = ?"
                " WHERE video_id = ? AND user_id = ?",
                (value, _utcnow_iso(), video_id, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO video_reactions (video_id, user_id, value, created_at)"
                " VALUES (?, ?, ?, ?)",
                (video_id, user_id, value, _utcnow_iso()),
            )
        conn.commit()
        counts = conn.execute(
            "SELECT"
            " (SELECT value FROM video_reactions"
            "   WHERE video_id = ? AND user_id = ?) AS my_reaction,"
            " (SELECT count(*) FROM video_reactions"
            "   WHERE video_id = ? AND value = 1) AS likes,"
            " (SELECT count(*) FROM video_reactions"
            "   WHERE video_id = ? AND value = -1) AS dislikes",
            (video_id, user_id, video_id, video_id),
        ).fetchone()
        return {
            "my_reaction": counts["my_reaction"],
            "likes": counts["likes"],
            "dislikes": counts["dislikes"],
        }
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Категории (Requirement «Категории видео — общий справочник с галереей»)
# --------------------------------------------------------------------------


@router.get("/api/videos/categories")
def list_categories(request: Request):
    """SELECT из image_categories (RO): справочник ОДИН, общий с галереей
    (sdd §4 — сервис НЕ пишет в чужую таблицу; создание категорий —
    галерея, POST /api/categories ядра)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name FROM image_categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return {"categories": [dict(row) for row in rows]}
    finally:
        conn.close()
