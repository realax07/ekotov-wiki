"""Точка входа images-сервиса (задача 1.2, add-gallery-service; design §3).

По образцу services/search/app/main.py: FastAPI с роутером изображений
(app/gallery.py), healthcheck без БД-запроса, 422 в форме ядра, сессионный
middleware (без сессии — 401, /openapi.json не публикуется). docs/redoc
выключены.

Запуск: uvicorn app.main:app --port 8379 (из каталога services/images/;
env: EKOTOV_WIKI_DB_PATH, EKOTOV_WIKI_IMAGES_DIR — дефолты /data/wiki.db,
/data/images — services/images/app/db.py и app/gallery.py).
"""

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.gallery import router as gallery_router
from app.middleware import register as register_auth_middleware

app = FastAPI(
    title="ekotov-wiki",
    docs_url=None,
    redoc_url=None,
    # FR-68-паттерн search: машинная схема включена, но публично не
    # раскрывается — /openapi.json защищен сессионным middleware.
    openapi_url="/openapi.json",
)
app.include_router(gallery_router)


# 422 в форме ядра/search: {"error": "validation error", "details": {...}}.
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


# Сессионный middleware (паттерн search; без валидной сессии — 401).
register_auth_middleware(app)


@app.get("/api/health")
def health() -> dict:
    """Health-check (exempt middleware; без БД-запроса — паритет search)."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8379")))
