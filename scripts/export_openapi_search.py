"""Экспорт контракта поиска OpenAPI → contracts/openapi-search.json.

Change add-microservices-full, tasks 0.1 (design §3, план §3).

Что делает:
  1. Поднимает локальный экземпляр монолита (uvicorn на свободном порту,
     временная пустая БД) — тот же механизм, что scripts/export_openapi.py:
     контракт должен быть зафиксирован ровно такой, какой его отдает живое
     приложение (middleware регистрируется через http-слой, прямой вызов
     app.openapi() не годится).
  2. Логинится seeded-юзером (owner) под тестовым паролем — без сессии
     middleware отвечает 302 → /login, схема не публикуется публично.
  3. Забирает GET /openapi.json, фильтрует paths до маршрутов поиска
     (префиксы /api/search и /api/suggestions — роутеры app/search.py и
     app/suggestions.py целиком переезжают в search-сервис, design §2) и
     пишет в contracts/openapi-search.json (формат — json.dumps
     (sort_keys=True, indent=2, ensure_ascii=False) + завершающий \\n —
     стабильный дифф). Components не фильтруются: общие схемы остаются
     как есть, чтобы контракт поиска был самодостаточным.

Проверка «экспорт = зафиксированный файл» (tasks 0.1, design §3): повторный
запуск скрипта не должен менять contracts/openapi-search.json (пустой
git-дифф).

Запуск:  python scripts/export_openapi_search.py   (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi-search.json
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-search.json"

# Префиксы путей search-сервиса (design §2: app/search.py + app/suggestions.py
# переезжают целиком → /api/search* + /api/suggestions*).
SEARCH_PATH_PREFIXES = ("/api/search", "/api/suggestions")

# Тестовые учетные данные seed-пользователей (как в tests/api/conftest.py,
# NFR-7 — значения без секретности).
OWNER_LOGIN = "owner"
OWNER_PASSWORD = "QaOwner_Pass_1!"


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


def _seed_owner(db_path: Path) -> None:
    """Seed owner с тестовым паролем в пустую БД (bcrypt — как
    tests/web/conftest._seed_users; NFR-7, значения без секретности)."""
    import bcrypt
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users (login, password_hash, role) VALUES (?, ?, ?)",
            (
                OWNER_LOGIN,
                bcrypt.hashpw(OWNER_PASSWORD.encode(), bcrypt.gensalt()).decode(),
                "Product manager",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _start_app(tmp_db: Path) -> tuple[subprocess.Popen, str]:
    """uvicorn app.main:app на свободном порту с временной пустой БД."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_db / "app.db"
    env = dict(
        __import__("os").environ,
        DB_PATH=str(db_path),
        SECRET_KEY="export-openapi-local-secret",
        AVATARS_DIR=str(tmp_db / "avatars"),
        TZ="UTC",
    )
    subprocess.run(
        [sys.executable, "-m", "app.db"],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True,
    )
    _seed_owner(db_path)
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=BACKEND_DIR, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc, base_url


def _login(base_url: str) -> requests.Session:
    """Сессия owner (кука Secure — по http на localhost банку снимаем,
    повторяя браузерное поведение tests/web/conftest.LocalhostSession)."""
    session = requests.Session()
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={"login": OWNER_LOGIN, "password": OWNER_PASSWORD},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"seed-вход owner не удался: {resp.status_code} {resp.text}")
    for cookie in session.cookies:
        cookie.secure = False
    return session


def _filter_search_schema(schema: dict) -> dict:
    """Фильтрация paths до маршрутов поиска; остальная схема — как отдана."""
    paths = schema.get("paths", {})
    search_paths = {
        path: ops
        for path, ops in paths.items()
        if path.startswith(SEARCH_PATH_PREFIXES)
    }
    if not search_paths:
        raise RuntimeError(
            "В схеме приложения не найдено ни одного маршрута поиска "
            f"({', '.join(SEARCH_PATH_PREFIXES)}) — фильтрация дала пустой контракт"
        )
    filtered = dict(schema)
    filtered["paths"] = search_paths
    return filtered


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="export-openapi-search-") as tmp:
        proc, base_url = _start_app(Path(tmp))
        try:
            _wait_ready(base_url)

            # Контроль FR-68 ДО входа: без сессии схема не отдается 200.
            anon = requests.get(f"{base_url}/openapi.json", timeout=5,
                                allow_redirects=False)
            if anon.status_code not in (302, 307, 401):
                raise RuntimeError(
                    f"FR-68 нарушен: /openapi.json без сессии = "
                    f"{anon.status_code} (ожидался 302 → /login или 401)"
                )

            session = _login(base_url)
            resp = session.get(f"{base_url}/openapi.json", timeout=10)
            resp.raise_for_status()
            schema = _filter_search_schema(resp.json())
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths = sorted(schema.get("paths", {}))
    print(f"OK: contracts/openapi-search.json записан "
          f"({len(paths)} путей, openapi {schema.get('openapi', '?')}):")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
