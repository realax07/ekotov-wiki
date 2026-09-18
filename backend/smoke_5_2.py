"""Смоук-проверка задачи 5.2 (FR-3, ОГР-5): /board рендерится, fast-подсветка
и обработка 409 присутствуют в разметке/ассетах, порядок на линии — серверный.
Запуск: DB_PATH=... SECRET_KEY=... python backend/smoke_5_2.py (временная БД).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-5.2")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import create_session  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
conn = get_connection()
conn.execute("INSERT INTO users (login, password_hash) VALUES (?, ?)", ("smoke", "x"))
conn.commit()
token = create_session(conn, 1)
conn.commit()
conn.close()

client = TestClient(app)

# 1) Без сессии — редирект на /login (NFR-7, не трогаем).
r = client.get("/board", follow_redirects=False)
assert r.status_code == 302 and r.headers["location"] == "/login", (r.status_code, r.headers.get("location"))
print("OK  /board без сессии -> редирект на /login")

# 2) С сессией — 200 и в разметке есть чекбокс fast, error-бокс формы, ассеты.
r = client.get("/board", cookies={"session": token})
assert r.status_code == 200, r.status_code
for marker in ('id="task-is-fast"', 'id="task-form-error"', "/static/js/board.js", "/static/css/board.css"):
    assert marker in r.text, marker
print("OK  GET /board с сессией -> 200, чекбокс fast и error-бокс формы в разметке")

# 3) Создание fast + обычных задач; вторая fast -> 409 fast line occupied.
r = client.post("/api/tasks", json={"title": "fast high", "is_fast": True, "priority": "high"}, cookies={"session": token})
assert r.status_code == 201 or r.status_code == 200, (r.status_code, r.text)
r = client.post("/api/tasks", json={"title": "normal low", "priority": "low"}, cookies={"session": token})
assert r.status_code in (200, 201), r.status_code
r = client.post("/api/tasks", json={"title": "normal high", "priority": "high"}, cookies={"session": token})
assert r.status_code in (200, 201), r.status_code
r = client.post("/api/tasks", json={"title": "normal med", "priority": "medium"}, cookies={"session": token})
assert r.status_code in (200, 201), r.status_code

r = client.post("/api/tasks", json={"title": "second fast", "is_fast": True}, cookies={"session": token})
assert r.status_code == 409 and r.json() == {"error": "fast line occupied"}, (r.status_code, r.text)
print("OK  вторая fast-задача -> 409 {error: fast line occupied} (серверный инвариант 5.1)")

# 4) Порядок на линии — серверный: fast первым, далее по приоритету.
r = client.get("/api/board", cookies={"session": token})
todo = r.json()["columns"]["todo"]
order = [(t["title"], t["is_fast"], t["priority"]) for t in todo]
assert order == [
    ("fast high", True, "high"),
    ("normal high", False, "high"),
    ("normal med", False, "medium"),
    ("normal low", False, "low"),
], order
print("OK  порядок в столбце (сервер, sdd §3.3):", order)

# 5) CSS: светло-синяя прозрачная подсветка fast-линии и карточки.
#    Статика раздается nginx напрямую из frontend/static (deploy/nginx),
#    приложение ее не маунтит — проверяем файл на диске.
with open(os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "css", "board.css"), encoding="utf-8") as f:
    css = f.read()
assert ".board-column.has-fast" in css, "нет правила подсветки столбца"
assert ".task-card-fast" in css, "нет правила подсветки карточки"
assert "rgba(52, 152, 219, 0.1)" in css, "нет rgba светло-синего прозрачного"
print("OK  board.css: .board-column.has-fast и .task-card-fast на rgba(52,152,219, alpha)")

# 6) JS: классы подсветки при рендере + ветка 409 с сообщением.
with open(os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "js", "board.js"), encoding="utf-8") as f:
    js = f.read()
assert "task-card-fast" in js, "карточка не получает класс подсветки"
assert 'classList.toggle("has-fast", hasFast)' in js, "столбец не получает has-fast"
assert 'response.status === 409' in js, "нет ветки 409"
assert '"fast line занята"' in js, "нет сообщения пользователю"
assert 'body.error === "fast line occupied"' in js, "не проверяется тело 409"
print("OK  board.js: has-fast/task-card-fast при рендере; 409 fast line occupied -> «fast line занята»")

print("\nSMOKE 5.2: все проверки зеленые")
