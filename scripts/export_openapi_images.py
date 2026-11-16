"""Экспорт контракта images-сервиса OpenAPI → contracts/openapi-images.json.

Change add-p20-contracts, волна 3, задачи 3.1/3.2 (design §1/§2), по
образцу scripts/export_openapi_video.py (а тот — export_openapi_search.py):
контракт замораживается ровно такой, какой отдает живой
services/images/app/main.py через http-слой, ПОЛНОСТЬЮ, без фильтрации:
11 операций на 8 path-items (gallery.py 10 + /api/health).

Что делает:
  1. Строит временную БД (users + sessions — минимум для сессионного
     middleware) и tmp-том картинок (EKOTOV_WIKI_IMAGES_DIR).
  2. Поднимает живой images-сервис (uvicorn app.main:app из каталога
     services/images на свободном порту) и вставляет валидную сессию
     прямой вставкой строки sessions (у сервиса нет роутера логина).
  3. Контроль без сессии: GET /openapi.json → 401 (схема не публикуется
     публично — services/images/app/middleware.py).
  4. Забирает GET /openapi.json ПОД сессией ЦЕЛИКОМ, ассертит ожидаемое
     множество path-items (9 путей / 11 операций — контроль полноты,
     design §1, Д-З1; расхождение = RuntimeError).
  5. Аннотирование ошибок (design §2, ОВ-7): components.schemas.Error
     {"error": …} (без additionalProperties:false — ОВ-1б); 401
     middleware / 422 validation-handler → $ref Error; 404/403
     (HTTPException {"detail": …}) → честная detail-схема. Ручные правки
     замороженного JSON вне экспорт-скрипта запрещены (FR-137).

Примечание (расхождение с формулировкой задачи 3.2, эскалировано ПМ):
409 у реакций images НЕТ — PUT like/dislike идемпотентны (BUG-026,
no-op/перенос, статус-кодов конфликта не порождают; в services/images/app
grep «409» пуст). Спека замораживает фактическое поведение (ОГР-29) —
инжектить фиктивный 409 запрещено; набор error-статусов спеки:
401/403/404/422/500 (500 в спеку не аннотируется — вне списка задачи).

Код сервиса не меняется (ОГР-29). Повторный запуск не меняет файл
(детерминизм; проверка задачи 3.1: git diff --exit-code пуст).

Запуск:  python scripts/export_openapi_images.py  (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi-images.json
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
SERVICE_DIR = REPO_ROOT / "services" / "images"
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-images.json"

# Полное множество path-items живого /openapi.json сервиса (design
# add-p20-contracts §1, Д-З1): gallery.py + healthcheck = 8 path-items /
# 11 операций. Расхождение живой схемы с этим множеством = RuntimeError.
EXPECTED_PATHS = {
    "/api/images",
    "/api/images/{image_id}",
    "/api/images/{image_id}/like",
    "/api/images/{image_id}/dislike",
    "/api/images/{image_id}/comments",
    "/api/images/{image_id}/comments/{comment_id}",
    "/api/images/{image_id}/name",
    "/api/health",
}
EXPECTED_OPERATIONS = 11

SESSION_COOKIE_NAME = "session"  # services/images/app/middleware.py
SESSION_TOKEN = "export-openapi-session"

# Валидная сессия: срок скользящий (+1 день), форма как в
# services/search/tests (fixture db_path).
SESSION_CREATED = datetime.now(timezone.utc)
SESSION_EXPIRES = SESSION_CREATED + timedelta(days=1)

# Минимальная схема БД для сессионного middleware сервиса (users +
# sessions; экспорту /openapi.json чтения images не нужны).
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
# Аннотирование ошибок (design §2, ОВ-7) — см. export_openapi_video.py
# --------------------------------------------------------------------------

ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {"error": {"type": "string"}},
}
DETAIL_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {"detail": {"type": "string"}},
}


def _error_ref_response(description: str) -> dict:
    return {
        "description": description,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
        },
    }


def _detail_response(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": dict(DETAIL_SCHEMA)}},
    }


# (path, method) → {status: response}. Состав снят с кода обработчиков
# (gallery.py/middleware.py/main.py) — ОГР-29. 409 отсутствует (см.
# докстринг модуля — реакции идемпотентны, BUG-026).
ANNOTATIONS: dict[tuple[str, str], dict[str, dict]] = {
    ("/api/images", "post"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "422": _error_ref_response(
            'две формы: {"error", "details"} (битый multipart/файл — '
            'validation-handler) и {"detail": "invalid file: unknown category"} '
            "(семантическая — HTTPException)"
        ),
    },
    ("/api/images", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
    },
    ("/api/images/{image_id}", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id)'
        ),
    },
    ("/api/images/{image_id}/like", "put"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id); '
            "повторный лайк — идемпотентный no-op 200 (BUG-026), 409 НЕТ"
        ),
    },
    ("/api/images/{image_id}/like", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id)'
        ),
    },
    ("/api/images/{image_id}/dislike", "put"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id); '
            "повторный дизлайк — идемпотентный no-op 200 (BUG-026), 409 НЕТ"
        ),
    },
    ("/api/images/{image_id}/dislike", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id)'
        ),
    },
    ("/api/images/{image_id}/comments", "post"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'две формы: {"error", "details"} (битый JSON/тело — validation-handler; '
            'нечисловой image_id) и {"detail": "comment body is empty"} '
            "(семантическая — HTTPException)"
        ),
    },
    ("/api/images/{image_id}/comments/{comment_id}", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка/комментарий не найден: {"detail"}'),
        "403": _detail_response('чужой комментарий: {"detail": "not your comment"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой image_id/comment_id)'
        ),
    },
    ("/api/images/{image_id}/name", "put"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('картинка не найдена: {"detail": "image not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (пустое/длинное/недопустимое name; '
            "нечисловой image_id)"
        ),
    },
}


def annotate(schema: dict) -> dict:
    """Детерминированное аннотирование ошибок (см. export_openapi_video.py)."""
    paths = schema["paths"]
    for (path, method), statuses in ANNOTATIONS.items():
        op = paths[path][method]
        responses = op.setdefault("responses", {})
        for status, response in statuses.items():
            responses[str(status)] = response

    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["Error"] = dict(ERROR_SCHEMA)
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
    """uvicorn app.main:app (services/images) на свободном порту, tmp-том."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_dir / "wiki.db"
    _build_db(db_path)
    (tmp_dir / "images").mkdir()
    env = dict(
        __import__("os").environ,
        EKOTOV_WIKI_DB_PATH=str(db_path),
        EKOTOV_WIKI_IMAGES_DIR=str(tmp_dir / "images"),
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
    with tempfile.TemporaryDirectory(prefix="export-openapi-images-") as tmp:
        proc, base_url = _start_service(Path(tmp))
        try:
            _wait_ready(base_url)

            # Контроль ДО входа: без сессии схема не отдается 200
            # (сервис отвечает 401 — services/images/app/middleware.py).
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

    # Контроль полноты (design add-p20-contracts §1, Д-З1): контракт =
    # живая схема сервиса 1:1; сверка по path-items И по числу операций.
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
            f"{EXPECTED_OPERATIONS} (gallery.py 10 + /api/health)"
        )

    schema = annotate(schema)

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK: contracts/openapi-images.json записан "
          f"({len(paths)} path-items / {operations} операций, "
          f"openapi {schema.get('openapi', '?')}):")
    for path in sorted(paths):
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
