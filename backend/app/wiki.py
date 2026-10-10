"""Wiki: REST API /api/wiki/* (change add-wiki, tasks.md 2.2; design.md §3,
§5, §6; FR-107…FR-116).

Контракт — design.md §3 дословно:
- Все методы требуют сессию (аноним — 401 middleware'ом, app/middleware.py,
  паттерн board.py §8); разделения по ролям НЕТ (решение 7, FR-115).
- GET /api/wiki/pages — плоский список {id, parent_id, title, updated_at};
  дерево строит клиент (§6, NFR-30 — один запрос, без вложенных).
- POST /api/wiki/pages — создание: title непустой (422), существующий
  parent_id (422), content санитизируется ДО записи (§4); 200 {id}
  (таблица контракта §3; ТЗ задачи говорит 201 — отдается 201, код
  создания ресурса; проверяется тестом на точное значение).
- GET /api/wiki/pages/{id} — страница + breadcrumb (сервер, §6: цепочка
  parent_id с лимитом глубины 100 от зацикливания) + can_delete (нет
  дочерних — для UI кнопки «Удалить», FR-116).
- PUT /api/wiki/pages/{id} — каждое сохранение = INSERT в page_versions
  (контент ПОСЛЕ санитизации, автор сессии, created_at) + updated_at
  (FR-112); 404 — нет страницы; 422 — пустой title.
- GET /api/wiki/pages/{id}/versions — список версий от новых к старым
  {id, author_id, created_at}, без контента (§9: составной индекс).
- GET /api/wiki/pages/{id}/versions/{vid} — контент версии (read-only).
- POST /api/wiki/pages/{id}/revert/{vid} — откат: контент версии становится
  текущим + НОВАЯ запись в page_versions (автор — исполнитель отката);
  история не переписывается (FR-113).
- GET /api/wiki/search?q= — LIKE %q% по title+content с экранированием
  %_\\ и ESCAPE '\\' (§6); сниппет: фрагмент вокруг первого вхождения
  (окно ±60 символов) + оффсет и длина совпадения — <mark> вставляет
  клиент по позиции (сервер HTML в API-ответ не вставляет); path —
  breadcrumb строкой; ORDER BY updated_at DESC, LIMIT 20.
- DELETE /api/wiki/pages/{id} — 409 при наличии дочерних (ОВ-2, FR-116);
  иначе удаление, версии уходят по FK ON DELETE CASCADE.

Время — msk_now_iso() из app.board (единый источник МСК-времени монолита,
паттерн board.py; формат «...+03:00» во всех полях даты).
"""

import sqlite3
from html.parser import HTMLParser
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from app.board import msk_now_iso
from app.db import get_connection
from app.sanitize import sanitize_html

router = APIRouter(prefix="/api/wiki")

NOT_FOUND_BODY = {"error": "not found"}

# Защита breadcrumb-цепочки от цикла в parent_id (design.md §6: «лимит
# глубины, например 100»).
MAX_DEPTH = 100

# Окно сниппета поиска вокруг первого вхождения (design.md §6: ±60).
SNIPPET_WINDOW = 60

SEARCH_LIMIT = 20


def _strip_tags(html: str) -> str:
    """HTML → plain-текст для сниппета поиска (review-001 DV-1): теги
    срезаются до вычисления окна/оффсета. Санитизация контента — отдельно,
    на записи (sanitize_html); здесь только срез разметки для выдачи."""


    class _TagDropper(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    dropper = _TagDropper()
    dropper.feed(html or "")
    return " ".join(" ".join(dropper.parts).split())


def _utcnow() -> str:
    return msk_now_iso()


def _session_user_id(conn: sqlite3.Connection, request: Request) -> int | None:
    """user_id по токену сессии из куки (паттерн app/comments.py)."""
    from app.auth import SESSION_COOKIE_NAME

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    return row[0] if row is not None else None


def _escape_like(value: str) -> str:
    """Экранирование спецсимволов LIKE (% _ \\) для паттерна с ESCAPE '\\'
    (design.md §6)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PageCreate(BaseModel):
    """Тело POST /api/wiki/pages (design.md §3)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    parent_id: int | None = None
    content: str = ""

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value


class PageUpdate(BaseModel):
    """Тело PUT /api/wiki/pages/{id}: частичное сохранение {title?, content?}."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str | None = None

    @field_validator("title")
    @classmethod
    def _title_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("title must not be empty")
        return value


def _page_exists(conn: sqlite3.Connection, page_id: int) -> bool:
    return (
        conn.execute("SELECT 1 FROM pages WHERE id = ?", (page_id,)).fetchone()
        is not None
    )


def _has_children(conn: sqlite3.Connection, page_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM pages WHERE parent_id = ? LIMIT 1", (page_id,)
        ).fetchone()
        is not None
    )


def _breadcrumb_chain(conn: sqlite3.Connection, page_id: int) -> list[dict[str, Any]]:
    """Цепочка предков {id, title} от корня к самой странице (design.md §6):
    цикл по parent_id, точечные SELECT по PK, лимит глубины от цикла."""
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    current: int | None = page_id
    while current is not None and len(seen) < MAX_DEPTH:
        if current in seen:
            break  # цикл в данных — обрываем, отдаем что накопили
        seen.add(current)
        row = conn.execute(
            "SELECT id, parent_id, title FROM pages WHERE id = ?", (current,)
        ).fetchone()
        if row is None:
            break
        chain.append({"id": row[0], "title": row[2]})
        current = row[1]
    chain.reverse()  # от корня к текущей
    return chain


def _path_string(conn: sqlite3.Connection, page_id: int) -> str:
    """Breadcrumb строкой (design.md §3: «путь = breadcrumb строкой»)."""
    return " / ".join(node["title"] for node in _breadcrumb_chain(conn, page_id))


def _insert_version(
    conn: sqlite3.Connection, page_id: int, content: str, author_id: int
) -> int:
    """Запись версии (FR-112): контент уже санитизирован вызывающим кодом."""
    version_id = conn.execute(
        "INSERT INTO page_versions (page_id, content, author_id, created_at)"
        " VALUES (?, ?, ?, ?)",
        (page_id, content, author_id, _utcnow()),
    ).lastrowid
    assert version_id is not None  # INSERT: sqlite всегда возвращает rowid
    return version_id


@router.get("/pages")
def list_pages() -> JSONResponse:
    """Плоский список страниц для дерева (design.md §3, §6): без контента."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, parent_id, title, updated_at FROM pages ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse(
        content={
            "pages": [
                {
                    "id": row[0],
                    "parent_id": row[1],
                    "title": row[2],
                    "updated_at": row[3],
                }
                for row in rows
            ]
        }
    )


@router.post("/pages", status_code=201)
def create_page(body: PageCreate, request: Request) -> JSONResponse:
    """Создание страницы (design.md §3): 201 {id}; 422 — пустой title /
    несуществующий parent_id; content санитизируется до записи (§4)."""
    conn = get_connection()
    try:
        if body.parent_id is not None and not _page_exists(conn, body.parent_id):
            return JSONResponse(
                status_code=422,
                content={"error": "validation error", "details": "parent_id not found"},
            )
        author_id = _session_user_id(conn, request)
        if author_id is None:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        now = _utcnow()
        content = sanitize_html(body.content)
        try:
            cur = conn.execute(
                "INSERT INTO pages (parent_id, title, content, author_id,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (body.parent_id, body.title, content, author_id, now, now),
            )
            page_id = cur.lastrowid
            assert page_id is not None  # INSERT: sqlite всегда возвращает rowid
        except sqlite3.IntegrityError:
            # Страховка FK схемы (design.md §1) поверх явной проверки.
            conn.rollback()
            return JSONResponse(
                status_code=422,
                content={"error": "validation error", "details": "parent_id not found"},
            )
        # Первая версия = исходный контент (PUT-цикл версий замкнут:
        # у страницы всегда есть v1).
        _insert_version(conn, page_id, content, author_id)
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(status_code=201, content={"id": page_id})


@router.get("/pages/{page_id}")
def get_page(page_id: int) -> JSONResponse:
    """Страница + breadcrumb от корня (сервер) + can_delete (design.md §3)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, parent_id, title, content, author_id, created_at,"
            " updated_at FROM pages WHERE id = ?",
            (page_id,),
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        page = {
            "id": row[0],
            "parent_id": row[1],
            "title": row[2],
            "content": row[3],
            "author_id": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "breadcrumb": _breadcrumb_chain(conn, page_id),
            "can_delete": not _has_children(conn, page_id),
        }
    finally:
        conn.close()
    return JSONResponse(content=page)


@router.put("/pages/{page_id}")
def update_page(page_id: int, body: PageUpdate, request: Request) -> JSONResponse:
    """Сохранение правки (design.md §3, FR-112): version INSERT на каждое
    сохранение + updated_at; 404 — нет страницы; 422 — пустой title."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT title, content FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        author_id = _session_user_id(conn, request)
        if author_id is None:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        title = body.title if body.title is not None else row[0]
        content = (
            sanitize_html(body.content) if body.content is not None else row[1]
        )
        _insert_version(conn, page_id, content, author_id)
        conn.execute(
            "UPDATE pages SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, _utcnow(), page_id),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"ok": True})


@router.get("/pages/{page_id}/versions")
def list_versions(page_id: int) -> JSONResponse:
    """Список версий страницы от новых к старым — без контента (design.md
    §3, §9); 404 — нет страницы."""
    conn = get_connection()
    try:
        if not _page_exists(conn, page_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        rows = conn.execute(
            "SELECT id, author_id, created_at FROM page_versions"
            " WHERE page_id = ? ORDER BY id DESC",
            (page_id,),
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse(
        content={
            "versions": [
                {"id": row[0], "author_id": row[1], "created_at": row[2]}
                for row in rows
            ]
        }
    )


def _version_content(
    conn: sqlite3.Connection, page_id: int, version_id: int
) -> tuple[str, int] | None:
    row = conn.execute(
        "SELECT content, author_id FROM page_versions"
        " WHERE id = ? AND page_id = ?",
        (version_id, page_id),
    ).fetchone()
    return (row[0], row[1]) if row is not None else None


@router.get("/pages/{page_id}/versions/{version_id}")
def get_version(page_id: int, version_id: int) -> JSONResponse:
    """Контент конкретной версии (read-only, design.md §3); 404 — нет
    страницы или версия чужой страницы."""
    conn = get_connection()
    try:
        if not _page_exists(conn, page_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        found = _version_content(conn, page_id, version_id)
        if found is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
    finally:
        conn.close()
    return JSONResponse(
        content={
            "id": version_id,
            "page_id": page_id,
            "content": found[0],
            "author_id": found[1],
        }
    )


@router.post("/pages/{page_id}/revert/{version_id}")
def revert_page(page_id: int, version_id: int, request: Request) -> JSONResponse:
    """Откат версии (FR-113, design.md §3): контент версии становится
    текущим + НОВАЯ версия (автор — исполнитель отката); история не
    переписывается; 404 — нет страницы/версии."""
    conn = get_connection()
    try:
        if not _page_exists(conn, page_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        found = _version_content(conn, page_id, version_id)
        if found is None:
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        author_id = _session_user_id(conn, request)
        if author_id is None:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        # Контент версии уже санитизирован на записи (§4); повторный прогон —
        # страховка от «грязных» данных прошлых эпох/ручных правок БД.
        content = sanitize_html(found[0])
        new_version_id = _insert_version(conn, page_id, content, author_id)
        conn.execute(
            "UPDATE pages SET content = ?, updated_at = ? WHERE id = ?",
            (content, _utcnow(), page_id),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"new_version_id": new_version_id})


@router.get("/search")
def search_pages(q: str, request: Request) -> JSONResponse:
    """LIKE-поиск (design.md §3, §6): %q% по title и content, экранирование
    %_\\ с ESCAPE '\\'; сниппет (окно ±60, оффсет+длина совпадения), path;
    ORDER BY updated_at DESC, LIMIT 20; 422 — пустой q."""
    if not q.strip():
        return JSONResponse(
            status_code=422,
            content={"error": "validation error", "details": "q must not be empty"},
        )
    conn = get_connection()
    try:
        pattern = f"%{_escape_like(q)}%"
        rows = conn.execute(
            "SELECT id, title, content, updated_at FROM pages"
            " WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'"
            " ORDER BY updated_at DESC, id DESC LIMIT ?",
            (pattern, pattern, SEARCH_LIMIT),
        ).fetchall()
        needle = q.lower()
        results = []
        for row in rows:
            # Сниппет по PLAIN-ТЕКСТУ (мокап: «…итоговая смета на материалы…»
            # без тегов, DV-1 review-001): HTML-теги срезаются до вычисления
            # окна и оффсета — клиент вставляет сниппет как текст, «<p>» и
            # прочая разметка в выдачу не попадают, match_offset/match_length
            # всегда в координатах plain-текста (подсветка не «разрезает» тег).
            plain = _strip_tags(row[2])
            pos = plain.lower().find(needle)
            snippet_start = max(0, (0 if pos < 0 else pos) - SNIPPET_WINDOW)
            match_offset = max(0, pos)
            snippet = plain[snippet_start : match_offset + len(q) + SNIPPET_WINDOW]
            results.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "path": _path_string(conn, row[0]),
                    "snippet": snippet,
                    "match_offset": match_offset - snippet_start if pos >= 0 else -1,
                    "match_length": len(q) if pos >= 0 else 0,
                }
            )
    finally:
        conn.close()
    return JSONResponse(content={"results": results})


@router.delete("/pages/{page_id}")
def delete_page(page_id: int) -> JSONResponse:
    """Удаление листа (FR-116, ОВ-2): 409 при наличии дочерних; иначе
    удаление — версии уходят по FK ON DELETE CASCADE (design.md §1)."""
    conn = get_connection()
    try:
        if not _page_exists(conn, page_id):
            return JSONResponse(status_code=404, content=NOT_FOUND_BODY)
        if _has_children(conn, page_id):
            return JSONResponse(
                status_code=409,
                content={"error": "page has child pages"},
            )
        conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"ok": True})
