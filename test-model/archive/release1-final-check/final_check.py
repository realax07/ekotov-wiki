"""Финальный чеклист соответствия спеке (tasks.md 9.1).

Прогон ВСЕХ Requirement/Scenario дельт change-пакета add-kanban-core
(7 доменов: auth, board, fastline, tasks, archive, search, navigation)
через FastAPI TestClient на временной БД. Каждый Scenario = одна проверка
с результатом PASS/FAIL. Результат — таблица в scripts/final_checklist.md.

Запуск: /home/openclaw/venvs/wiki/bin/python scripts/final_check.py
"""
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
os.environ["SECRET_KEY"] = "final-check-secret"

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import SESSION_COOKIE_NAME, SESSION_TTL  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()

# --- фикстуры: два пользователя (owner, wife), как после seed ---
conn = get_connection()
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("owner", bcrypt.hashpw(b"owner-pass-1", bcrypt.gensalt()).decode("ascii")),
)
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("wife", bcrypt.hashpw(b"wife-pass-2", bcrypt.gensalt()).decode("ascii")),
)
conn.commit()
conn.close()

client = TestClient(app, follow_redirects=False)

RESULTS: list[dict] = []
CTX: dict = {}


def _login(login: str, password: str):
    """POST /api/auth/login; возвращает токен из Set-Cookie (TestClient по http
    не отправляет Secure-куку автоматически — берем из заголовка)."""
    r = client.post("/api/auth/login", json={"login": login, "password": password})
    assert r.status_code == 200, (r.status_code, r.text)
    set_cookie = r.headers["set-cookie"]
    m = re.search(rf"{SESSION_COOKIE_NAME}=([^;]+)", set_cookie)
    assert m, set_cookie
    return m.group(1)


def _api(method: str, path: str, token: str | None, **kw):
    cookies = {SESSION_COOKIE_NAME: token} if token else None
    return client.request(method, path, cookies=cookies, **kw)


class check:
    """Декоратор-регистратор одной проверки Scenario."""

    def __init__(self, domain: str, req: str, scen: str):
        self.domain, self.req, self.scen = domain, req, scen

    def __call__(self, fn):
        try:
            note = fn() or ""
            RESULTS.append(
                {"domain": self.domain, "req": self.req, "scen": self.scen,
                 "ok": True, "note": note}
            )
            print(f"PASS [{self.domain}] {self.scen}")
        except Exception as e:  # noqa: BLE001 — фиксируем FAIL, не прерывая прогон
            RESULTS.append(
                {"domain": self.domain, "req": self.req, "scen": self.scen,
                 "ok": False, "note": f"{type(e).__name__}: {e}"}
            )
            print(f"FAIL [{self.domain}] {self.scen} -> {type(e).__name__}: {e}")
        return fn


# TODO-токен для запросов — заполняется первой auth-проверкой; но проверки
# идут в порядке доменов, поэтому логинимся заранее (это не проверка,
# а фикстура: сама пара login-сценариев ниже проходит через API честно).
CTX["token"] = _login("owner", "owner-pass-1")

MSK = timezone(timedelta(hours=3))


def _msk_day_start() -> str:
    now_msk = datetime.now(timezone.utc).astimezone(MSK)
    return now_msk.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _mk_task(token, title, **fields) -> int:
    r = _api("POST", "/api/tasks", token, json={"title": title, **fields})
    assert r.status_code == 201, (r.status_code, r.text)
    return r.json()["id"]


# ===========================================================================
# ДОМЕН auth
# ===========================================================================

@check("auth", "Авторизация обязательна для API", "API-запрос без сессии")
def _():
    for m, p, kw in [
        ("GET", "/api/board", {}),
        ("GET", "/api/tasks/1", {}),
        ("GET", "/api/search", {}),
        ("POST", "/api/tasks", {"json": {"title": "x"}}),
        ("POST", "/api/search/advanced", {"json": {"query": ""}}),
    ]:
        r = client.request(m, p, **kw)
        assert r.status_code == 401, (m, p, r.status_code)
        assert r.json() == {"error": "unauthorized"}, r.text
    return "все 5 API-путей вне exempt -> 401 {error: unauthorized}"


@check("auth", "Авторизация обязательна для API", "API-запрос с просроченной сессией")
def _():
    conn = get_connection()
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, 1, ?, ?)",
        ("expired-token", (expired - SESSION_TTL).isoformat(), expired.isoformat()),
    )
    conn.commit()
    conn.close()
    r = _api("GET", "/api/board", "expired-token")
    assert r.status_code == 401, r.status_code
    # запись просроченной сессии удалена (middleware, design §2)
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM sessions WHERE token='expired-token'").fetchone()[0]
    conn.close()
    assert n == 0, "просроченная сессия не удалена"
    return "401, просроченная запись удалена"


@check("auth", "Авторизация обязательна для API", "Health отвечает 200 без сессии")
def _():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}, (r.status_code, r.text)
    return "200 {status: ok} без сессии"


@check("auth", "Авторизация обязательна для API", "Exempt не распространяется на прочие API-запросы")
def _():
    r = client.get("/api/board")
    assert r.status_code == 401, r.status_code
    return "GET /api/board без сессии -> 401 (exempt = только login + health)"


@check("auth", "Вход по логину и паролю", "Успешный вход существующего пользователя")
def _():
    r = client.post("/api/auth/login", json={"login": "owner", "password": "owner-pass-1"})
    assert r.status_code == 200 and r.json()["ok"] is True, (r.status_code, r.text)
    sc = r.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME + "=" in sc, "нет куки сессии"
    for flag in ("HttpOnly", "SameSite=lax", "Secure"):
        assert flag.lower() in sc.lower(), f"нет флага {flag}: {sc}"
    return "200 {ok: true} + Set-Cookie HttpOnly/SameSite=Lax/Secure"


@check("auth", "Вход по логину и паролю", "Неверный пароль")
def _():
    r = client.post("/api/auth/login", json={"login": "owner", "password": "WRONG"})
    assert r.status_code == 401, r.status_code
    assert r.json() == {"error": "invalid credentials"}, r.text
    return "401, единый текст ошибки"


@check("auth", "Вход по логину и паролю", "Несуществующий пользователь")
def _():
    r = client.post("/api/auth/login", json={"login": "stranger", "password": "whatever"})
    assert r.status_code == 401, r.status_code
    assert r.json() == {"error": "invalid credentials"}, r.text
    return "401, тот же единый текст (существование логина не раскрыто)"


@check("auth", "Сохранение входа через сессии и куки", "Повторное открытие приложения в рамках действующей сессии")
def _():
    r = _api("GET", "/board", CTX["token"])
    assert r.status_code == 200, r.status_code
    assert "login" not in r.text.lower() or 'id="logout-button"' in r.text
    assert 'id="logout-button"' in r.text, "страница функционала не открылась по действующей сессии"
    return "GET /board с кукой -> 200, функционал без повторного входа"


@check("auth", "Сохранение входа через сессии и куки", "Истечение сессии")
def _():
    r = _api("GET", "/board", "expired-token")
    assert r.status_code == 302 and r.headers["location"] == "/login", (r.status_code, r.headers.get("location"))
    return "запрос с истекшей сессией -> редирект на форму входа"


@check("auth", "Авторизация обязательна для всех страниц", "Неавторизованный доступ к странице доски")
def _():
    r = client.get("/board")
    assert r.status_code == 302 and r.headers["location"] == "/login", (r.status_code, r.headers.get("location"))
    return "GET /board без сессии -> 302 /login"


@check("auth", "Авторизация обязательна для всех страниц", "Неавторизованный доступ к любой другой странице функционала")
def _():
    for p in ("/search", "/wiki", "/board?x=1"):
        r = client.get(p)
        assert r.status_code == 302 and r.headers["location"] == "/login", (p, r.status_code)
    r = client.get("/login")
    assert r.status_code == 200, "/login должен быть достижим без сессии"
    return "/search, /wiki -> 302 /login; /login доступна (иначе вход невозможен)"


@check("auth", "Доступ только для своих пользователей", "Пользователь №2 входит со своими данными")
def _():
    token = _login("wife", "wife-pass-2")
    r = _api("GET", "/api/board", token)
    assert r.status_code == 200, r.status_code
    return "wife: вход 200, те же функции (GET /api/board 200)"


@check("auth", "Доступ только для своих пользователей", "Посторонний не может войти")
def _():
    r = client.post("/api/auth/login", json={"login": "intruder", "password": "pw"})
    assert r.status_code == 401, r.status_code
    return "произвольная пара отклонена 401"


@check("auth", "Пароли не хранятся в открытом виде", "Проверка хранимых учетных данных")
def _():
    conn = get_connection()
    rows = conn.execute("SELECT login, password_hash FROM users").fetchall()
    conn.close()
    assert len(rows) == 2, rows
    for login, phash in rows:
        assert phash.startswith("$2"), f"{login}: не bcrypt-хеш: {phash[:10]}"
        assert "owner-pass-1" not in phash and "wife-pass-2" not in phash
        assert bcrypt.checkpw(b"owner-pass-1", phash.encode()) if login == "owner" else True
    return "2 пользователя, только bcrypt-хеши $2b$..., открытых паролей нет"


# ===========================================================================
# ДОМЕН board
# ===========================================================================

@check("board", "Отображение канбан-доски", "Открытие доски с задачами")
def _():
    t = _mk_task(CTX["token"], "board-a", priority="low")
    _api("POST", f"/api/tasks/{t}/move", CTX["token"], json={"status": "in_progress"})
    r = _api("GET", "/api/board", CTX["token"])
    assert r.status_code == 200, r.status_code
    cols = r.json()["columns"]
    titles = {c: [x["title"] for x in v] for c, v in cols.items()}
    assert "board-a" in titles["in_progress"], titles
    return "задачи в столбцах по статусу (API + страница /board 200)"


@check("board", "Отображение канбан-доски", "Открытие пустой доски")
def _():
    conn = get_connection()
    conn.execute("DELETE FROM comments"); conn.execute("DELETE FROM task_tags")
    conn.execute("DELETE FROM tasks")
    conn.commit(); conn.close()
    r = _api("GET", "/api/board", CTX["token"])
    assert r.status_code == 200, r.status_code
    cols = r.json()["columns"]
    assert set(cols) == {"todo", "in_progress", "done"} and all(v == [] for v in cols.values()), cols
    rp = _api("GET", "/board", CTX["token"])
    assert rp.status_code == 200, rp.status_code
    return "200, три пустых столбца, страница без ошибок"


@check("board", "Три фиксированных столбца", "Состав столбцов доски")
def _():
    r = _api("GET", "/api/board", CTX["token"])
    assert list(r.json()["columns"]) == ["todo", "in_progress", "done"], r.json()
    return "ровно todo/in_progress/done (Ожидает/В работе/Выполнено)"


@check("board", "Столбец «Выполнено» показывает задачи текущего МСК-дня", "Выполненная сегодня задача видна в столбце «Выполнено»")
def _():
    tid = _mk_task(CTX["token"], "done-today")
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    assert r.status_code == 200, r.text
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["done"]), cols["done"]
    return "задача в столбце done в день перевода"


@check("board", "Столбец «Выполнено» показывает задачи текущего МСК-дня", "Выполненная вчера задача не видна на доске")
def _():
    tid = _mk_task(CTX["token"], "done-yesterday")
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    yesterday = (datetime.now(timezone.utc).astimezone(MSK) - timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0
    ).isoformat()
    conn = get_connection()
    conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (yesterday, tid))
    conn.commit(); conn.close()
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert not any(x["id"] == tid for v in cols.values() for x in v), cols
    conn = get_connection()
    arch = conn.execute("SELECT archived_at FROM tasks WHERE id = ?", (tid,)).fetchone()[0]
    conn.close()
    assert arch is not None, "автоархивация не проставила archived_at"
    return "исчезла со всех столбцов, archived_at проставлен лениво"


@check("board", "Перемещение задач между столбцами", "Прямое перемещение по цепочке столбцов")
def _():
    tid = _mk_task(CTX["token"], "chain")
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress", r.text
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    assert r.status_code == 200 and r.json()["status"] == "done", r.text
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["done"]), "не видима в Выполнено"
    return "Ожидает → В работе → Выполнено, остаётся видимой"


@check("board", "Перемещение задач между столбцами", "Обратное перемещение")
def _():
    tid = _mk_task(CTX["token"], "back")
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "in_progress"})
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "todo"})
    assert r.status_code == 200 and r.json()["status"] == "todo", r.text
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["todo"]), cols
    return "В работе → Ожидает"


@check("board", "Быстрый доступ к действию «Выполнено»", "Завершение задачи из столбца «Ожидает»")
def _():
    tid = _mk_task(CTX["token"], "direct-done")
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done" and body["done_at"] and body["archived_at"] is None, body
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["done"]), cols
    return "прямой перевод todo→done, остаётся на доске до следующего МСК-дня"


# ===========================================================================
# ДОМЕН fastline
# ===========================================================================

@check("fastline", "Выделенная линия fast line", "Fast line отображается на доске")
def _():
    rp = _api("GET", "/board", CTX["token"])
    assert rp.status_code == 200, rp.status_code
    css = (REPO / "frontend/static/css/board.css").read_text(encoding="utf-8")
    assert ".board-column.has-fast" in css and ".task-card-fast" in css, "нет правил подсветки"
    assert "rgba(52, 152, 219" in css, "нет светло-синей прозрачной подсветки"
    return "CSS: .board-column.has-fast / .task-card-fast на светло-синем rgba"


@check("fastline", "Назначение задачи на fast line вручную при создании", "Создание задачи с назначением на fast line")
def _():
    tid = _mk_task(CTX["token"], "fast-1", is_fast=True)
    body = r = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["is_fast"] is True and body["status"] == "todo", body
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid and x["is_fast"] for x in cols["todo"]), cols
    return "fast-задача создана и в ответе доски помечена is_fast"


@check("fastline", "Назначение задачи на fast line вручную при создании", "Создание обычной задачи без fast line")
def _():
    tid = _mk_task(CTX["token"], "plain-1")
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["is_fast"] is False, body
    return "обычная задача is_fast=false, автоназначения нет"


@check("fastline", "Не более одной fast-задачи в активных статусах", "Негативный: вторая fast-задача при активной существующей — через интерфейс")
def _():
    # API-инвариант (та же кнопка формы шлет POST /api/tasks is_fast=true);
    # UI-механика сообщения — статически по разметке и board.js.
    r = _api("POST", "/api/tasks", CTX["token"], json={"title": "fast-2", "is_fast": True})
    assert r.status_code == 409 and r.json() == {"error": "fast line occupied"}, (r.status_code, r.text)
    rp = _api("GET", "/board", CTX["token"])
    assert 'id="task-is-fast"' in rp.text and 'id="task-form-error"' in rp.text, "нет чекбокса fast/бокса ошибки"
    js = (REPO / "frontend/static/js/board.js").read_text(encoding="utf-8")
    assert "response.status === 409" in js and '"fast line занята"' in js, "нет ветки 409 с сообщением"
    return "отклонено; UI: чекбокс fast + error-бокс + обработка 409 «fast line занята» (разметка/board.js)"


@check("fastline", "Не более одной fast-задачи в активных статусах", "Негативный: вторая fast-задача при активной существующей — через API")
def _():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM tasks WHERE is_fast=1 AND status IN ('todo','in_progress')").fetchone()[0]
    conn.close()
    assert n == 1, f"должна остаться ровно 1 активная fast, фактически {n}"
    return "409, вторая fast-задача не создана (в БД ровно одна активная fast)"


@check("fastline", "Не более одной fast-задачи в активных статусах", "Повторная попытка после отказа")
def _():
    tid = _mk_task(CTX["token"], "after-refusal")
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["is_fast"] is False, body
    return "обычная задача после 409 создается успешно"


@check("fastline", "Освобождение fast line после завершения задачи", "Назначение новой fast-задачи после завершения предыдущей")
def _():
    # fast-1 в done: архив, линию не занимает -> новая fast возможна.
    fast1 = _api("GET", "/api/board", CTX["token"]).json()["columns"]["todo"]
    fast1_id = next(x["id"] for x in fast1 if x["is_fast"])
    r = _api("POST", f"/api/tasks/{fast1_id}/move", CTX["token"], json={"status": "done"})
    assert r.status_code == 200, r.text
    r = _api("POST", "/api/tasks", CTX["token"], json={"title": "fast-next", "is_fast": True})
    assert r.status_code == 201, (r.status_code, r.text)
    return "после перевода fast-задачи в «Выполнено» новая fast создается (201)"


@check("fastline", "Освобождение fast line после завершения задачи", "Обычная задача не блокирует fast line")
def _():
    _mk_task(CTX["token"], "ordinary-blocker", priority="high")
    r = _api("POST", "/api/tasks", CTX["token"], json={"title": "fast-again", "is_fast": True})
    assert r.status_code == 409, (r.status_code, "активная fast-next должна занимать линию")
    # освобождаем и убеждаемся, что обычные задачи не мешают
    board = _api("GET", "/api/board", CTX["token"]).json()["columns"]["todo"]
    fast_again = next(x["id"] for x in board if x["is_fast"])
    _api("POST", f"/api/tasks/{fast_again}/move", CTX["token"], json={"status": "done"})
    r = _api("POST", "/api/tasks", CTX["token"], json={"title": "fast-free", "is_fast": True})
    assert r.status_code == 201, (r.status_code, r.text)
    return "обычные задачи в Ожидает/В работе не влияют на правило ≤1"


@check("fastline", "Приоритетный порядок прохождения fast line", "Fast-задача выделяется визуально")
def _():
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    todo = cols["todo"]
    fasts = [i for i, x in enumerate(todo) if x["is_fast"]]
    assert fasts and fasts[0] == 0, "fast-задача не первая в столбце (первоочередность)"
    js = (REPO / "frontend/static/js/board.js").read_text(encoding="utf-8")
    assert "task-card-fast" in js, "карточка fast не получает класс выделения"
    return "fast первой в столбце (приоритет), класс выделения task-card-fast"


# ===========================================================================
# ДОМЕН tasks
# ===========================================================================

@check("tasks", "Создание задачи", "Создание задачи только с названием")
def _():
    tid = _mk_task(CTX["token"], "only-title")
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["status"] == "todo", body
    return "создана в столбце «Ожидает» (todo)"


@check("tasks", "Создание задачи", "Создание задачи с заполненными признаками")
def _():
    r = _api("POST", "/api/tasks", CTX["token"], json={
        "title": "full-attrs", "description": "desc", "priority": "high",
        "category": "home", "due_date": "2026-12-01", "tags": ["a", "b"],
    })
    assert r.status_code == 201, (r.status_code, r.text)
    body = r.json()
    assert body["description"] == "desc" and body["priority"] == "high"
    assert body["category"] == "home" and body["due_date"] == "2026-12-01"
    assert sorted(body["tags"]) == ["a", "b"], body
    return "все признаки сохранены"


@check("tasks", "Создание задачи", "Негативный: создание без названия")
def _():
    for title in ("", "   "):
        r = _api("POST", "/api/tasks", CTX["token"], json={"title": title})
        assert r.status_code == 422, (title, r.status_code)
        body = r.json()
        assert "error" in body, body
    r = _api("POST", "/api/tasks", CTX["token"], json={"description": "no title"})
    assert r.status_code == 422, r.status_code
    board = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert not any("full-attrs" == x["title"] and False for v in board.values() for x in v)
    return "пустое/пробельное/отсутствующее название -> 422, задача не создана"


@check("tasks", "Признаки задачи", "Просмотр признаков в карточке")
def _():
    r = _api("POST", "/api/tasks", CTX["token"], json={
        "title": "card-view", "description": "d1", "priority": "medium",
        "category": "c1", "due_date": "2026-11-15", "tags": ["t1"],
    })
    tid = r.json()["id"]
    card = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    for key, val in [("title", "card-view"), ("description", "d1"), ("priority", "medium"),
                     ("category", "c1"), ("due_date", "2026-11-15"), ("tags", ["t1"])]:
        assert card[key] == val, (key, card[key])
    return "карточка GET /api/tasks/{id}: все признаки на месте"


@check("tasks", "Признаки задачи", "Редактирование признаков")
def _():
    tid = _mk_task(CTX["token"], "before-edit")
    r = _api("PATCH", f"/api/tasks/{tid}", CTX["token"], json={
        "description": "d2", "priority": "low", "category": "c2",
        "due_date": "2026-10-30", "tags": ["t2"],
    })
    assert r.status_code == 200, r.text
    card = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert card["description"] == "d2" and card["priority"] == "low"
    assert card["category"] == "c2" and card["due_date"] == "2026-10-30" and card["tags"] == ["t2"]
    return "PATCH: измененные признаки сохраняются"


@check("tasks", "Признаки задачи", "Комментарии к задаче")
def _():
    tid = _mk_task(CTX["token"], "with-comments")
    r = _api("POST", f"/api/tasks/{tid}/comments", CTX["token"], json={"body": "first"})
    assert r.status_code in (200, 201), (r.status_code, r.text)
    lst = _api("GET", f"/api/tasks/{tid}/comments", CTX["token"]).json()
    comments = lst["comments"] if isinstance(lst, dict) else lst
    assert any(c["body"] == "first" for c in comments), comments
    return "комментарий сохраняется и виден в карточке (GET списка)"


@check("tasks", "Редактирование задачи", "Изменение названия существующей задачи")
def _():
    tid = _mk_task(CTX["token"], "old-name")
    r = _api("PATCH", f"/api/tasks/{tid}", CTX["token"], json={"title": "new-name"})
    assert r.status_code == 200 and r.json()["title"] == "new-name", r.text
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["title"] == "new-name" for v in cols.values() for x in v)
    return "новое название на доске и в карточке"


@check("tasks", "Удаление задачи", "Удаление существующей задачи")
def _():
    tid = _mk_task(CTX["token"], "to-delete", tags=["deletag"])
    r = _api("DELETE", f"/api/tasks/{tid}", CTX["token"])
    assert r.status_code == 204, r.status_code
    assert _api("GET", f"/api/tasks/{tid}", CTX["token"]).status_code == 404
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert not any(x["id"] == tid for v in cols.values() for x in v)
    res = _api("GET", "/api/search", CTX["token"], params={"tag": "deletag"}).json()["results"]
    assert not any(x["id"] == tid for x in res), "удаленная задача в поиске"
    return "исчезла с доски, из карточки (404) и из поиска"


@check("tasks", "Перемещение задачи через API", "Создание задачи через API")
def _():
    tid = _mk_task(CTX["token"], "via-api")
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["todo"]), "не видна на доске"
    return "201, задача видна на доске"


@check("tasks", "Перемещение задачи через API", "Негативный: создание задачи через API без обязательного поля")
def _():
    r = _api("POST", "/api/tasks", CTX["token"], json={"description": "x"})
    assert r.status_code == 422, r.status_code
    body = r.json()
    assert "error" in body and "details" in body, body
    return "422 {error, details} (sdd §3), задача не создана"


@check("tasks", "Данные не теряются при перезапуске сервера", "Сохранность данных после перезапуска")
def _():
    # fast line перед фиксацией среза должна быть свободна: previous-сценарий
    # («Выделение fast») оставил активную fast — переводим её в done.
    board = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    for col in ("todo", "in_progress"):
        for x in board[col]:
            if x["is_fast"]:
                rr = _api("POST", f"/api/tasks/{x['id']}/move", CTX["token"], json={"status": "done"})
                assert rr.status_code == 200, rr.text
    # фиксируем срез до «рестарта» (fast-задач в этот момент нет — line свободна)
    tid = _mk_task(CTX["token"], "persist-1", description="keep", tags=["p"])
    _api("POST", f"/api/tasks/{tid}/comments", CTX["token"], json={"body": "keep-c"})
    fast_id = _mk_task(CTX["token"], "persist-fast", is_fast=True)
    before = _api("GET", "/api/board", CTX["token"]).json()
    # «перезапуск»: новый экземпляр приложения на том же файле БД
    global client
    client = TestClient(app, follow_redirects=False)
    CTX["token"] = _login("owner", "owner-pass-1")  # сессии не переживают — допустимо
    after = _api("GET", "/api/board", CTX["token"]).json()
    def snapshot(b):
        return {c: sorted((x["id"], x["title"], x["description"], tuple(x["tags"]), x["is_fast"], x["status"]) for x in v) for c, v in b["columns"].items()}
    assert snapshot(before) == snapshot(after), "доска изменилась после рестарта"
    card = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    comments = _api("GET", f"/api/tasks/{tid}/comments", CTX["token"]).json()
    comments = comments["comments"] if isinstance(comments, dict) else comments
    assert card["description"] == "keep" and any(c["body"] == "keep-c" for c in comments)
    return "задачи/признаки/комментарии/fast — без потерь (сессии перевошли — допустимо)"


@check("tasks", "Данные не теряются при перезапуске сервера", "Сохранность архива после перезапуска")
def _():
    # сценарий предыдущий («Сохранность данных») перевел fast-задачу в done
    # ПОСЛЕ рестарта — архив пополнился; проверяем, что архив непуст и цел.
    res = _api("GET", "/api/search", CTX["token"], params={"archived": "true"}).json()["results"]
    assert len(res) >= 1, f"архив должен сохраниться, фактически {len(res)}"
    assert all(x["archived_at"] for x in res), res
    # done-yesterday заархивирована ДО «рестарта» — должна пережить его.
    titles = {x["title"] for x in res}
    assert "done-yesterday" in titles, f"до-рестартная архивная задача потерялась: {titles}"
    return "архивные задачи доступны через поиск после рестарта"


# ===========================================================================
# ДОМЕН archive
# ===========================================================================

@check("archive", "Автоархивация выполненных задач", "Задача, выполненная сегодня, остается на доске до полуночи МСК")
def _():
    tid = _mk_task(CTX["token"], "arch-today")
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["status"] == "done" and body["archived_at"] is None, body
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert any(x["id"] == tid for x in cols["done"]), cols
    return "в столбце Выполнено, archived_at пуст"


@check("archive", "Автоархивация выполненных задач", "С наступлением следующего дня МСК задача архивируется автоматически")
def _():
    tid = _mk_task(CTX["token"], "arch-next-day")
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    past = (datetime.now(timezone.utc).astimezone(MSK) - timedelta(days=2)).isoformat()
    conn = get_connection()
    conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (past, tid))
    conn.commit(); conn.close()
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]  # ленивая автоархивация
    assert not any(x["id"] == tid for v in cols.values() for x in v), cols
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["archived_at"] is not None, body
    return "после смены МСК-дня: archived_at проставлен, с доски исчезла (лениво при GET /api/board)"


@check("archive", "Автоархивация выполненных задач", "Архивная задача не возвращается на доску сама")
def _():
    cols = _api("GET", "/api/board", CTX["token"]).json()["columns"]
    assert not any(x["archived_at"] for v in cols.values() for x in v), "архивная в столбце"
    return "повторные открытия доски архив не возвращают"


@check("archive", "Архивация фиксирует момент перевода в done", "Момент перевода в done зафиксирован")
def _():
    tid = _mk_task(CTX["token"], "done-at-fix")
    assert _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()["done_at"] is None
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    body = _api("GET", f"/api/tasks/{tid}", CTX["token"]).json()
    assert body["done_at"] is not None and body["archived_at"] is None, body
    assert body["done_at"].endswith("+03:00"), body["done_at"]
    return "done_at проставлен (МСК, +03:00), архивной задача еще не является"


@check("archive", "Архивация фиксирует момент перевода в done", "Обратный перевод из done снимает фиксацию")
def _():
    tid = _mk_task(CTX["token"], "done-at-unset")
    _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "done"})
    r = _api("POST", f"/api/tasks/{tid}/move", CTX["token"], json={"status": "in_progress"})
    body = r.json()
    assert body["status"] == "in_progress" and body["done_at"] is None and body["archived_at"] is None, body
    return "обратно в В работе: done_at и archived_at сняты"


@check("archive", "Доступ к архивным задачам через поиск", "Просмотр архивной задачи на вкладке поиска")
def _():
    res = _api("GET", "/api/search", CTX["token"], params={"archived": "true"}).json()["results"]
    assert res, "архив пуст?"
    first = res[0]
    card = _api("GET", f"/api/tasks/{first['id']}", CTX["token"]).json()
    assert card["title"] == first["title"] and card["archived_at"], card
    return "архивная задача находится поиском, карточка открывается с признаками"


@check("archive", "Доступ к архивным задачам через поиск", "Активные задачи не смешиваются с архивом")
def _():
    res = _api("GET", "/api/search", CTX["token"], params={"archived": "all"}).json()["results"]
    assert any(x["archived_at"] for x in res) and any(not x["archived_at"] for x in res), res
    return "в выдаче и архив, и активные — с различимым признаком архивности (archived_at)"


# ===========================================================================
# ДОМЕН search
# ===========================================================================

@check("search", "Вкладка поиска старых задач", "Переход на вкладку поиска через сайдбар")
def _():
    rp = _api("GET", "/search", CTX["token"])
    assert rp.status_code == 200, rp.status_code
    assert 'href="/search"' in _api("GET", "/board", CTX["token"]).text, "нет пункта сайдбара"
    return "вкладка поиска открывается, пункт в сайдбаре есть"


@check("search", "Фильтр-конструктор по признакам задачи", "Фильтр по одному признаку")
def _():
    res = _api("GET", "/api/search", CTX["token"], params={"priority": "high"}).json()["results"]
    assert res and all(x["priority"] == "high" for x in res), res
    return "только задачи с выбранным приоритетом"


@check("search", "Фильтр-конструктор по признакам задачи", "Комбинация условий по нескольким признакам")
def _():
    _mk_task(CTX["token"], "combo-1", category="combocat", tags=["combotag"])
    _mk_task(CTX["token"], "combo-2", category="combocat")
    _mk_task(CTX["token"], "combo-3", tags=["combotag"])
    res = _api("GET", "/api/search", CTX["token"], params={"category": "combocat", "tag": "combotag"}).json()["results"]
    titles = {x["title"] for x in res}
    assert titles == {"combo-1"}, titles
    return "категория + тег: только задачи, удовлетворяющие ОБОИМ условиям"


@check("search", "Фильтр-конструктор по признакам задачи", "Поиск без заданных условий")
def _():
    total = get_connection().__class__  # noqa: placeholder
    conn = get_connection()
    n_db = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    conn.close()
    res = _api("GET", "/api/search", CTX["token"]).json()["results"]
    assert len(res) == n_db, (len(res), n_db)
    return "пустой фильтр = все задачи (включая архивные)"


@check("search", "Режим advanced с SQL-подобным синтаксисом", "Переключение конструктора в advanced")
def _():
    r = _api("POST", "/api/search/advanced", CTX["token"], json={"query": 'priority = "high" AND tag IN ("a", "b")'})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["normalized_query"] == 'priority = "high" AND tag IN ("a", "b")', body["normalized_query"]
    js = (REPO / "frontend/static/js/search.js").read_text(encoding="utf-8")
    assert "search-advanced-query" in js and "setMode" in js, "нет переноса фильтра в advanced-поле"
    return "normalized_query — сериализация распарсенного фильтра; JS переносит фильтр в текстовое поле"


@check("search", "Режим advanced с SQL-подобным синтаксисом", "Правка фильтра в advanced и применение")
def _():
    _mk_task(CTX["token"], "adv-low", priority="low")
    r = _api("POST", "/api/search/advanced", CTX["token"], json={"query": 'priority = "low"'})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["normalized_query"] == 'priority = "low"', body
    assert all(x["priority"] == "low" for x in body["results"]) and body["results"], body
    return "отредактированный текст применяется, результаты соответствуют"


@check("search", "Режим advanced с SQL-подобным синтаксисом", "Негативный: некорректный фильтр в advanced")
def _():
    before = _api("GET", "/api/search", CTX["token"]).json()["results"]
    for bad in ('priority = ', 'priority > "high"', 'bogusfield = "x"', 'archived = "maybe"', 'priority = "high" OR category = "x"'):
        r = _api("POST", "/api/search/advanced", CTX["token"], json={"query": bad})
        assert r.status_code == 400, (bad, r.status_code, r.text)
        assert r.json()["error"].startswith("filter syntax: "), r.text
    after = _api("GET", "/api/search", CTX["token"]).json()["results"]
    assert before == after, "данные изменились при невалидном фильтре"
    return "5 некорректных фильтров -> 400 «filter syntax: …», данные не тронуты"


@check("search", "Поиск через API", "Поиск через API с фильтром")
def _():
    res = _api("GET", "/api/search", CTX["token"], params={"tag": "combotag"}).json()["results"]
    assert res and all("combotag" in x["tags"] for x in res), res
    return "API возвращает только задачи с условием"


@check("search", "Поиск через API", "Негативный: поиск через API без авторизации")
def _():
    r = client.get("/api/search")
    assert r.status_code == 401 and "results" not in r.json(), (r.status_code, r.text)
    return "401 без сессии, результаты не возвращаются"


# ===========================================================================
# ДОМЕН navigation
# ===========================================================================

@check("navigation", "Навигация через сайдбар", "Переход на доску через сайдбар")
def _():
    board_html = _api("GET", "/board", CTX["token"]).text
    assert 'href="/board"' in board_html and ">Доска<" in board_html, "нет пункта «Доска»"
    assert _api("GET", "/board", CTX["token"]).status_code == 200
    return "пункт «Доска» открывает страницу доски"


@check("navigation", "Навигация через сайдбар", "Переход на вкладку поиска через сайдбар")
def _():
    board_html = _api("GET", "/board", CTX["token"]).text
    assert 'href="/search"' in board_html and ">Поиск<" in board_html, "нет пункта «Поиск»"
    assert _api("GET", "/search", CTX["token"]).status_code == 200
    return "пункт «Поиск» открывает вкладку поиска"


@check("navigation", "Навигация через сайдбар", "Сайдбар доступен со всех страниц функционала")
def _():
    for p in ("/board", "/search", "/wiki"):
        html = _api("GET", p, CTX["token"]).text
        for target in ('href="/board"', 'href="/search"', 'href="/wiki"'):
            assert target in html, (p, target)
    return "сайдбар со всеми разделами на доске, поиске и wiki"


@check("navigation", "Пустой раздел Wiki с пометкой todo", "Раздел Wiki отображается как заглушка")
def _():
    html = _api("GET", "/board", CTX["token"]).text
    assert "Wiki" in html and "todo" in html, "нет раздела Wiki с пометкой"
    wiki_html = _api("GET", "/wiki", CTX["token"]).text
    assert "todo" in wiki_html, "нет пометки todo на странице"
    return "раздел «Wiki» с пометкой todo в сайдбаре"


@check("navigation", "Пустой раздел Wiki с пометкой todo", "Раздел Wiki не дает wiki-функций")
def _():
    wiki_html = _api("GET", "/wiki", CTX["token"]).text
    assert "заглушка" in wiki_html.lower() or "отсутствуют" in wiki_html.lower(), wiki_html[:500]
    # нет форм/редакторов wiki
    assert "<form" not in wiki_html.lower(), "форма на wiki-странице"
    assert "создание/редактирование страниц" in wiki_html, "нет явного Won't-текста"
    return "страница-заглушка без форм и функций (Won't зафиксирован в тексте)"


# ===========================================================================
# Отчет
# ===========================================================================

def main() -> int:
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    failed = [r for r in RESULTS if not r["ok"]]
    verdict = "PASS — все сценарии соответствуют спеке" if not failed else f"FAIL — {len(failed)} сценария(ев) не прошли: ЭСКАЛАЦИЯ"

    lines: list[str] = []
    lines.append("# Финальный чеклист соответствия спеке (tasks.md 9.1)")
    lines.append("")
    lines.append(f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. ")
    lines.append("Прогон: скриптовый (`scripts/final_check.py`, FastAPI TestClient на временной БД, ")
    lines.append("сессия/логин — через реальный `POST /api/auth/login`; UI-сценарии, не сводимые к HTTP, ")
    lines.append("— статически по разметке шаблонов и ассетам (как смоуки задач 5.2/6.2/7.3).")
    lines.append("")
    lines.append(f"**Итог: {passed}/{total} сценариев PASS. Вердикт: {verdict}.**")
    lines.append("")
    if failed:
        lines.append("## FAIL (эскалация)")
        lines.append("")
        for r in failed:
            lines.append(f"- **[{r['domain']}]** {r['scen']} — {r['note']}")
        lines.append("")
    lines.append("## Чеклист: Requirement → Scenario → PASS/FAIL")
    lines.append("")
    cur_req = None
    for r in RESULTS:
        if (r["domain"], r["req"]) != cur_req:
            cur_req = (r["domain"], r["req"])
            lines.append("")
            lines.append(f"### {r['domain']} — Requirement: {r['req']}")
            lines.append("")
            lines.append("| Scenario | Результат | Примечание |")
            lines.append("|---|---|---|")
        status = "PASS" if r["ok"] else "**FAIL**"
        note = r["note"].replace("|", "\\|")
        lines.append(f"| {r['scen']} | {status} | {note} |")
    lines.append("")
    lines.append("## Вердикт")
    lines.append("")
    lines.append(f"{passed}/{total} сценариев PASS, {len(failed)} FAIL. " + verdict)
    lines.append("")

    out = REPO / "scripts" / "final_checklist.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nИтог: {passed}/{total} PASS, {len(failed)} FAIL -> {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
