"""Точка входа weather-сервиса (change weather-service, задачи 3.1–3.2;
design §2, §6).

По образцу services/video/app/main.py (без converter/lifespan — у
сервиса нет фоновых воркеров и БД): FastAPI с роутером погоды
(app/routes.py), healthcheck без БД-запроса и без вызова провайдера,
422 в форме ядра, сессионный middleware (без сессии — 401; exempt
только /api/health — authcheck-эндпоинта НЕТ, design §5).
docs/redoc выключены.

Запуск: uvicorn app.main:app --port 8381 (из каталога services/weather/;
env: EKOTOV_WIKI_DB_PATH, EKOTOV_WEATHER_CACHE_PATH, EKOTOV_WEATHER_USER_AGENT —
дефолты /data/wiki.db, /cache/weather.json, ekotov-wiki-weather/1.0).
"""

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.middleware import register as register_auth_middleware
from app.routes import router as weather_router

app = FastAPI(
    title="ekotov-wiki",
    docs_url=None,
    redoc_url=None,
    # FR-68-паттерн search/images/video: машинная схема включена, но
    # публично не раскрывается — /openapi.json защищен сессионным middleware.
    openapi_url="/openapi.json",
)
app.include_router(weather_router)


# 422 в форме ядра/search/images/video: {"error": "validation error", "details": {...}}.
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


# Сессионный middleware (паттерн video/images; без валидной сессии — 401).
register_auth_middleware(app)


@app.get("/api/health")
def health() -> dict:
    """Health-check (exempt middleware; без БД и без провайдера —
    health 200 и на пустом томе кэша; design §6)."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8381")))
