"""Smoke-проверка фикса integer-бага комментариев (dev, ui-fix).

S1: воспроизведение бага на TestClient: POST /api/tasks/null/comments -> 422
    (type=int_parsing). Это серверный контракт — он не менялся; JS-фикс
    исключает попадание UI на этот путь (см. S3).
S2: sanity: нормальный путь (создать задачу -> комментарий -> удалить) работает.
S3: статическая проверка JS: все вызовы submitComment/openTaskDetail/
    moveCurrentTask защищены guard'ом isValidTaskId — путь с null из UI
    недостижим.
"""
import os
import re
import sys

sys.path.insert(0, "/home/openclaw/ekotov-wiki/backend")
os.environ["DB_PATH"] = "/tmp/fix_smoke.db"
os.environ["SECRET_KEY"] = "0123456789abcdef0123456789abcdef"

from app.db import init_db  # noqa: E402
from app.seed_users import seed_user  # noqa: E402

init_db()
print("seed owner:", seed_user("owner", "owner", "QaOwner_Pass_1!"))
print("seed wife:", seed_user("wife", "wife", "QaWife_Pass_2!"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

# --- S1: воспроизведение исходного бага (серверный 422 на null) ---
# Кука session ставится с флагом Secure (sdd §3.1) — TestClient по http
# ее не хранит; повторяем браузерное поведение trustworthy origin
# (аналог LocalhostSession в tests/api/conftest.py).
from types import SimpleNamespace  # noqa: E402

_orig_post = client.post


def _post_unsecure(url, **kwargs):
    resp = _orig_post(url, **kwargs)
    for cookie in client.cookies.jar:  # http.cookiejar.Cookie objects
        cookie.secure = False
    return resp


client.post = _post_unsecure  # type: ignore[assignment]

r = client.post("/api/auth/login", json={"login": "owner", "password": "QaOwner_Pass_1!"})
assert r.status_code == 200, r.text
r = client.post("/api/tasks/null/comments", json={"body": "smoke"})
print("S1 POST /api/tasks/null/comments ->", r.status_code)
d = r.json()
details = d.get("details")
if isinstance(details, list) and details:
    first = details[0]
    print("   loc:", first.get("loc"), "| msg:", first.get("msg"), "| type:", first.get("type"))
assert r.status_code == 422, "ожидаем 422 на null (серверный контракт)"

# --- S2: sanity нормального пути ---
r = client.post("/api/tasks", json={"title": "smoke-fix"})
assert r.status_code == 201, r.text
tid = r.json()["id"]
r = client.post(f"/api/tasks/{tid}/comments", json={"body": "ok"})
print("S2 POST /api/tasks/{id}/comments ->", r.status_code)
assert r.status_code == 201
r = client.delete(f"/api/tasks/{tid}")
print("   cleanup DELETE ->", r.status_code)
assert r.status_code in (200, 204)

# --- S3: статическая проверка JS-гвардов ---
js = open("/home/openclaw/ekotov-wiki/frontend/static/js/board.js", encoding="utf-8").read()


def has_guard(fn_name: str) -> bool:
    m = re.search(r"function\s+" + fn_name + r"\s*\([^)]*\)\s*\{", js)
    if not m:
        return False
    body_start = m.end()
    # тело функции до следующей функции верхнего уровня — грубо, но
    # guard стоит первой строкой, поэтому смотрим первые 300 символов
    return "isValidTaskId" in js[body_start:body_start + 300]


for fn in ("openTaskDetail", "submitComment", "moveCurrentTask"):
    print(f"S3 guard in {fn}:", has_guard(fn))
    assert has_guard(fn), f"нет guard'а в {fn}"

# единственная точка записи currentTaskId числом — валидный путь
sets = re.findall(r"currentTaskId\s*=\s*([^;]+);", js)
print("S3 assignments to currentTaskId:", sorted(set(s.strip() for s in sets)))

print("SMOKE OK")
