"""Смоук-проверка NFR-3 (tasks.md 8.1): данные переживают рестарт процесса.

Методика (эмуляция systemd restart):
  ФАЗА A — запуск процесса (uvicorn на отдельном порту), создание набора:
  задачи с признаками/тегами/комментариями, архивная (done вчера по МСК),
  fast-задача, сессия. Снимок БД (строки по всем таблицам + фактический
  journal_mode). Остановка процесса (SIGTERM, как systemd stop).
  ФАЗА B — запуск процесса заново на том же DB_PATH, повторный снимок,
  сравнение: 0 потерь. Плюс сквозная проверка содержимого через API
  (доска, карточка, комментарии, поиск) — не только построчный дифф.

Запуск:  python backend/smoke_8_1.py   (DB_PATH/SECRET_KEY создает сам,
порт 8391; venv проекта: /home/openclaw/venvs/wiki/bin/python)

sdd §5 NFR-3: «Все данные в SQLite (WAL, fsync); сессии при рестарте могут
инвалилироваться (NFR-3 — про данные)» — сессии проверяются отдельно:
запись в таблице sessions сохраняется (фактически сессия переживает рестарт,
это СВЕРХ допустимого — фиксация факта в отчете).
"""

import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

BACKEND = os.path.dirname(os.path.abspath(__file__))
PORT = 8391
BASE = f"http://127.0.0.1:{PORT}"

DB_PATH = os.environ.get("SMOKE_DB") or tempfile.mktemp(suffix=".db", dir="/tmp")
SECRET = os.environ.get("SMOKE_SECRET") or "smoke-secret-8.1"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def req(method: str, path: str, body: dict | None = None, token: str | None = None):
    """HTTP-запрос к живому процессу (urllib — никаких in-process состояний)."""
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Cookie", f"session={token}")
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def wait_port_free(timeout: float = 10.0) -> None:
    """Перед стартом: порт не должен слушать чужой процесс (запуск uvicorn
    в противном случае молча упадет, а запросы пойдут старику)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            try:
                s.connect(("127.0.0.1", PORT))
            except OSError:
                return
        time.sleep(0.25)
    raise RuntimeError(f"порт {PORT} занят — уберите зависший процесс и перезапустите")


def start_process() -> subprocess.Popen:
    wait_port_free()
    env = dict(os.environ, DB_PATH=DB_PATH, SECRET_KEY=SECRET)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=1) as r:
                if r.status == 200:
                    return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("процесс не поднялся")


def db_snapshot() -> dict:
    """Полный снимок: строки всех таблиц + journal_mode (фактический режим)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        snap = {"journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0]}
        for t in tables:
            snap[t] = conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()
        return snap
    finally:
        conn.close()


def stop_process(proc: subprocess.Popen) -> None:
    """Эмуляция systemd stop: SIGTERM (то, что шлет systemd), затем ждать."""
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=15)


# ============================ ФАЗА A ============================
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
for suffix in ("-wal", "-shm"):
    if os.path.exists(DB_PATH + suffix):
        os.remove(DB_PATH + suffix)

sys.path.insert(0, BACKEND)
os.environ.setdefault("DB_PATH", DB_PATH)
os.environ.setdefault("SECRET_KEY", SECRET)
from app.db import init_db  # noqa: E402

init_db()
proc_a = start_process()
print(f"=== ФАЗА A: процесс pid={proc_a.pid}, DB={DB_PATH} ===")

# seed-пользователь напрямую в БД (seed_users интерактивен — вне скоупа проверки)
conn = sqlite3.connect(DB_PATH)
import bcrypt
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("smoke", bcrypt.hashpw(b"smoke-pass", bcrypt.gensalt()).decode("ascii")),
)
conn.commit()
conn.close()

status, body = req("POST", "/api/auth/login",
                   {"login": "smoke", "password": "smoke-pass"})
check("A: логин 200", status == 200, f"status={status}")
set_cookie = urllib.request.Request(BASE + "/api/auth/login",
                                    data=json.dumps({"login": "smoke", "password": "smoke-pass"}).encode())
set_cookie.add_header("Content-Type", "application/json")
with urllib.request.urlopen(set_cookie) as resp:
    token = resp.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]

# Набор: обычная с признаками/тегами, fast, архивная
s, t1 = req("POST", "/api/tasks", {
    "title": "NFR обычная", "description": "дескрипшн",
    "priority": "high", "category": "work",
    "due_date": "2026-10-01", "tags": ["home", "nfr"],
}, token)
check("A: создание обычной 201", s == 201, f"status={s}")
s, t2 = req("POST", "/api/tasks", {"title": "NFR fast", "is_fast": True,
                                   "priority": "high", "tags": ["nfr"]}, token)
check("A: создание fast 201", s == 201, f"status={s}")
s, t3 = req("POST", "/api/tasks", {"title": "NFR in-progress", "tags": ["nfr"]}, token)
check("A: создание in_progress 201", s == 201)
s, _ = req("POST", f"/api/tasks/{t3['id']}/move", {"status": "in_progress"}, token)
s, t4 = req("POST", "/api/tasks", {"title": "NFR архивная"}, token)
req("POST", f"/api/tasks/{t4['id']}/move", {"status": "done"}, token)
# архивная: done вчера по МСК + archived_at (лениво) — прямая правка, как в smoke_6_1
conn = sqlite3.connect(DB_PATH)
conn.execute(
    "UPDATE tasks SET done_at='2026-09-17T10:00:00+03:00', "
    "archived_at='2026-09-18T00:00:01+03:00' WHERE id=?",
    (t4["id"],),
)
conn.commit()
conn.close()
s, c1 = req("POST", f"/api/tasks/{t1['id']}/comments",
            {"body": "комментарий до рестарта"}, token)
check("A: комментарий 201", s in (200, 201), f"status={s}")
s, c2 = req("POST", f"/api/tasks/{t3['id']}/comments",
            {"body": "второй комментарий"}, token)
check("A: комментарий 2 201", s in (200, 201), f"status={s}")

snap_a = db_snapshot()
print(f"Снимок A: journal_mode={snap_a['journal_mode']}, "
          + ", ".join(f"{t}={len(rows)}" for t, rows in snap_a.items() if isinstance(rows, list)))
check("A: journal_mode=WAL", snap_a["journal_mode"] == "wal",
      f"фактический режим: {snap_a['journal_mode']}")

stop_process(proc_a)
print(f"=== Процесс остановлен (SIGTERM, exit={proc_a.returncode}) — рестарт ===")

# ============================ ФАЗА B ============================
proc_b = start_process()
print(f"=== ФАЗА B: процесс pid={proc_b.pid} ===")
snap_b = db_snapshot()

# --- Сравнение снимков: 0 потерь ---
check("B: journal_mode сохранился (WAL)", snap_b["journal_mode"] == snap_a["journal_mode"])
same_tables = set(snap_a) == set(snap_b)
check("B: набор таблиц тот же", same_tables)
if same_tables:
    for t in sorted(snap_a):
        if t == "journal_mode":
            continue
        check(f"B: таблица {t}: 0 потерь", snap_a[t] == snap_b[t],
              f"{len(snap_a[t])} строк до, {len(snap_b[t])} после")
    diff = [t for t in snap_a if t != "journal_mode" and snap_a[t] != snap_b[t]]
    print(f"Различающиеся таблицы: {diff or 'нет'}")

# --- Сквозная проверка через API ---
s, login = req("POST", "/api/auth/login", {"login": "smoke", "password": "smoke-pass"})
check("B: логин после рестарта 200", s == 200, f"status={s}")
with urllib.request.urlopen(urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"login": "smoke", "password": "smoke-pass"}).encode(),
        headers={"Content-Type": "application/json"})) as resp:
    token_b = resp.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]

s, card = req("GET", f"/api/tasks/{t1['id']}", token=token_b)
check("B: карточка на месте", s == 200 and card["title"] == "NFR обычная")
check("B: признаки карточки (priority/category/due/tags)",
      card["priority"] == "high" and card["category"] == "work"
      and card["due_date"] == "2026-10-01" and sorted(card["tags"]) == ["home", "nfr"],
      json.dumps({k: card[k] for k in ("priority", "category", "due_date", "tags")}, ensure_ascii=False))
s, comments = req("GET", f"/api/tasks/{t1['id']}/comments", token=token_b)
comments_list = comments.get("comments", []) if isinstance(comments, dict) else []
check("B: комментарий на месте", s == 200 and len(comments_list) == 1
      and comments_list[0]["body"] == "комментарий до рестарта",
      f"{len(comments_list)} шт.")

s, board = req("GET", "/api/board", token=token_b)
check("B: доска 200", s == 200)
cols = board["columns"]
check("B: столбец Ожидает: fast + обычная (fast первым по sdd §3.3)",
      [t["title"] for t in cols["todo"]] == ["NFR fast", "NFR обычная"]
      and cols["todo"][0]["is_fast"] is True,
      f"todo: {[t['title'] for t in cols['todo']]}")
check("B: столбец В работе: задача на месте", len(cols["in_progress"]) == 1
      and cols["in_progress"][0]["title"] == "NFR in-progress")
check("B: архивная не на доске", all(
    t["title"] != "NFR архивная" for st in cols.values() for t in st))

s, sr = req("GET", "/api/search?archived=true", token=token_b)
arch = [t for t in sr["results"] if t["title"] == "NFR архивная"]
check("B: архивная в поиске (archived=true) с признаком архивности",
      s == 200 and len(arch) == 1 and arch[0]["archived_at"] is not None)

s, sr = req("POST", "/api/search/advanced",
            {"query": "tag IN (\"nfr\") AND priority = \"high\""}, token_b)
check("B: advanced-поиск после рестарта", s == 200 and len(sr["results"]) >= 2,
      f"status={s}, {len(sr.get('results', []))} результатов")

# Фактический режим WAL в БД после рестарта (повторная фиксация)
check("B: journal_mode в БД после рестарта — wal", snap_b["journal_mode"] == "wal")

stop_process(proc_b)

print()
if failures:
    print(f"ИТОГ: FAIL ({len(failures)}): {failures}")
    sys.exit(1)
print("ИТОГ: PASS — NFR-3 подтвержден: рестарт процесса, 0 потерь данных")
