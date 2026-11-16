"""Экспорт контракта search-сервиса OpenAPI → contracts/openapi-search.json.

Change add-microservices-full, tasks 0.1 (design §3); волна 1 пакета
add-p20-contracts, задача 1.1 (design §1): полный экспорт живой схемы
СЕРВИСА 1:1 — фильтрация по префиксам упразднена, контракт замораживается
ровно такой, какой отдает живой services/search/app/main.py (5 path-items,
включая /api/health).

Что делает:
  1. Строит временную БД (users + sessions — минимум для сессионного
     middleware сервиса) и вставляет валидную сессию: у сервиса нет
     роутера логина (design add-microservices-full §2), вход делается
     прямой вставкой строки sessions, как в services/search/tests.
  2. Поднимает живой search-сервис (uvicorn app.main:app из каталога
     services/search на свободном порту) — контракт должен быть
     зафиксирован ровно такой, какой его отдает живое приложение через
     http-слой (middleware регистрируется через http, прямой вызов
     app.openapi() не годится).
  3. Контроль без сессии: GET /openapi.json → 401 (схема не публикуется
     публично — services/search/app/middleware.py, паттерн ядра).
  4. Забирает GET /openapi.json ПОД сессией ЦЕЛИКОМ (без фильтрации —
     у сервиса своя схема целиком, FR-133/FR-137), ассертит ожидаемое
     множество path-items (5 путей, расхождение = RuntimeError — контроль
     полноты, design add-p20-contracts §1) и пишет
     contracts/openapi-search.json (формат — json.dumps(sort_keys=True,
     indent=2, ensure_ascii=False) + завершающий \\n — стабильный дифф).

Код сервиса не меняется (ОГР-29). Проверка «экспорт = зафиксированный
файл» (задача 1.1): повторный запуск скрипта не меняет
contracts/openapi-search.json (пустой git-дифф).

Запуск:  python scripts/export_openapi_search.py   (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi-search.json
"""

from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = REPO_ROOT / "services" / "search"
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-search.json"

# Полное множество path-items живого /openapi.json сервиса (design
# add-p20-contracts §1): search/suggestions-роутеры + healthcheck.
# Расхождение живой схемы с этим множеством = RuntimeError.
EXPECTED_PATHS = {
    "/api/search",
    "/api/search/advanced",
    "/api/suggestions",
    "/api/suggestions/users",
    "/api/health",
}

SESSION_COOKIE_NAME = "session"  # services/search/app/middleware.py
SESSION_TOKEN = "export-openapi-session"

# Валидная сессия: срок скользящий (+1 день), форма как в
# services/search/tests/test_search_service.py (fixture db_path).
SESSION_CREATED = datetime.now(timezone.utc)
SESSION_EXPIRES = SESSION_CREATED + timedelta(days=1)

# Минимальная схема БД для сессионного middleware сервиса (users +
# sessions; сервис — read-only потребитель, экспорту /openapi.json
# запросы к tasks не нужны).
DB_SCHEMA_SQL = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  login TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT,
  role TEXT,
  bio TEXT,
  avatar_path TEXT,
  avatar_updated_at TEXT
);
CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(base_url: str, deadline: float = 60.0) -> None:
    last_error: Exception | None = None
    started = time.monotonic()
    while time.monotonic() - started < deadline:
        try:
            resp = requests.get(f"{base_url}/api/health", timeout=2)
            if resp.status_code == 200 and resp.json() == {"status": "ok"}:
                return
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(0.3)
    raise RuntimeError(f"Локальный app {base_url} не готов за {deadline}s: {last_error}")


def _build_db(db_path: Path) -> None:
    """Временная БД: user owner + валидная сессия для middleware сервиса."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DB_SCHEMA_SQL)
        conn.execute(
            "INSERT INTO users (id, login, password_hash) VALUES (1, 'owner', 'x')"
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES (?, 1, ?, ?)",
            (SESSION_TOKEN, SESSION_CREATED.isoformat(), SESSION_EXPIRES.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _start_service(tmp_dir: Path) -> tuple[subprocess.Popen, str]:
    """uvicorn app.main:app (services/search) на свободном порту с tmp-БД."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_dir / "wiki.db"
    _build_db(db_path)
    env = dict(
        __import__("os").environ,
        EKOTOV_WIKI_DB_PATH=str(db_path),
        TZ="UTC",
    )
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=SERVICE_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc, base_url


def _session() -> requests.Session:
    """Клиент с валидной сессией (кука Secure — по http на localhost банку
    снимаем, как в LocalhostSession-паттерне tests/web/conftest.py)."""
    session = requests.Session()
    session.cookies.set(SESSION_COOKIE_NAME, SESSION_TOKEN, domain="127.0.0.1")
    return session


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="export-openapi-search-") as tmp:
        proc, base_url = _start_service(Path(tmp))
        try:
            _wait_ready(base_url)

            # Контроль FR-68 ДО входа: без сессии схема не отдается 200
            # (сервис отвечает 401 — API-путь, services/search/app/middleware.py).
            anon = requests.get(f"{base_url}/openapi.json", timeout=5,
                                allow_redirects=False)
            if anon.status_code != 401:
                raise RuntimeError(
                    f"FR-68 нарушен: /openapi.json без сессии = "
                    f"{anon.status_code} (ожидался 401 — сервис без валидной "
                    f"сессии не публикует схему)"
                )

            resp = _session().get(f"{base_url}/openapi.json", timeout=10)
            resp.raise_for_status()
            schema = resp.json()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    # Контроль полноты (design add-p20-contracts §1): контракт = живая
    # схема сервиса 1:1, без фильтрации.
    paths = set(schema.get("paths", {}))
    if paths != EXPECTED_PATHS:
        raise RuntimeError(
            "Живая схема сервиса разошлась с ожидаемым множеством path-items: "
            f"лишние {sorted(paths - EXPECTED_PATHS)}, "
            f"недостающие {sorted(EXPECTED_PATHS - paths)}"
        )

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK: contracts/openapi-search.json записан "
          f"({len(paths)} путей, openapi {schema.get('openapi', '?')}):")
    for path in sorted(paths):
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
