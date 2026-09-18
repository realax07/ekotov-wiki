"""Смоук-замер NFR-2/NFR-1 (tasks.md 8.2): 1000+ задач, отклик ≤2 с.

Методика:
  - ЖИВОЙ процесс uvicorn (127.0.0.1, порт 8392) + urllib: без TestClient —
    замер честного HTTP-цикла (сокет, сериализация), как при реальном
    открытии доски. Замер: time.perf_counter() вокруг полного запроса.
  - Наполнение: 1100 задач скриптом через API — реалистичное распределение
    (60% todo / 20% in_progress / 10% done сегодня / 10% архив done-вчера),
    признаки: 3 приоритета (примерно поровну + часть без), 5 категорий,
    8 тегов (по 1-3 на задачу), дедлайны ±30 дней; ~10% done → done_at
    вчера по МСК → ленивая автоархивация на первом GET /api/board.
    Первая доска-прогрев выполняет разовую автоархивацию ~110 UPDATE —
    отдельно в статистику не идет (прогрев), замеряется стабилизировавшийся
    отклик.
  - Замеры (10 прогонов каждый, NFR-1 порог 2.0 с):
      GET /api/board            — открытие доски
      GET /api/search           — 3 варианта: пустой / priority+category /
                                  archived=true
      POST /api/search/advanced — фильтр с tag IN + priority
      POST /api/tasks           — создание
      PATCH /api/tasks/{id}     — редактирование
      POST /api/tasks/{id}/move — перемещение (todo → in_progress → todo)
  - Отчет: min/avg/p95/max по каждому действию, verdict ≤2 с.

Запуск: python backend/smoke_8_2.py   (venv: /home/openclaw/venvs/wiki/bin/python)
"""

import json
import os
import signal
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BACKEND = os.path.dirname(os.path.abspath(__file__))
PORT = 8392
BASE = f"http://127.0.0.1:{PORT}"
N_TASKS = 1100
RUNS = 10
THRESHOLD_S = 2.0

DB_PATH = os.environ.get("SMOKE_DB") or tempfile.mktemp(suffix=".db", dir="/tmp")

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def req(method: str, path: str, body: dict | None = None, token: str | None = None):
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
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            try:
                s.connect(("127.0.0.1", PORT))
            except OSError:
                return
        time.sleep(0.25)
    raise RuntimeError(f"порт {PORT} занят — уберите зависший процесс")


def start_process() -> subprocess.Popen:
    wait_port_free()
    env = dict(os.environ, DB_PATH=DB_PATH, SECRET_KEY="smoke-secret-8.2")
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


def stop_process(proc: subprocess.Popen) -> None:
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=15)


def login() -> str:
    r = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"login": "smoke", "password": "smoke-pass"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r) as resp:
        return resp.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]


def bench(name: str, fn, runs: int = RUNS) -> list[float]:
    """fn() → (status, body); возвращает список секунд, PASS при всех 2xx и ≤2с."""
    times: list[float] = []
    codes: list[int] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        status, _body = fn()
        times.append(time.perf_counter() - t0)
        codes.append(status)
    ok_codes = all(200 <= c < 300 for c in codes)
    mx = max(times)
    check(
        f"8.2 {name}: avg={statistics.mean(times)*1000:.0f} мс, "
        f"min={min(times)*1000:.0f} мс, max={mx*1000:.0f} мс ≤ 2000 мс",
        ok_codes and mx <= THRESHOLD_S,
        f"codes={sorted(set(codes))}",
    )
    return times


# ============================== Подготовка ==============================
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
for suffix in ("-wal", "-shm"):
    if os.path.exists(DB_PATH + suffix):
        os.remove(DB_PATH + suffix)

sys.path.insert(0, BACKEND)
os.environ.setdefault("DB_PATH", DB_PATH)
os.environ.setdefault("SECRET_KEY", "smoke-secret-8.2")
from app.db import init_db  # noqa: E402

init_db()
proc = start_process()
print(f"=== Процесс pid={proc.pid}, DB={DB_PATH}, порог {THRESHOLD_S} с ===")

import bcrypt  # noqa: E402
conn = sqlite3.connect(DB_PATH)
conn.execute(
    "INSERT INTO users (login, password_hash) VALUES (?, ?)",
    ("smoke", bcrypt.hashpw(b"smoke-pass", bcrypt.gensalt()).decode("ascii")),
)
conn.commit()
conn.close()
token = login()

# ============================ Наполнение 1100 ===========================
# Реалистичное распределение (sdd §1: 2 пользователя, 1000+ задач):
# статусы: 60% todo, 20% in_progress, 10% done сегодня, 10% done вчера→архив
# признаки: приоритеты high/medium/low/none, 5 категорий, 8 тегов (1–3 шт),
# дедлайны в окне ±30 дней.
import random  # noqa: E402
from datetime import date, timedelta  # noqa: E402

random.seed(8202)
PRIORITIES = ["high", "medium", "low", None]
CATEGORIES = ["work", "home", "personal", "finance", "health"]
TAGS = ["urgent", "home", "car", "docs", "call", "buy", "read", "nfr"]
today = date(2026, 9, 18)

t_fill0 = time.perf_counter()
created_ids: list[int] = []
batch_errors = 0
for i in range(N_TASKS):
    status: str
    if i < int(N_TASKS * 0.10):
        status = "done_archive"
    elif i < int(N_TASKS * 0.20):
        status = "done_today"
    elif i < int(N_TASKS * 0.40):
        status = "in_progress"
    else:
        status = "todo"
    tags = random.sample(TAGS, k=random.choice((1, 1, 2, 3)))
    body = {
        "title": f"Задача {i:04d} {random.choice(('настроить', 'проверить', 'купить', 'написать', 'позвонить'))}",
        "priority": random.choice(PRIORITIES),
        "category": random.choice(CATEGORIES),
        "due_date": (today + timedelta(days=random.randint(-30, 30))).isoformat(),
        "tags": tags,
    }
    s, t = req("POST", "/api/tasks", body, token)
    if s != 201:
        batch_errors += 1
        continue
    tid = t["id"]
    created_ids.append(tid)
    if status in ("done_archive", "done_today", "in_progress"):
        target = "done" if status != "in_progress" else "in_progress"
        s, _ = req("POST", f"/api/tasks/{tid}/move", {"status": target}, token)
        if s != 200:
            batch_errors += 1
fill_s = time.perf_counter() - t_fill0

# 10% done вчера по МСК → archived_at проставит ленивая автоархивация доски.
# ВАЖНО: подзапрос с ORDER BY id — без него LIMIT берет строки в порядке
# индекса, а не «первые 110 задач» (поймано на прогоне 8.2: 46 вместо 110).
conn = sqlite3.connect(DB_PATH)
cut = int(N_TASKS * 0.10)
conn.execute(
    "UPDATE tasks SET done_at='2026-09-17T10:00:00+03:00' "
    "WHERE status='done' AND id IN "
    "(SELECT id FROM tasks WHERE status='done' ORDER BY id LIMIT ?)",
    (cut,),
)
conn.commit()
n_by_status = dict(conn.execute(
    "SELECT status, COUNT(*) FROM tasks GROUP BY status").fetchall())
conn.close()
print(f"Наполнение: {len(created_ids)} задач через API за {fill_s:.1f} с "
      f"({batch_errors} ошибок), по статусам: {n_by_status}")
check("8.2: наполнено 1000+ задач (NFR-2)", len(created_ids) >= 1000,
      f"{len(created_ids)} шт.")

# Прогрев: первый GET /api/board выполняет ленивую автоархивацию (разовый UPDATE)
s, _ = req("GET", "/api/board", token=token)
t0 = time.perf_counter()
s, _ = req("GET", "/api/board", token=token)
warm = time.perf_counter() - t0
conn = sqlite3.connect(DB_PATH)
archived = conn.execute(
    "SELECT COUNT(*) FROM tasks WHERE archived_at IS NOT NULL").fetchone()[0]
conn.close()
print(f"Прогрев+автоархивация: {archived} задач в архиве, "
      f"доска после прогрева {warm*1000:.0f} мс")
check("8.2: автоархивация сработала на 1-м чтении доски", archived >= cut - 5,
      f"{archived} архивных")

# ============================== Замеры ==================================
print(f"\n=== Замеры ({RUNS} прогонов каждый, порог {THRESHOLD_S} с) ===")

times_board = bench("GET /api/board (открытие доски)",
                    lambda: req("GET", "/api/board", token=token))

search_cases = [
    ("GET /api/search (пустой фильтр = все задачи)",
     "/api/search"),
    ("GET /api/search (priority=high + category=work + 2 тега)",
     "/api/search?priority=high&category=work&tag=urgent&tag=docs"),
    ("GET /api/search (archived=true)",
     "/api/search?archived=true"),
]
times_search = []
for name, qs in search_cases:
    times_search.extend(bench(name, lambda qs=qs: req("GET", qs, token=token)))

times_advanced = bench(
    "POST /api/search/advanced (tag IN + priority + due-диапазон)",
    lambda: req("POST", "/api/search/advanced",
                {"query": "tag IN (\"urgent\", \"docs\") AND priority = \"high\" "
                          "AND due <= 2026-10-01"}, token))

# Мутирующие действия: каждая операция на своей задаче (реалистичный отклик)
times_post, times_patch, times_move = [], [], []
probe = created_ids[-30:]
for tid in probe:
    t0 = time.perf_counter()
    s, _ = req("POST", "/api/tasks",
               {"title": f"NFR перф {tid}", "tags": ["perf"], "priority": "low"},
               token)
    times_post.append(time.perf_counter() - t0)
    assert s == 201, (s, tid)

    t0 = time.perf_counter()
    s, _ = req("PATCH", f"/api/tasks/{tid}",
               {"description": f"описание {tid}", "priority": "high"}, token)
    times_patch.append(time.perf_counter() - t0)
    assert s == 200, (s, tid)

    t0 = time.perf_counter()
    s, _ = req("POST", f"/api/tasks/{tid}/move", {"status": "in_progress"}, token)
    times_move.append(time.perf_counter() - t0)
    assert s == 200, (s, tid)
# Уборка: probe-задачи удаляются (не влияют на распределение)
for tid in probe:
    req("DELETE", f"/api/tasks/{tid}", token=token)


def report(name: str, times: list[float]) -> None:
    mx = max(times)
    check(f"8.2 {name}: avg={statistics.mean(times)*1000:.0f} мс, "
          f"max={mx*1000:.0f} мс ≤ 2000 мс ({len(times)} оп.)",
          mx <= THRESHOLD_S)


report("POST /api/tasks (создание)", times_post)
report("PATCH /api/tasks/{id} (редактирование)", times_patch)
report("POST /api/tasks/{id}/move (перемещение)", times_move)

stop_process(proc)

print()
if failures:
    print(f"ИТОГ: FAIL ({len(failures)}): {failures}")
    sys.exit(1)
print("ИТОГ: PASS — NFR-1 (≤2 с) на 1000+ задач подтвержден по всем действиям")
