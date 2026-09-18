"""Смоук-проверка логики нового TC-arch-007 (правка review-002).

Воспроизводит порядок шагов 3-5 кейса на TestClient против реального
продакшн-кода: move→done заново (done_at = DA2'), UPDATE-смещение done_at
на вчера, GET /api/board → ленивая автоархивация (done_at вчера <
начала текущего МСК-дня). Каждый шаг кейса = одна проверка с теми же
наблюдениями (done_at/archived_at/столбец доски), что в кейсе.

Формат done_at — только продакшн-«...+03:00» (см. smoke_6_1.py:
строка +00:00 маскировала blocker review-6.1-001).

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_arch_007.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-arch-007")

import bcrypt
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import create_session  # noqa: E402
from app.board import msk_now_iso  # noqa: E402
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

client = TestClient(app, base_url="https://test")
CK = {"cookies": {"session": token}}

results = []


def check(name, ok, fact=""):
    results.append(ok)
    print(("OK   " if ok else "FAIL ") + name + (" | " + fact if fact else ""))


def db_task(task_id):
    c = get_connection()
    try:
        return c.execute(
            "SELECT status, done_at, archived_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    finally:
        c.close()


def set_done_at(task_id, iso):
    assert iso.endswith("+03:00"), f"done_at обязан быть в +03:00, got {iso!r}"
    c = get_connection()
    try:
        c.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (iso, task_id))
        c.commit()
    finally:
        c.close()


def board_done_ids():
    cols = client.get("/api/board", **CK).json()["columns"]
    return [t["id"] for t in cols["done"]]


# --- Предусловия кейса: задача «Цикл», шаги 1-2 (done → in_progress) ---
tid = client.post("/api/tasks", json={"title": "Цикл"}, **CK).json()["id"]

# Шаг 1: move → done → DA1
client.post(f"/api/tasks/{tid}/move", json={"status": "done"}, **CK)
DA1 = client.get(f"/api/tasks/{tid}", **CK).json()["done_at"]

# Шаг 2: move → in_progress → done_at = NULL
client.post(f"/api/tasks/{tid}/move", json={"status": "in_progress"}, **CK)
status_db, done_db, _ = db_task(tid)
check("Шаг 2 (предусловие): done_at снят при уходе из done", done_db is None,
      f"status={status_db} done_at={done_db}")

# --- Шаг 3 кейса: move → done ЗАНОВО, зафиксировать свежий DA2' ---
r = client.post(f"/api/tasks/{tid}/move", json={"status": "done"}, **CK)
DA2 = r.json()["done_at"]
arch_db = db_task(tid)[2]
check(
    "Шаг 3: повторный move → done: свежий done_at = DA2', archived_at NULL, в done-столбце",
    r.status_code == 200
    and DA2 is not None and DA2 != DA1
    and DA2.endswith("+03:00")
    and arch_db is None
    and tid in board_done_ids(),
    f"DA1={DA1} DA2'={DA2} archived_at={arch_db}",
)

# --- Шаг 4 кейса: UPDATE-смещение done_at на вчера (DA2), затем чтение задачи:
# --- смещение наблюдаемо, move его еще не перезаписал
now_msk = datetime.fromisoformat(msk_now_iso())
DA2_shifted = (now_msk - timedelta(days=1)).replace(
    hour=18, minute=0, second=0, microsecond=0
).isoformat()
set_done_at(tid, DA2_shifted)  # UPDATE tasks SET done_at='<вчера>T18:00:00+03:00'
status_db, done_db, arch_db = db_task(tid)
check(
    "Шаг 4: UPDATE-смещение done_at на вчера — наблюдаемо в GET /api/tasks/{id}",
    done_db == DA2_shifted and DA2_shifted[:10] < DA2[:10] and status_db == "done",
    f"done_at после UPDATE={done_db} (вчера; DA2' был {DA2})",
)

# --- Шаг 5 кейса: GET /api/board → ленивая автоархивация
# --- (done_at вчера < начала текущего МСК-дня): archived_at проставлен,
# --- задача исчезла из done-столбца, done_at сохранен неизменным
columns = client.get("/api/board", **CK).json()["columns"]
everywhere = [t["id"] for col in columns.values() for t in col]
status_db, done_db, arch_db = db_task(tid)
check(
    "Шаг 5: ленивая автоархивация по смещенному done_at (вчера < начала МСК-дня)",
    arch_db is not None
    and tid not in everywhere
    and done_db == DA2_shifted
    and status_db == "done",
    f"done_at={done_db} archived_at={arch_db}; исчез с доски: {tid not in everywhere}",
)

print()
failed = results.count(False)
print(f"ИТОГО: {len(results) - failed}/{len(results)} зеленых")
if failed:
    sys.exit(1)
print("SMOKE arch-007 (review-002): логика шагов 3-5 подтверждена")
