"""Смоук-проверка задачи 7.3: вкладка поиска в UI (sdd.md §3.5, §3.6).

Пункты локальной проверки задания 7.3 (TestClient): GET /search с сессией
→ 200 и страница содержит оба режима; без сессии → 302 (middleware);
регрессия: /board, /login, GET /api/board не сломаны.

DOM/JS-логика (query-string конструктора, POST {query}, 400/401/422,
XSS-рендер) — backend/smoke_7_3_dom.js (jsdom).

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_7_3.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-7.3")

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import create_session  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402

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

client = TestClient(app, base_url="https://test")  # кука Secure → https
CK = {"cookies": {"session": token}}

results = []


def check(n, name, cond, detail=""):
    results.append((n, name, cond, detail))
    print(f"{'PASS' if cond else 'FAIL'} {n}: {name} {detail}")


# 1) GET /search с сессией → 200, страница содержит оба режима
r = client.get("/search", **CK)
html = r.text
markers = [
    "search-mode-switch",       # переключатель режимов
    "search-mode-advanced",     # кнопка переключения на advanced
    "search-builder",           # режим конструктора
    "search-advanced",          # режим advanced (секция)
    "search-advanced-query",    # текстовое поле фильтра
    "search-priority", "search-category", "search-tags",
    "search-due-before", "search-due-after", "search-archived",
    "search-results",           # контейнер результатов
    "/static/js/search.js", "/static/css/search.css",
]
missing = [m for m in markers if m not in html]
check(1, "GET /search (сессия) → 200, оба режима в разметке",
      r.status_code == 200 and not missing,
      f"missing={missing}" if missing else f"{len(markers)} маркеров")

# 2) без сессии → 302 (middleware, sdd §3.6); follow_redirects=False —
# иначе httpx молча проходит редирект и возвращает 200 страницы входа.
r = client.get("/search", follow_redirects=False)
check(2, "GET /search (без сессии) → 302 на /login",
      r.status_code == 302 and "/login" in r.headers.get("location", ""),
      str(r.status_code) + " " + r.headers.get("location", ""))

# 7) Регрессия: доска/login не сломаны
r = client.get("/board", **CK)
check("7a", "GET /board (сессия) → 200, доска в разметке",
      r.status_code == 200 and "board" in r.text and "/static/js/board.js" in r.text)
r = client.get("/login")
check("7b", "GET /login → 200 (форма входа доступна без сессии)",
      r.status_code == 200 and "login-form" in r.text)
r = client.post("/api/auth/login", json={"login": "smoke", "password": "smoke-pass"})
check("7c", "POST /api/auth/login → 200",
      r.status_code == 200, str(r.status_code))
r = client.get("/api/board", **CK)
check("7d", "GET /api/board (сессия) → 200",
      r.status_code == 200, str(r.status_code))
r = client.get("/api/search", **CK)
check("7e", "GET /api/search (сессия) → 200 (7.1 цел)",
      r.status_code == 200, str(r.status_code))
r = client.post("/api/search/advanced", json={"query": 'priority = "high"'}, **CK)
check("7f", "POST /api/search/advanced → 200 + normalized_query (7.2 цел)",
      r.status_code == 200 and "normalized_query" in r.json(),
      str(r.status_code))

fails = [x for x in results if not x[2]]
print(f"\n{'ALL PASS' if not fails else f'FAILURES: {len(fails)}'} "
      f"({len(results)} проверок)")
sys.exit(1 if fails else 0)
