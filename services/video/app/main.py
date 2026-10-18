"""Точка входа video-сервиса (tasks 1.2, video-hosting волна 1; design §2).

По образцу services/images/app/main.py: FastAPI с роутером видео
(app/videos.py), healthcheck без БД-запроса, 422 в форме ядра, сессионный
middleware (без сессии — 401; exempt /api/health и /api/videos/authcheck —
стык nginx auth_request, design §5). docs/redoc выключены.

Запуск: uvicorn app.main:app --port 8380 (из каталога services/video/;
env: EKOTOV_WIKI_DB_PATH, EKOTOV_WIKI_VIDEOS_DIR — дефолты /data/wiki.db,
/data/videos — services/video/app/db.py и app/storage.py).

Волна 3 (tasks 3.1, кусок B): converter.start_worker() на СТАРТЕ
приложения (lifespan — НЕ на импорте: recover_pending читает БД, путь
которой известен только при старте процесса; найдено смоуком волны 3) —
крэш-восстановление (re-enqueue uploaded/converting) + поток-воркер
конвертации; env EKOTOV_WIKI_CONVERTER=off выключает автостарт
(сервисные тесты кусков A/D — детерминированный «uploaded» без
писателя статуса).
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app import converter
from app.middleware import register as register_auth_middleware
from app.social import router as social_router
from app.videos import router as videos_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Кусок B (tasks 3.1): крэш-восстановление + фоновый поток-воркер
    # конвертации (uploaded/converting → очередь; design §3). Единственный
    # писатель статуса — этот воркер; env EKOTOV_WIKI_CONVERTER=off —
    # детерминированный режим без конвертации (сервисные тесты).
    converter.start_worker()
    yield


app = FastAPI(
    title="ekotov-wiki",
    docs_url=None,
    redoc_url=None,
    # FR-68-паттерн search/images: машинная схема включена, но публично не
    # раскрывается — /openapi.json защищен сессионным middleware.
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.include_router(videos_router)
app.include_router(social_router)  # кусок D (tasks 2.2): комментарии/реакции/категории


# 422 в форме ядра/search/images: {"error": "validation error", "details": {...}}.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation error",
            "details": jsonable_encoder(exc.errors()),
        },
    )


# Сессионный middleware (паттерн images; без валидной сессии — 401, NFR-36).
register_auth_middleware(app)


@app.get("/api/health")
def health() -> dict:
    """Health-check (exempt middleware; без БД-запроса — паритет images/search)."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8380")))
