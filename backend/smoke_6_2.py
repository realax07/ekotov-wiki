"""Смоук-проверка задачи 6.2: признак «архивная» в карточке (FR-4).

1) Архивная задача (move в done + ленивая автоархивация через
   подмененный done_at «вчера») → GET /api/tasks/{id} → archived_at
   IS NOT NULL в ответе.
2) Не-архивная задача → archived_at null.
3) HTML карточки: тег #task-detail-archive-badge присутствует в
   board.html; JS-логика рендера (renderTaskDetail) тогглит hidden
   по task.archived_at — проверяется в smoke_6_2_dom.js (jsdom).

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_6_2.py
"""

import os
import re
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-6.2")

import bcrypt
from fastapi.testclient import TestClient

from app.auth import create_session  # noqa: E402
from app.board import msk_now_iso  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")

init_db()
conn = get_connection()
_smoke_hash = bcrypt.hashpw(b"smoke-pass", bcrypt.gensalt())
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("smoke", _smoke_hash.decode("ascii")),
)
conn.commit()
token = create_session(conn, 1)
conn.close()

client = TestClient(app, base_url="https://test")
CK = {"cookies": {"session": token}}


def api(method, path, **kw):
    r = client.request(method, path, cookies=CK["cookies"], **kw)
    assert r.status_code < 500, (r.status_code, r.text)
    return r


failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL") + ": " + name)
    if not cond:
        failures.append(name)


# --- 1. Архивная: move в done + ленивая автоархивация (done_at вчера) ---
r = api("POST", "/api/tasks", json={"title": "архивная тест"})
assert r.status_code == 201, r.text
archived_id = r.json()["id"]
r = api("POST", f"/api/tasks/{archived_id}/move", json={"status": "done"})
assert r.status_code == 200, r.text

# Ленивая автоархивация сервера опирается на done_at < начала текущего
# МСК-дня: подменяем done_at на «вчера» в продакшн-формате +03:00
# (тот же прием, что в smoke_6_1.py; API-путей прямой простановки
# archived_at нет — это домен автоархивации 6.1).
yesterday = (
    datetime.fromisoformat(msk_now_iso()) - timedelta(days=1)
).isoformat()
c = get_connection()
c.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (yesterday, archived_id))
c.commit()
c.close()

r = api("GET", "/api/board")  # триггер ленивой автоархивации
assert r.status_code == 200
r = api("GET", f"/api/tasks/{archived_id}")
task = r.json()
check("архивная: GET /api/tasks/{id} → 200", r.status_code == 200)
check("архивная: archived_at IS NOT NULL в ответе", task.get("archived_at"))

# --- 2. Не-архивная: todo, archived_at отсутствует ---
r = api("POST", "/api/tasks", json={"title": "живая тест"})
assert r.status_code == 201, r.text
live_id = r.json()["id"]
r = api("GET", f"/api/tasks/{live_id}")
check("не-архивная: archived_at null в ответе", r.json().get("archived_at") is None)

# --- 3. Доска не показывает архивные (регрессия 4.3/6.1) ---
r = api("GET", "/api/board")
columns = r.json()["columns"]
board_ids = [t["id"] for col in columns.values() for t in col]
check("доска: архивная задача не в ответе", archived_id not in board_ids)
check("доска: не-архивная задача в столбце todo", live_id in board_ids)

# --- 4. HTML карточки: бейдж в разметке + JS-логика ---
with open(os.path.join(FRONTEND, "templates", "board.html"), encoding="utf-8") as f:
    html = f.read()
check(
    "board.html: бейдж «Архивная» присутствует (id + текст)",
    'id="task-detail-archive-badge"' in html and "Архивная" in html,
)
with open(os.path.join(FRONTEND, "static", "js", "board.js"), encoding="utf-8") as f:
    js = f.read()
check(
    "board.js: бейдж тогглится по archived_at (hidden = !task.archived_at)",
    bool(re.search(r"task-detail-archive-badge[^\n]*\n?\s*\.hidden\s*=\s*\n?\s*!task\.archived_at", js)),
)
check(
    "XSS: innerHTML не используется в рендере (только упоминание в комментарии шапки)",
    all(
        "textContent" in line or line.strip().startswith("*") or "не innerHTML" in line
        for line in js.splitlines()
        if "innerHTML" in line
    ),
)

print()
if failures:
    print("ИТОГ: FAIL — " + ", ".join(failures))
    sys.exit(1)
print("ИТОГ: все проверки 6.2 PASS")
