"""Экспорт контракта weather-сервиса OpenAPI → contracts/openapi-weather.json.

Change add-p20-contracts, волна 4, задачи 4.1/4.2 (design §1/§2), по
образцу scripts/export_openapi_video.py: контракт замораживается ровно
такой, какой отдает живой services/weather/app/main.py через http-слой,
ПОЛНОСТЬЮ: /api/weather + /api/health (2 path-items / 2 операции).

Что делает:
  1. Строит временную БД (users + sessions — минимум для сессионного
     middleware, открытие read-only — services/weather/app/db.py) и
     tmpdir кэш-файла (EKOTOV_WEATHER_CACHE_PATH). Провайдер НЕ
     вызывается: экспорт снимает только /openapi.json и /api/health —
     ни один маршрут погоды не исполняется (Open-Meteo в спеку не
     входит, Д-17).
  2. Поднимает живой weather-сервис (uvicorn app.main:app из каталога
     services/weather на свободном порту) и вставляет валидную сессию
     прямой вставкой строки sessions (у сервиса нет роутера логина).
  3. Контроль без сессии: GET /openapi.json → 401 (схема не публикуется
     публично — services/weather/app/middleware.py).
  4. Забирает GET /openapi.json ПОД сессией ЦЕЛИКОМ, ассертит ожидаемое
     множество path-items (контроль полноты, design §1; расхождение =
     RuntimeError).
  5. Аннотирование (design §2, ОВ-7; ТЗ задача 4.2): components.schemas.
     Error {"error": …} + $ref на 401 (middleware) и 503
     (weather_unavailable — деградация, Retry-After: 60); 200-ответ
     /api/weather получает схему карточки («Сегодня» + ровно 7 дней,
     null-метрики «—» = типы [<число>, null]) — структура снята с
     app/provider.py::normalize (design §6 weather-service), без
     упоминания Open-Meteo (Д-17). Ручные правки замороженного JSON
     вне экспорт-скрипта запрещены (FR-137).

Код сервиса не меняется (ОГР-29). Повторный запуск не меняет файл
(детерминизм; проверка задачи 4.1: git diff --exit-code пуст).

Запуск:  python scripts/export_openapi_weather.py (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi-weather.json
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
SERVICE_DIR = REPO_ROOT / "services" / "weather"
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-weather.json"

# Полное множество path-items живого /openapi.json сервиса (design
# add-p20-contracts §1). Расхождение живой схемы с этим множеством =
# RuntimeError.
EXPECTED_PATHS = {
    "/api/weather",
    "/api/health",
}
EXPECTED_OPERATIONS = 2

SESSION_COOKIE_NAME = "session"  # services/weather/app/middleware.py
SESSION_TOKEN = "export-openapi-session"

# Валидная сессия: срок скользящий (+1 день), форма как в
# services/search/tests (fixture db_path).
SESSION_CREATED = datetime.now(timezone.utc)
SESSION_EXPIRES = SESSION_CREATED + timedelta(days=1)

# Минимальная схема БД (users + sessions); weather открывает ее read-only.
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

# --------------------------------------------------------------------------
# Аннотирование (design §2, ОВ-7 + схема карточки задачи 4.2)
# --------------------------------------------------------------------------

ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {"error": {"type": "string"}},
}

# Метрики-«прочерки»: провайдер может отдать null по любой метрике
# (app/provider.py::_num/_round1 — деградация «—» во фронтенде), поэтому
# числовые поля карточки — [<тип>, null] (draft-07).
_NULL_NUM = {"type": ["number", "null"]}
_NULL_INT = {"type": ["integer", "null"]}

_WIND_SCHEMA = {
    "type": "object",
    "required": ["dir", "speed"],
    "properties": {"dir": {"type": "string"}, "speed": _NULL_NUM},
}

_DAY_SCHEMA = {
    "type": "object",
    "required": ["date", "code", "description", "temp_max", "temp_min",
                 "precipitation", "wind"],
    "properties": {
        "date": {"type": "string"},
        "code": _NULL_INT,
        "description": {"type": "string"},
        "temp_max": _NULL_NUM,
        "temp_min": _NULL_NUM,
        "precipitation": _NULL_NUM,
        "wind": _WIND_SCHEMA,
    },
}

# Карточка «Сегодня» = day-поля (max/min/осадки/ветер из daily[0]) +
# текущие температура/ощущается/влажность/давление из current
# (app/provider.py::normalize); давление — мм рт. ст. (целое).
_TODAY_SCHEMA = {
    "type": "object",
    "required": ["code", "description", "temp_max", "temp_min", "precipitation",
                 "wind", "temperature", "apparent", "humidity", "pressure_mmhg"],
    "properties": {
        "code": _NULL_INT,
        "description": {"type": "string"},
        "temp_max": _NULL_NUM,
        "temp_min": _NULL_NUM,
        "precipitation": _NULL_NUM,
        "wind": _WIND_SCHEMA,
        "temperature": _NULL_NUM,
        "apparent": _NULL_NUM,
        "humidity": _NULL_NUM,
        "pressure_mmhg": _NULL_INT,
    },
}

WEATHER_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["fetched_at", "stale", "today", "days"],
    "properties": {
        "fetched_at": {"type": "string"},
        "stale": {"type": "boolean"},
        "today": _TODAY_SCHEMA,
        # Ровно 7 элементов, включая сегодня (design §6 weather-service).
        "days": {"type": "array", "minItems": 7, "maxItems": 7, "items": _DAY_SCHEMA},
    },
}


def _error_ref_response(description: str) -> dict:
    return {
        "description": description,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
        },
    }


def annotate(schema: dict) -> dict:
    """Детерминированное аннотирование: Error+$ref, схема карточки 200.

    Живая схема 401/503 через OpenAPI не декларируется (middleware /
    JSONResponse), 200 /api/weather приходит пустой схемой (у маршрута нет
    response_model) — все три аннотации добавляет скрипт (Н-2).
    """
    op = schema["paths"]["/api/weather"]["get"]
    responses = op.setdefault("responses", {})
    responses["200"] = {
        "description": (
            "Карточка погоды: fetched_at + stale + today («Сегодня») + days "
            "(ровно 7 дней, включая сегодня); числовые метрики могут быть "
            "null (деградация «—» во фронтенде)"
        ),
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/WeatherResponse"}
            }
        },
    }
    responses["401"] = _error_ref_response(
        "unauthorized (без валидной сессии — middleware)"
    )
    responses["503"] = _error_ref_response(
        'деградация: нет кэша И провайдер недоступен — '
        '{"error": "weather_unavailable"}, заголовок Retry-After: 60'
    )

    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["Error"] = dict(ERROR_SCHEMA)
    components["WeatherResponse"] = dict(WEATHER_RESPONSE_SCHEMA)
    return schema


# --------------------------------------------------------------------------
# Механика живого экспорта (образец — scripts/export_openapi_video.py)
# --------------------------------------------------------------------------


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
    """uvicorn app.main:app (services/weather) на свободном порту; tmpdir
    кэш-файла; провайдер не вызывается (нужен только /openapi.json)."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_dir / "wiki.db"
    _build_db(db_path)
    cache_dir = tmp_dir / "weather-cache"
    cache_dir.mkdir()
    env = dict(
        __import__("os").environ,
        EKOTOV_WIKI_DB_PATH=str(db_path),
        EKOTOV_WEATHER_CACHE_PATH=str(cache_dir / "weather.json"),
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
    with tempfile.TemporaryDirectory(prefix="export-openapi-weather-") as tmp:
        proc, base_url = _start_service(Path(tmp))
        try:
            _wait_ready(base_url)

            # Контроль ДО входа: без сессии схема не отдается 200
            # (сервис отвечает 401 — services/weather/app/middleware.py).
            anon = requests.get(f"{base_url}/openapi.json", timeout=5,
                                allow_redirects=False)
            if anon.status_code != 401:
                raise RuntimeError(
                    f"/openapi.json без сессии = {anon.status_code} "
                    f"(ожидался 401 — сервис без валидной сессии не "
                    f"публикует схему)"
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
    # схема сервиса 1:1.
    paths = set(schema.get("paths", {}))
    if paths != EXPECTED_PATHS:
        raise RuntimeError(
            "Живая схема сервиса разошлась с ожидаемым множеством path-items: "
            f"лишние {sorted(paths - EXPECTED_PATHS)}, "
            f"недостающие {sorted(EXPECTED_PATHS - paths)}"
        )
    operations = sum(
        len([m for m in item if m in {"get", "post", "put", "patch", "delete"}])
        for item in schema["paths"].values()
    )
    if operations != EXPECTED_OPERATIONS:
        raise RuntimeError(
            f"Живая схема несет {operations} операций, ожидалось "
            f"{EXPECTED_OPERATIONS} (/api/weather + /api/health)"
        )

    schema = annotate(schema)

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK: contracts/openapi-weather.json записан "
          f"({len(paths)} path-items / {operations} операций, "
          f"openapi {schema.get('openapi', '?')}):")
    for path in sorted(paths):
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
