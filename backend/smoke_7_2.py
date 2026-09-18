"""Смоук-проверка задачи 7.2: advanced search (parse/build + POST-роут).

Пункты локальной проверки из задания 7.2:
1) валидный запрос из sdd-примера → 200, results корректны,
   normalized_query согласован;
2) синтаксические ошибки (незакрытая кавычка, неизвестный оператор,
   мусор) → 400 с позицией/причиной, ЗАПРОС НЕ ВЫПОЛНЕН;
3) parse(build(x)) == x — круговая согласованность;
4) build(parse(текст)) для валидных текстов;
5) инъекция (DROP TABLE внутри кавычек значения) → значение-строка;
6) без сессии → 401;
7) результаты совпадают с эквивалентным GET-фильтром;
+ прямые вызовы parse/build (чистые функции без HTTP).

Запуск: DB_PATH=/tmp/... SECRET_KEY=... python backend/smoke_7_2.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db", dir="/tmp"))
os.environ.setdefault("SECRET_KEY", "smoke-secret-7.2")

import bcrypt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import create_session  # noqa: E402
from app.db import get_connection, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.search import (  # noqa: E402
    FilterSyntaxError,
    SearchFilters,
    build,
    build_where,
    parse,
)

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


def make_task(title, **extra):
    r = client.post("/api/tasks", json={"title": title, **extra}, **CK)
    assert r.status_code == 201, (r.status_code, r.text)
    return r.json()["id"]


# --- Набор задач: как в smoke_7_1 (задачи A–E) --------------------------
make_task("A high home", priority="high", category="work",
          tags=["home"], due_date="2026-09-20")
make_task("B medium car", priority="medium", category="personal",
          tags=["car"], due_date="2026-09-25")
make_task("C low both", priority="low", category="work",
          tags=["home", "car"], due_date="2026-10-01")
make_task("D no-features")  # без признаков
id_e = make_task("E archived done", priority="high", category="personal",
                 tags=["home"], due_date="2026-09-22")
c = get_connection()
c.execute(
    "UPDATE tasks SET status='done', done_at='2026-09-17T10:00:00+03:00', "
    "archived_at='2026-09-18T00:00:01+03:00' WHERE id=?",
    (id_e,),
)
c.commit()
c.close()

ADV = "/api/search/advanced"


def adv(query):
    return client.post(ADV, json={"query": query}, **CK)


def titles(resp):
    return sorted(t["title"] for t in resp.json()["results"])


# --- 1) sdd-пример: priority = "high" AND tag IN ("home") → 200 ---------
r = adv('priority = "high" AND tag IN ("home")')
check(1, "sdd-пример → 200, results корректны",
      r.status_code == 200 and titles(r) == ["A high home", "E archived done"],
      titles(r) if r.status_code == 200 else r.text)
nq = r.json().get("normalized_query")
check("1b", "normalized_query согласован (build(parse(ввод)))",
      nq == build(parse('priority = "high" AND tag IN ("home")'))
      and nq == 'priority = "high" AND tag IN ("home")', repr(nq))

# --- 2) синтаксические ошибки → 400, ЗАПРОС НЕ ВЫПОЛНЕН ----------------
errors = [
    ("незакрытая кавычка", 'priority = "high'),
    ("неизвестный оператор", 'priority ~~ "high"'),
    ("мусор", '### &&& ???'),
    ("неизвестное поле", 'color = "red"'),
    ("OR", 'priority = "high" OR priority = "low"'),
    ("незакрытая IN-скобка", 'tag IN ("home", "car"'),
    ("невалидный priority", 'priority = "urgent"'),
    ("дата-мусор", "due > 2026-13-99"),
    ("тег с = вместо IN", 'tag = "home"'),
    ("archived с неверным значением", 'archived = "maybe"'),
    ("хвост после условия", 'priority = "high" priority'),
]
n_fail = 0
for name, q in errors:
    r = adv(q)
    body = r.json()
    ok = (r.status_code == 400
          and body.get("error", "").startswith("filter syntax: ")
          and "position" in body["error"])
    if not ok:
        n_fail += 1
    check(f"2:{name}", f"{q!r} → 400 filter syntax", ok,
          f"({r.status_code}, {body})")
# ЗАПРОС НЕ ВЫПОЛНЕН: таблица не тронута, все задачи на месте
check("2:не-выполнен", "после 11 ошибок данные целы (запрос не выполнялся)",
      len(client.get("/api/search", **CK).json()["results"]) == 5)
# пустой текст — НЕ ошибка: пустой фильтр = все задачи (как GET)
r = adv("")
check("2:пустой", "пустой текст → 200, все задачи",
      r.status_code == 200 and len(r.json()["results"]) == 5
      and r.json()["normalized_query"] == "")

# --- 2b) битый JSON → 400 (не 500); дубликаты полей → 400 --------------
r = client.post(ADV, content="{not json",
                headers={"Content-Type": "application/json"}, **CK)
check("2:битый-json", "битый JSON {not json → 400 (не 500), формат error",
      r.status_code == 400 and r.json().get("error", "").startswith("filter syntax:"),
      f"({r.status_code}, {r.text[:200]})")
dups = [
    ("дубликат priority =", 'priority = "high" AND priority = "low"'),
    ("дубликат category =", 'category = "work" AND category = "home"'),
    ("дубликат priority !=", 'priority != "low" AND priority = "high"'),
    ("дубликат tag IN", 'tag IN ("home") AND tag IN ("car")'),
    ("дубликат archived", 'archived = false AND archived = true'),
    ("дубликат due =", "due = 2026-09-21 AND due = 2026-09-25"),
    ("дубликат due >=", "due >= 2026-09-21 AND due >= 2026-09-25"),
    ("дубликат due_before", "due_before <= 2026-09-21 AND due_before <= 2026-09-25"),
]
for name, q in dups:
    r = adv(q)
    ok = (r.status_code == 400
          and "duplicate field" in r.json().get("error", ""))
    check(f"2:{name}", f"{q!r} → 400 duplicate field", ok,
          f"({r.status_code}, {r.json()})")
# диапазон due (>= A AND <= B) — НЕ дубликат: разные слоты due_after/due_before
r = adv("due >= 2026-09-21 AND due <= 2026-09-25")
check("2:диапазон-due", "due >= A AND due <= B → 200 (не дубликат)",
      r.status_code == 200, f"({r.status_code}, {r.text[:200]})")
# одиночные поля по-прежнему валидны (регрессия семантики дубликатов)
r = adv('priority = "high" AND category = "work" AND archived = false '
        'AND tag IN ("home") AND due >= 2026-01-01')
check("2:не-дубликаты", "разные поля в одном запросе по-прежнему → 200",
      r.status_code == 200, f"({r.status_code}, {r.text[:200]})")

# --- 3) parse(build(x)) == x (круговая согласованность) ----------------
def as_tuple(f: SearchFilters):
    return (f.priority, f.category, tuple(sorted(f.tags)),
            f.due_before, f.due_after, f.archived)


filters_set = [
    SearchFilters(),
    SearchFilters(priority="high"),
    SearchFilters(category="work"),
    SearchFilters(tags=["home"]),
    SearchFilters(tags=["home", "car"]),
    SearchFilters(due_before=__import__("datetime").date(2026, 9, 25)),
    SearchFilters(due_after=__import__("datetime").date(2026, 9, 20)),
    SearchFilters(due_after=__import__("datetime").date(2026, 9, 21),
                  due_before=__import__("datetime").date(2026, 9, 25)),
    SearchFilters(archived="true"),
    SearchFilters(archived="false"),
    SearchFilters(priority="high", tags=["home", "car"], archived="false"),
    SearchFilters(priority="high", category="work", tags=["home"],
                  due_before=__import__("datetime").date(2026, 12, 31),
                  archived="all"),
]
n_round = 0
for i, x in enumerate(filters_set):
    y = parse(build(x))
    if as_tuple(y) == as_tuple(x):
        n_round += 1
    else:
        check(f"3:{i}", "parse(build(x)) == x", False,
              f"{x!r} → {build(x)!r} → {y!r}")
check(3, f"parse(build(x)) == x ({n_round}/{len(filters_set)} фильтров)",
      n_round == len(filters_set))

# --- 4) build(parse(текст)) для валидных текстов -----------------------
texts = [
    ('priority = "high" AND tag IN ("home")',
     'priority = "high" AND tag IN ("home")'),
    ("archived = false", "archived = false"),
    ("due >= 2026-09-21 AND due <= 2026-09-25",
     "due >= 2026-09-21 AND due <= 2026-09-25"),
    ("category = work", 'category = "work"'),  # голое слово нормализуется
    ('tag IN ("car", "home")', 'tag IN ("car", "home")'),
]
n_b = 0
for src, want in texts:
    got = build(parse(src))
    if got == want:
        n_b += 1
    else:
        check(f"4:{src!r}", "build(parse(текст))", False, f"→ {got!r}, want {want!r}")
check(4, f"build(parse(текст)) каноничен ({n_b}/{len(texts)} текстов)",
      n_b == len(texts))

# --- 5) инъекция: DROP TABLE внутри кавычек → значение-строка, не SQL ---
inj = 'category = "work; DROP TABLE tasks;--"'
r = adv(inj)
check("5a", f"инъекция {inj!r} → 200 (значение-строка), 0 совпадений",
      r.status_code == 200 and r.json()["results"] == [],
      f"({r.status_code}, {r.json() if r.status_code == 200 else r.text})")
# инъекция через tag IN
inj2 = 'tag IN ("home; DROP TABLE tasks;--")'
r = adv(inj2)
check("5b", f"инъекция в tag IN → 200, 0 совпадений",
      r.status_code == 200 and r.json()["results"] == [],
      f"({r.status_code}, {r.json() if r.status_code == 200 else r.text})")
# WHERE-фрагмент содержит только плейсхолдеры, инъекционный текст — в params
f = parse(inj)
where, params = build_where(f)
check("5c", "инъекционный текст НЕ в WHERE, только в bind-параметрах",
      "DROP" not in where and "work; DROP TABLE tasks;--" in params,
      f"where={where!r}, params={params!r}")
# таблица цела
check("5d", "таблица tasks цела после инъекций (все 5 задач)",
      len(client.get("/api/search", **CK).json()["results"]) == 5)
# normalized_query — сериализация структуры, не эхо ввода
check("5e", "normalized_query = build(parse(...)), не эхо ввода",
      r.json()["normalized_query"] == build(parse(inj2)),
      repr(r.json()["normalized_query"]))
# инъекционный текст ВНЕ кавычек — синтаксическая ошибка (и тоже не SQL)
r = adv('category = "work"; DROP TABLE tasks;--')
check("5f", "инъекция вне кавычек → 400 filter syntax (не выполняется)",
      r.status_code == 400
      and r.json()["error"].startswith("filter syntax: "), r.json())

# --- 6) без сессии → 401 -----------------------------------------------
check(6, "POST /api/search/advanced без сессии → 401",
      client.post(ADV, json={"query": 'priority = "high"'}).status_code == 401)

# --- 7) результаты совпадают с эквивалентным GET-фильтром --------------
pairs = [
    ('priority = "high" AND tag IN ("home")', {"priority": "high", "tag": "home"}),
    ('category = "work"', {"category": "work"}),
    ("archived = true", {"archived": "true"}),
    ("archived = false", {"archived": "false"}),
    ("due >= 2026-09-21 AND due <= 2026-09-25",
     {"due_after": "2026-09-21", "due_before": "2026-09-25"}),
    ("due <= 2026-09-20", {"due_before": "2026-09-20"}),
    ("due >= 2026-09-25", {"due_after": "2026-09-25"}),
    ('tag IN ("home", "car")', {"tag": ["home", "car"]}),
    ('priority = "high" AND category = "personal" AND archived = "true"',
     {"priority": "high", "category": "personal", "archived": "true"}),
]
n_pairs = 0
for q, params_get in pairs:
    t_adv = titles(adv(q))
    rg = client.get("/api/search", params=params_get, **CK)
    t_get = sorted(t["title"] for t in rg.json()["results"])
    if t_adv == t_get:
        n_pairs += 1
    else:
        check(f"7:{q!r}", "advanced == GET", False, f"{t_adv} != {t_get}")
check(7, f"advanced == эквивалентный GET ({n_pairs}/{len(pairs)} пар)",
      n_pairs == len(pairs))

# --- прямые вызовы parse/build: чистые функции, без HTTP ---------------
f = parse('priority = "high" AND tag IN ("home", "car") '
          'AND due >= 2026-09-20 AND archived = false')
check("8a", "parse: структура SearchFilters заполнена",
      f.priority == "high" and sorted(f.tags) == ["car", "home"]
      and f.due_after.isoformat() == "2026-09-20" and f.archived == "false",
      repr(f))
# != парсится и дает корректный WHERE (расширение 7.2, GET не выставляет)
f = parse('priority != "low"')
where, params = build_where(f)
check("8b", "parse(!=) → параметризованный WHERE с NULL-веткой",
      where == " WHERE (tasks.priority != ? OR tasks.priority IS NULL)"
      and params == ["low"], f"{where} {params}")
r = adv('priority != "low"')
check("8c", "priority != low → 200, без low-задач",
      r.status_code == 200
      and {t["priority"] for t in r.json()["results"]} == {"high", "medium", None},
      sorted(str(t["priority"]) for t in r.json()["results"]))
# escape в кавычках: \" внутри значения
f = parse('category = "quote \\" inside"')
check("8d", "кавычки с escape в значении", f.category == 'quote " inside',
      repr(f.category))
built = build(SearchFilters(category='quote " inside'))
check("8e", "build экранирует кавычки, parse восстанавливает",
      built == 'category = "quote \\" inside"'
      and parse(built).category == 'quote " inside', built)
# позиция ошибки — точная (0-based)
try:
    parse('priority = "high" AND due_before > 2026-01-01')
    check("8f", "позиция ошибки", False, "не бросил")
except FilterSyntaxError as e:
    # ошибка оператора привязана к ПОЛЮ (pos=22, 'due_before'):
    # оператор валиден лексически, невалидна комбинация поле+оператор.
    check("8f", "ошибка комбинации поле+оператор: pos=22 (due_before)",
          e.pos == 22 and "due_before supports" in e.reason,
          f"pos={e.pos}, {e}")
try:
    parse('priority =')
    check("8g", "незавершенное условие", False, "не бросил")
except FilterSyntaxError as e:
    check("8g", "незавершенное условие → unexpected end", True,
          f"pos={e.pos}, {e}")

fails = [x for x in results if not x[2]]
print(f"\n{'ALL PASS' if not fails else f'FAILURES: {len(fails)}'} "
      f"({len(results)} проверок)")
sys.exit(1 if fails else 0)
