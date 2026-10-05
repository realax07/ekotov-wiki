"""Точка входа search-сервиса (задача 1.1, add-microservices-full; design §2).

Мини-main: FastAPI с обоими роутерами поиска (app/search.py,
app/suggestions.py — перенесены как есть), healthcheck и тем же паттерном
запрета OpenAPI-схемы без сессии, что в ядре (backend/app/main.py +
backend/app/middleware.py): /openapi.json не входит в exempt-список
middleware → без валидной сессии 401 (API-путь), /docs и /redoc выключены.

Запуск: uvicorn app.main:app --port 8378 (из каталога services/search/;
DB_PATH — env EKOTOV_WIKI_DB_PATH, дефолт /data/wiki.db — services/search/app/db.py).
"""

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.db import get_connection
from app.middleware import register as register_auth_middleware
from app.search import router as search_router
from app.suggestions import router as suggestions_router

app = FastAPI(
    title="ekotov-wiki",
    docs_url=None,
    redoc_url=None,
    # FR-68 / design §2: машинная схема включена (контракт сервиса,
    # contracts/openapi-search.json), но публично НЕ раскрывается —
    # /openapi.json защищен сессионным middleware, как в ядре.
    openapi_url="/openapi.json",
)
app.include_router(search_router)
app.include_router(suggestions_router)


# 422 в форме sdd §3 ({"error": "validation error", "details": {...}}) —
# минимальная локальная копия install_error_handlers из backend/app/tasks.py:
# search-роутер возвращает 422 (невалидные query-параметры, kind, query-не-строка),
# форма тела должна совпадать с ядром (контракт заморожен в
# contracts/openapi-search.json, responses 422).
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation error",
            # jsonable_encoder — паритет ядра (backend/app/tasks.py:706):
            # exc.errors() может нести не-JSON-сериализуемые ctx (ValueError
            # в custom-валидаторах) — без обертки это 500 вместо 422.
            "details": jsonable_encoder(exc.errors()),
        },
    )


# Сессионный middleware ядра (паттерн backend/app/middleware.py, локальная
# копия в app/middleware.py): exempt — только GET /api/health (+ POST
# /api/auth/login из полного списка, для единообразия паттерна; роутера
# логина в сервисе нет — путь просто не заматчится).
register_auth_middleware(app)


@app.get("/api/health")
def health() -> dict:
    """Health-check сервиса (exempt-список middleware — монитор/deploy до входа)."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8378")))
