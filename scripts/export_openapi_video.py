"""Экспорт контракта video-сервиса OpenAPI → contracts/openapi-video.json.

Change add-p20-contracts, волна 2, задачи 2.1/2.2 (design §1/§2): контракт
замораживается ровно такой, какой отдает живой services/video/app/main.py
через http-слой (middleware регистрируется через http — прямой вызов
app.openapi() не годится), ПОЛНОСТЬЮ, без фильтрации (у сервиса своя схема
целиком): 14 операций на 10 path-items (videos.py 7 + social.py 6 +
/api/health; PATCH rename и GET /api/videos/authcheck включены).

Что делает:
  1. Строит временную БД (users + sessions — минимум для сессионного
     middleware) и tmp-том файлов (EKOTOV_WIKI_VIDEOS_DIR); воркер
     конвертации выключен (EKOTOV_WIKI_CONVERTER=off — паритет
     services/video/tests/conftest.py, детерминизм).
  2. Поднимает живой video-сервис (uvicorn app.main:app из каталога
     services/video на свободном порту) и вставляет валидную сессию
     прямой вставкой строки sessions (у сервиса нет роутера логина).
  3. Контроль без сессии: GET /openapi.json → 401 (схема не публикуется
     публично — services/video/app/middleware.py).
  4. Забирает GET /openapi.json ПОД сессией ЦЕЛИКОМ, ассертит ожидаемое
     множество path-items (10 путей / 14 операций — контроль полноты,
     design §1, Д-З1; расхождение = RuntimeError).
  5. Аннотирование ошибок (design §2, ОВ-7; арх-ревью Н-2 — контракт =
     детерминированный экспорт + аннотации скрипта): components.schemas.
     Error {"error": …} (без additionalProperties:false — ОВ-1б); 401
     middleware / 422 validation-handler → $ref Error; 404/403/409
     (HTTPException {"detail": …}) → честная detail-схема; пометка
     «internal: потребитель — nginx auth_request, не браузер» в
     description authcheck. Ручные правки замороженного JSON вне
     экспорт-скрипта запрещены (FR-137).

Код сервиса не меняется (ОГР-29). Повторный запуск не меняет файл
(детерминизм; проверка задачи 2.1: git diff --exit-code пуст).

Запуск:  python scripts/export_openapi_video.py   (из корня репозитория)
Проверка: git diff --exit-code -- contracts/openapi-video.json
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
SERVICE_DIR = REPO_ROOT / "services" / "video"
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi-video.json"

# Полное множество path-items живого /openapi.json сервиса (design
# add-p20-contracts §1, Д-З1): videos.py (A) + social.py (D) + healthcheck
# = 10 path-items / 14 операций. Расхождение живой схемы с этим множеством
# = RuntimeError.
EXPECTED_PATHS = {
    "/api/videos",
    "/api/videos/{video_id}",
    "/api/videos/{video_id}/file",
    "/api/videos/{video_id}/preview",
    "/api/videos/{video_id}/comments",
    "/api/videos/{video_id}/comments/{comment_id}",
    "/api/videos/{video_id}/reaction",
    "/api/videos/categories",
    "/api/videos/authcheck",
    "/api/health",
}
EXPECTED_OPERATIONS = 14

SESSION_COOKIE_NAME = "session"  # services/video/app/middleware.py
SESSION_TOKEN = "export-openapi-session"

# Валидная сессия: срок скользящий (+1 день), форма как в
# services/search/tests (fixture db_path).
SESSION_CREATED = datetime.now(timezone.utc)
SESSION_EXPIRES = SESSION_CREATED + timedelta(days=1)

# Минимальная схема БД для сессионного middleware сервиса (users +
# sessions; экспорту /openapi.json чтения video_videos не нужны).
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
# Аннотирование ошибок (design §2, ОВ-7)
# --------------------------------------------------------------------------

# {"error": …} — фактический стандарт middleware (401) и validation-handler
# (422) сервиса; {"detail": …} — форма HTTPException (404/403/409/семантика
# 422). Error БЕЗ additionalProperties:false (ОВ-1б).
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

_AUTHCHECK_INTERNAL = (
    "internal: потребитель — nginx auth_request (стык /_video_auth), "
    "не браузер"
)


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
# (videos.py/social.py/middleware.py/main.py) — ОГР-29: спека описывает
# фактическое поведение. 422 всегда Error-формой (validation-handler в
# app/main.py); где семантический 422 идет HTTPException-ом ({"detail"}),
# форма указана в description.
ANNOTATIONS: dict[tuple[str, str], dict[str, dict]] = {
    ("/api/videos", "post"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (handler RequestValidationError); '
            "семантические отказы загрузки (лимит 500 МБ, unknown category) — та же форма"
        ),
    },
    ("/api/videos", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
    },
    ("/api/videos/{video_id}", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
    },
    ("/api/videos/{video_id}", "patch"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (пустой/длинный/недопустимый title)'
        ),
    },
    ("/api/videos/{video_id}/file", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео/файл не найден: {"detail"}'),
        "409": _detail_response(
            'видео еще не готово (конвертация): {"detail": "video is not ready"}'
        ),
    },
    ("/api/videos/{video_id}/preview", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео/кадр не найден: {"detail"}'),
        "409": _detail_response(
            'видео/превью еще не готово (конвертация): {"detail"}'
        ),
    },
    ("/api/videos/{video_id}/comments", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
    },
    ("/api/videos/{video_id}/comments", "post"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
        "422": _error_ref_response(
            'две формы: {"error", "details"} (битый JSON/тело — validation-handler) '
            'и {"detail": "comment text is empty"} (семантическая — HTTPException); '
            "схема — унифицированная Error (required только error, ОВ-1б)"
        ),
    },
    ("/api/videos/{video_id}/comments/{comment_id}", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео/комментарий не найден: {"detail"}'),
        "403": _detail_response('чужой комментарий: {"detail": "not your comment"}'),
        "422": _error_ref_response(
            'validation error: {"error", "details"} (нечисловой comment_id)'
        ),
    },
    ("/api/videos/{video_id}/reaction", "delete"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
        "422": _error_ref_response(
            'две формы: {"error", "details"} (битый JSON — validation-handler) '
            'и {"detail": "value must be 1 or -1"} (семантическая — HTTPException)'
        ),
    },
    ("/api/videos/{video_id}/reaction", "put"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
        "404": _detail_response('видео не найдено: {"detail": "video not found"}'),
        "422": _error_ref_response(
            'две формы: {"error", "details"} (битый JSON — validation-handler) '
            'и {"detail": "value must be 1 or -1"} (семантическая — HTTPException)'
        ),
    },
    ("/api/videos/categories", "get"): {
        "401": _error_ref_response("unauthorized (без валидной сессии — middleware)"),
    },
    ("/api/videos/authcheck", "get"): {
        "401": _error_ref_response(
            'невалидная сессия: {"error": "unauthorized"} (решает сам эндпоинт)'
        ),
    },
}


def annotate(schema: dict) -> dict:
    """Детерминированное аннотирование ошибок + internal-пометка authcheck.

    Живая схема остается 1:1 по путям/операциям/схемам 200 — добавляются
    ТОЛЬКО описания error-ответов, отсутствующие в FastAPI-экспорте
    (middleware-401 и HTTPException-ответы через OpenAPI не декларируются).
    """
    paths = schema["paths"]
    for (path, method), statuses in ANNOTATIONS.items():
        op = paths[path][method]
        responses = op.setdefault("responses", {})
        for status, response in statuses.items():
            responses[str(status)] = response

    # Internal-пометка authcheck (задача 2.2; в экспорт-скрипте, не руками).
    authcheck = paths["/api/videos/authcheck"]["get"]
    description = authcheck.get("description", "")
    marker = _AUTHCHECK_INTERNAL
    if marker not in description:
        authcheck["description"] = (
            f"{description}\n\n{marker}" if description else marker
        )

    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["Error"] = dict(ERROR_SCHEMA)
    return schema


# --------------------------------------------------------------------------
# Механика живого экспорта (образец — scripts/export_openapi_search.py)
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
    """uvicorn app.main:app (services/video) на свободном порту, tmp-том."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_dir / "wiki.db"
    _build_db(db_path)
    (tmp_dir / "videos").mkdir()
    env = dict(
        __import__("os").environ,
        EKOTOV_WIKI_DB_PATH=str(db_path),
        EKOTOV_WIKI_VIDEOS_DIR=str(tmp_dir / "videos"),
        # Воркер конвертации не нужен (экспортируется только /openapi.json);
        # детерминизм — паритет services/video/tests/conftest.py.
        EKOTOV_WIKI_CONVERTER="off",
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
    with tempfile.TemporaryDirectory(prefix="export-openapi-video-") as tmp:
        proc, base_url = _start_service(Path(tmp))
        try:
            _wait_ready(base_url)

            # Контроль ДО входа: без сессии схема не отдается 200
            # (сервис отвечает 401 — services/video/app/middleware.py).
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
            f"{EXPECTED_OPERATIONS} (videos.py 7 + social.py 6 + /api/health)"
        )

    schema = annotate(schema)

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK: contracts/openapi-video.json записан "
          f"({len(paths)} path-items / {operations} операций, "
          f"openapi {schema.get('openapi', '?')}):")
    for path in sorted(paths):
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
