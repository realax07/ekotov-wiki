"""Экспорт машинного контракта OpenAPI → contracts/openapi.json.

Change add-containerization, tasks 0.2/0.3 (design §4, FR-68).

Что делает:
  1. Поднимает локальный экземпляр приложения (uvicorn на свободном порту,
     временная пустая БД) — «fetch под тестовой сессией против локального app»,
     как в tests/web/conftest.py (web_server). Прямой вызов app.openapi()
     не годится: middleware регистрируется через http-слой, а контракт должен
     быть зафиксирован ровно такой, какой его отдает живое приложение.
  2. Логинится seeded-юзером (owner) под тестовым паролем — без сессии
     middleware отвечает 302 → /login (FR-68: схема не публикуется публично).
  3. Забирает GET /openapi.json и пишет в contracts/openapi.json (формат —
     json.dumps(sort_keys=True, indent=2, ensure_ascii=False) + завершающий
     \n — стабильный дифф).

Проверка «экспорт = зафиксированный файл» (tasks 0.3): повторный запуск
скрипта не должен менять contracts/openapi.json (пустой git-дифф).

Запуск:  python scripts/export_openapi.py            (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi.json

API-тест поведения схемы без сессии — tests/api/test_openapi_r11.py
(302 → /login без сессии; 200 под сессией; /docs, /redoc — 404).
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
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi.json"

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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="export-openapi-") as tmp:
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
            schema = resp.json()
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
    paths = len(schema.get("paths", {}))
    print(f"OK: contracts/openapi.json записан ({paths} путей, "
          f"openapi {schema.get('openapi', '?')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
