"""Смоук-проверка задач 4.4 (переработка) + 6.1 (sdd r5, FR-4 новая редакция).

Проверки постановки: move в done (реальный done_at из API); done_at
сегодня на доске; ленивая автоархивация по done_at вчера (сдвиг
внутри формата +03:00); обратный move; границы МСК-дня (23:59:59.999
вчера — архив; 00:00:00.000 сегодня — доска; БЛОКЕР-КЕЙС: done в
01:00 МСК по подмененным часам — задача остается на доске);
регрессия (login/health/CRUD/comments/fast-инвариант); миграция done_at.

Все подменяемые done_at — ТОЛЬКО в продакшн-формате «...+03:00»
(msk_now_iso/сдвиг datetime от него): строка «+00:00» маскировала
blocker review-6.1-001 (#2 review).

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_6_1.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-6.1")

import bcrypt
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import create_session  # noqa: E402
from app.board import msk_now_iso  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402

DB_PATH = os.environ["DB_PATH"]

init_db()
conn = get_connection()
# Валидный bcrypt-хеш (смок-пароль "smoke-pass"): login-проверка 6b
# выполняет bcrypt.checkpw — фейковый хеш уронил бы ее ValueError'ом.
_smoke_hash = bcrypt.hashpw(b"smoke-pass", bcrypt.gensalt())
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("smoke", _smoke_hash.decode("ascii")),
)
conn.commit()
token = create_session(conn, 1)
conn.close()

# base_url https (кука Secure — plain http TestClient не сохранит сессию)
client = TestClient(app, base_url="https://test")
CK = {"cookies": {"session": token}}


def db_task(task_id):
    c = get_connection()
    try:
        row = c.execute(
            "SELECT status, done_at, archived_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    finally:
        c.close()
    return row


def make_task(title, **extra):
    r = client.post("/api/tasks", json={"title": title, **extra}, **CK)
    assert r.status_code == 201, (r.status_code, r.text)
    return r.json()["id"]


def set_done_at(task_id, iso):
    """Подмена done_at в БД ТОЛЬКО строками формата продакшн-пути
    («...+03:00», тик msk_now_iso): лексикографическое сравнение в
    autoarchive корректно внутри одного формата; негативные кейсы
    (вчера/граница) строятся сдвигом datetime внутри этого же формата.
    Строкой «+00:00» done_at больше не подставляется никогда — такой
    формат маскировал blocker review-6.1-001 (#2 review)."""
    assert iso.endswith("+03:00"), f"done_at обязан быть в +03:00, got {iso!r}"
    c = get_connection()
    try:
        c.execute(
            "UPDATE tasks SET done_at = ? WHERE id = ?", (iso, task_id)
        )
        c.commit()
    finally:
        c.close()


def msk_shift_iso(**kwargs):
    """Момент now по msk_now_iso, сдвинутый на kwargs (timedelta),
    в том же формате «...+03:00» — для негативных кейсов."""
    base = datetime.fromisoformat(msk_now_iso())
    return (base + timedelta(**kwargs)).isoformat()


results = []


def check(name, ok, fact=""):
    results.append((name, ok, fact))
    print(("OK   " if ok else "FAIL ") + name + (" | " + fact if fact else ""))


# --- Проверка 1: move в done → 200, done_at проставлен, archived_at NULL,
# --- задача ЕСТЬ в done-столбце /api/board.
t1 = make_task("П1: done сегодня")
r = client.post(f"/api/tasks/{t1}/move", json={"status": "done"}, **CK)
body = r.json()
assert r.status_code == 200, (r.status_code, r.text)
assert body["done_at"] is not None and body["archived_at"] is None, body
status_db, done_db, arch_db = db_task(t1)
board = client.get("/api/board", **CK).json()["columns"]
in_done = [t["id"] for t in board["done"]]
check(
    "1. move в done: 200, done_at в БД, archived_at NULL, в done-столбце",
    status_db == "done"
    and done_db is not None
    and arch_db is None
    and t1 in in_done,
    f"db: status={status_db} done_at={done_db} archived_at={arch_db}; "
    f"board.done ids={in_done}",
)

# --- Проверка 2: done_at сегодня → задача на доске (после повторного GET).
r = client.get("/api/board", **CK)
still = [t["id"] for t in r.json()["columns"]["done"]]
check("2. done_at сегодня → задача на доске", t1 in still, f"board.done={still}")

# --- Проверка 3: done_at = вчера 23:59 МСК (сдвиг ВНУТРИ формата +03:00)
# --- → GET /api/board → archived_at лениво, задача исчезла.
t3 = make_task("П3: архивация вчера")
r = client.post(f"/api/tasks/{t3}/move", json={"status": "done"}, **CK)
assert r.status_code == 200, (r.status_code, r.text)
# «Вчера 23:59:59 МСК» относительно текущего момента (работает в любой
# час МСК-дня: сейчас - 24ч - (текущее время - 23:59:59)).
now_msk = datetime.fromisoformat(msk_now_iso())
yesterday_2359 = (now_msk - timedelta(days=1)).replace(
    hour=23, minute=59, second=59, microsecond=0
)
set_done_at(t3, yesterday_2359.isoformat())
r = client.get("/api/board", **CK)
columns = r.json()["columns"]
everywhere = [t["id"] for col in columns.values() for t in col]
status_db, done_db, arch_db = db_task(t3)
check(
    "3. done_at вчера 23:59 МСК: ленивая автоархивация, исчез с доски",
    arch_db is not None
    and t3 not in everywhere
    and columns.get("done_note") is None,
    f"db: done_at={done_db} archived_at={arch_db}; доска без задачи: "
    f"{t3 not in everywhere}; done_note в ответе: {columns.get('done_note')!r}",
)

# --- Проверка 4: обратный move из done → оба поля NULL.
t4 = make_task("П4: обратный move")
client.post(f"/api/tasks/{t4}/move", json={"status": "done"}, **CK)
r = client.post(f"/api/tasks/{t4}/move", json={"status": "in_progress"}, **CK)
body = r.json()
status_db, done_db, arch_db = db_task(t4)
board = client.get("/api/board", **CK).json()["columns"]
in_prog = [t["id"] for t in board["in_progress"]]
check(
    "4. обратный move done→in_progress: оба NULL, задача в «В работе»",
    body["done_at"] is None
    and body["archived_at"] is None
    and done_db is None
    and arch_db is None
    and t4 in in_prog,
    f"db: done_at={done_db} archived_at={arch_db}",
)

# --- Проверка 5: негативные кейсы границы — done_at сдвигом ВНУТРИ
# --- формата +03:00 (не строкой чужого формата, см. set_done_at).
# --- 5а: вчера 23:59:59.999 МСК → архивируется «после полуночи».
t5 = make_task("П5: граница полуночи МСК")
r = client.post(f"/api/tasks/{t5}/move", json={"status": "done"}, **CK)
assert r.status_code == 200, (r.status_code, r.text)
just_before_midnight = (
    datetime.fromisoformat(msk_now_iso()) - timedelta(days=1)
).replace(hour=23, minute=59, second=59, microsecond=999000)
set_done_at(t5, just_before_midnight.isoformat())
r = client.get("/api/board", **CK)
columns = r.json()["columns"]
everywhere = [t["id"] for col in columns.values() for t in col]
status_db, done_db, arch_db = db_task(t5)
check(
    "5. done_at 23:59:59.999 МСК вчера → архивируется после полуночи",
    arch_db is not None and t5 not in everywhere,
    f"done_at={done_db} (23:59 МСК вчера) → archived_at={arch_db}",
)
# 5б: done_at ровно 00:00:00.000000 МСК сегодня — НЕ архивируется
# (граница включена: сравнение строгое done_at < day_start).
t5b = make_task("П5б: граница 00:00 сегодня")
r = client.post(f"/api/tasks/{t5b}/move", json={"status": "done"}, **CK)
assert r.status_code == 200, (r.status_code, r.text)
midnight_today = datetime.fromisoformat(msk_now_iso()).replace(
    hour=0, minute=0, second=0, microsecond=0
)
set_done_at(t5b, midnight_today.isoformat())
client.get("/api/board", **CK)
status_db, done_db, arch_db = db_task(t5b)
check(
    "5б. done_at 00:00:00.000 МСК сегодня → НЕ архивируется (граница включена)",
    arch_db is None,
    f"done_at={done_db} archived_at={arch_db}",
)

# --- Проверка 5в (blocker review-6.1-001, часы 00:00–03:59 МСК):
# --- эмуляция «сейчас 01:00 МСК»: done_at = msk_now_iso от
# --- подмененных часов (01:00 МСК СЕГОДНЯ, реальный продакшн-код) →
# --- GET /api/board → задача ОСТАЕТСЯ в done-столбце, архивации нет.
t5c = make_task("П5в: done в 01:00 МСК")
r = client.post(f"/api/tasks/{t5c}/move", json={"status": "done"}, **CK)
assert r.status_code == 200, (r.status_code, r.text)
# Прямой вызов msk_now_iso при подмене datetime в модуле — тот же
# продакшн-код, что в move; подмена часов, не подмена формата.
import app.board as board_mod  # noqa: E402

# Реальный тик ДО подмены часов — база эмуляции.
_real_now_msk = datetime.fromisoformat(msk_now_iso())
_fake_now = _real_now_msk.replace(
    hour=1, minute=0, second=0, microsecond=0
)  # «Сейчас» = сегодня 01:00:00 МСК (UTC+03:00)


class _FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return _fake_now.astimezone(tz) if tz is not None else _fake_now


_orig_datetime = board_mod.datetime
board_mod.datetime = _FakeDT
try:
    done_at_1am = board_mod.msk_now_iso()
    day_start_1am = board_mod._msk_day_start_iso()
finally:
    board_mod.datetime = _orig_datetime
set_done_at(t5c, done_at_1am)
r = client.get("/api/board", **CK)
columns = r.json()["columns"]
in_done = [t["id"] for t in columns["done"]]
status_db, done_db, arch_db = db_task(t5c)
check(
    "5в. move→done в 01:00 МСК (подмененные часы) → задача НА доске, не архивирована",
    done_at_1am.endswith("+03:00")
    and done_at_1am[:10] == day_start_1am[:10]
    and arch_db is None
    and t5c in in_done,
    f"done_at={done_db} (01:00 МСК сегодня, формат {done_at_1am[-6:]}); "
    f"граница дня={day_start_1am}; archived_at={arch_db}; в done-столбце: {t5c in in_done}",
)

# --- Проверка 6: регрессия login/health/CRUD/comments/fast-инвариант.
r = client.get("/api/health")
check("6a. health", r.status_code == 200 and r.json() == {"status": "ok"})
r = client.post(
    "/api/auth/login", json={"login": "smoke", "password": "smoke-pass"}
)
check(
    "6b. login: валидный → 200 ok; неверный пароль → 401 единый текст",
    r.status_code == 200 and r.json()["ok"] is True,
)
r = client.post(
    "/api/auth/login", json={"login": "smoke", "password": "wrong"}
)
check(
    "6b. login: неверный пароль → 401 единый текст",
    r.status_code == 401 and r.json() == {"error": "invalid credentials"},
)
t6 = make_task("П6: регрессия CRUD", priority="high", tags=["reg"])
r = client.get(f"/api/tasks/{t6}", **CK)
task_obj_keys = set(r.json().keys())
check(
    "6c. GET task: схема sdd §3.2 (12 полей, включая done_at)",
    task_obj_keys
    == {
        "id", "title", "description", "priority", "category", "due_date",
        "tags", "is_fast", "status", "done_at", "archived_at",
    },
    f"keys={sorted(task_obj_keys)}",
)
r = client.patch(f"/api/tasks/{t6}", json={"priority": "low"}, **CK)
check("6d. PATCH", r.status_code == 200 and r.json()["priority"] == "low")
r = client.post(
    f"/api/tasks/{t6}/comments", json={"body": "смоке-коммент"}, **CK
)
assert r.status_code in (200, 201), (r.status_code, r.text)
r = client.get(f"/api/tasks/{t6}/comments", **CK)
check(
    "6e. comments POST/GET",
    len(r.json()["comments"]) == 1
    and r.json()["comments"][0]["body"] == "смоке-коммент",
)
# todo↔in_progress не задеты; 409 fast-инвариант жив.
tf = make_task("П6f: fast", is_fast=True)
r = client.post(f"/api/tasks/{tf}/move", json={"status": "in_progress"}, **CK)
check(
    "6f. move todo→in_progress: 200, колонки не тронуты",
    r.status_code == 200
    and r.json()["done_at"] is None
    and r.json()["archived_at"] is None,
)
r = client.post("/api/tasks", json={"title": "вторая fast", "is_fast": True}, **CK)
check(
    "6g. вторая fast → 409 fast line occupied",
    r.status_code == 409 and r.json() == {"error": "fast line occupied"},
)
# 422 недопустимый статус в move.
r = client.post(f"/api/tasks/{t6}/move", json={"status": "nope"}, **CK)
check("6h. move: недопустимый статус → 422", r.status_code == 422)

# --- Проверка 7: миграция done_at — свежая БД и БД до-r5 (ALTER),
# --- повторный init идемпотентен.
c = get_connection()
cols_fresh = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
c.close()
init_db()  # повторный запуск — идемпотентен
c = get_connection()
cols_after = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
idxs = {
    row[1]
    for row in c.execute("PRAGMA index_list(tasks)").fetchall()
}
c.close()

# БД в старой схеме (без done_at): emulate pre-r5.
old_db = os.path.join("/tmp", "pre_r5_" + os.path.basename(DB_PATH))
c = get_connection(old_db)
c.executescript(
    """
    CREATE TABLE tasks (
      id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT,
      priority TEXT, category TEXT, due_date TEXT,
      is_fast INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'todo',
      archived_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    INSERT INTO tasks (title, created_at, updated_at)
      VALUES ('старая задача', '2026-01-01T00:00:00+00:00',
              '2026-01-01T00:00:00+00:00');
    """
)
c.commit()
c.close()
from app import config  # noqa: E402
config.settings.db_path = old_db
init_db()
c = get_connection(old_db)
cols_old = {row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()}
old_row = c.execute(
    "SELECT title, done_at FROM tasks WHERE title = 'старая задача'"
).fetchone()
c.close()
config.settings.db_path = DB_PATH

check(
    "7. миграция done_at: свежая БД, идемпотентность, ALTER pre-r5",
    "done_at" in cols_fresh
    and cols_fresh == cols_after
    and "done_at" in cols_old
    and old_row == ("старая задача", None)
    and "idx_tasks_done_at" in idxs,
    f"fresh={sorted(cols_fresh)}; pre-r5 колонки={sorted(cols_old)}; "
    f"idx_tasks_done_at в индексах: {'idx_tasks_done_at' in idxs}",
)

print()
failed = [name for name, ok, _ in results if not ok]
print(f"ИТОГО: {len(results) - len(failed)}/{len(results)} зеленых")
if failed:
    print("FAIL:", failed)
    sys.exit(1)
print("SMOKE 4.4/6.1: все проверки зеленые")
