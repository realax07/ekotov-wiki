"""Смоук-проверка задачи 7.1: GET /api/search (sdd.md r5 §3.5; спека search).

11 пунктов из задания 7.1 (локальная проверка): пустой фильтр, priority,
category, tag одиночный/множественный, due-границы, archived x3,
комбинация, 422 (priority/дата), 401 без сессии, SQL-инъекция.

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_7_1.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-7.1")

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


def make_task(title, **extra):
    r = client.post("/api/tasks", json={"title": title, **extra}, **CK)
    assert r.status_code == 201, (r.status_code, r.text)
    return r.json()["id"]


# --- Набор задач: разные приоритеты, категории, теги, сроки, архив ---
make_task("A high home", priority="high", category="work",
          tags=["home"], due_date="2026-09-20")
make_task("B medium car", priority="medium", category="personal",
          tags=["car"], due_date="2026-09-25")
make_task("C low both", priority="low", category="work",
          tags=["home", "car"], due_date="2026-10-01")
make_task("D no-features")  # без признаков
id_e = make_task("E archived done", priority="high", category="personal",
                 tags=["home"], due_date="2026-09-22", is_fast=False)
# E → done + лениво заархивирована (done_at вчера по МСК, подмена напрямую в БД
# — как в smoke_6_1): archived_at = прошлый МСК-день.
c = get_connection()
c.execute(
    "UPDATE tasks SET status='done', done_at='2026-09-17T10:00:00+03:00', "
    "archived_at='2026-09-18T00:00:01+03:00' WHERE id=?",
    (id_e,),
)
c.commit()
c.close()

ids = {t["title"][0]: t["id"] for t in client.get("/api/search", **CK).json()["results"]}

results = []


def check(n, name, cond, detail=""):
    results.append((n, name, cond, detail))
    print(f"{'PASS' if cond else 'FAIL'} {n}: {name} {detail}")


def search(params):
    r = client.get("/api/search", params=params, **CK)
    return r


def titles(params):
    r = search(params)
    assert r.status_code == 200, (r.status_code, r.text)
    return sorted(t["title"] for t in r.json()["results"])


# 1) пустой фильтр → все задачи, включая архивные
r = search({})
all_titles = sorted(t["title"] for t in r.json()["results"])
archived_flags = {t["title"]: (t["archived_at"] is not None)
                  for t in r.json()["results"]}
check(1, "пустой фильтр = все (5 шт, вкл. архив)",
      r.status_code == 200 and len(all_titles) == 5
      and "E archived done" in all_titles, all_titles)
# признак архивности в каждом Task (11 полей sdd §3.2)
t0 = r.json()["results"][0]
fields = {"id", "title", "description", "priority", "category", "due_date",
          "tags", "is_fast", "status", "done_at", "archived_at"}
check("1b", "Task: 11 полей + archived_at различим",
      set(t0.keys()) == fields and archived_flags["E archived done"] is True
      and archived_flags["A high home"] is False, str(set(t0.keys())))

# 2) priority=high → только high
res = search({"priority": "high"}).json()["results"]
check(2, "priority=high → только high",
      {t["priority"] for t in res} == {"high"} and len(res) == 2,
      sorted(t["title"] for t in res))

# 3) category фильтрует
check(3, "category=work → A, C",
      titles({"category": "work"}) == ["A high home", "C low both"])

# 4) tag одиночный и множественный (IN = ИЛИ внутри признака, design §6)
check("4a", "tag=home (одиночный) → A, C, E",
      titles({"tag": "home"}) == ["A high home", "C low both", "E archived done"])
check("4b", "tag=home&tag=car (множественный, IN/ИЛИ) → все с home ИЛИ car",
      titles([("tag", "home"), ("tag", "car")]) ==
      ["A high home", "B medium car", "C low both", "E archived done"])

# 5) due-границы; граничные даты — включительно
check("5a", "due_before=2026-09-20 (вкл) → A",
      titles({"due_before": "2026-09-20"}) == ["A high home"])
check("5b", "due_after=2026-09-25 (вкл) → B, C",
      titles({"due_after": "2026-09-25"}) == ["B medium car", "C low both"])
check("5c", "due_before+due_after (диапазон) → B, E",
      titles({"due_after": "2026-09-21", "due_before": "2026-09-25"}) ==
      ["B medium car", "E archived done"])

# 6) archived=true/false/all
check("6a", "archived=true → только архивная E",
      titles({"archived": "true"}) == ["E archived done"])
check("6b", "archived=false → только активные (без E)",
      titles({"archived": "false"}) ==
      ["A high home", "B medium car", "C low both", "D no-features"])
check("6c", "archived=all → все 5", len(search({"archived": "all"}).json()["results"]) == 5)

# 7) комбинация фильтров → AND
check(7, "priority=high AND tag=home AND archived=false → A",
      titles({"priority": "high", "tag": "home", "archived": "false"}) ==
      ["A high home"])

# 8) невалидный priority → 422
check(8, "priority=urgent → 422",
      search({"priority": "urgent"}).status_code == 422)

# 9) невалидная дата → 422
check(9, "due_before=not-a-date → 422",
      search({"due_before": "not-a-date"}).status_code == 422)
check("9b", "archived=bogus → 422",
      search({"archived": "bogus"}).status_code == 422)

# 10) без сессии → 401
check(10, "без сессии → 401",
      client.get("/api/search").status_code == 401)

# 11) SQL-инъекция: не выполняется как SQL, таблица цела
inj = "home' OR 1=1--"
r = search({"tag": inj})
check(11, f"инъекция tag={inj!r} → не SQL, 0 совпадений",
      r.status_code == 200 and r.json()["results"] == [])
r = search({"category": "work'; DROP TABLE tasks;--"})
check("11b", "инъекция category (DROP) → не совпадает, таблица цела",
      r.status_code == 200 and r.json()["results"] == [])
check("11c", "таблица tasks цела (все 5 задач после инъекций)",
      len(search({}).json()["results"]) == 5)

fails = [x for x in results if not x[2]]
print(f"\n{'ALL PASS' if not fails else f'FAILURES: {len(fails)}'} "
      f"({len(results)} проверок)")
sys.exit(1 if fails else 0)
