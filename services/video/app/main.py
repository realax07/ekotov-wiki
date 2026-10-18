"""Точка входа video-сервиса (tasks 1.2, video-hosting волна 1; design §2).

По образцу services/images/app/main.py: FastAPI с роутером видео
(app/videos.py), healthcheck без БД-запроса, 422 в форме ядра, сессионный
middleware (без сессии — 401; exempt /api/health и /api/videos/authcheck —
стык nginx auth_request, design §5). docs/redoc выключены.

Запуск: uvicorn app.main:app --port 8380 (из каталога services/video/;
env: EKOTOV_WIKI_DB_PATH, EKOTOV_WIKI_VIDEOS_DIR — дефолты /data/wiki.db,
/data/videos — services/video/app/db.py и app/storage.py).

Волна 3 (tasks 3.1) добавит строку старта converter.start_worker() здесь —
единственное запланированное расширение этого файла (sdd §2).
"""

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.middleware import register as register_auth_middleware
from app.social import router as social_router
from app.videos import router as videos_router

app = FastAPI(
    title="ekotov-wiki",
    docs_url=None,
    redoc_url=None,
    # FR-68-паттерн search/images: машинная схема включена, но публично не
    # раскрывается — /openapi.json защищен сессионным middleware.
    openapi_url="/openapi.json",
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
