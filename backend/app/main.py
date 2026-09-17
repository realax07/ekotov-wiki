"""Точка входа ekotov-wiki (FastAPI, sdd.md §2)."""

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.auth import SESSION_COOKIE_NAME
from app.auth import router as auth_router
from app.config import settings  # noqa: F401 — валидация конфига на старте
from app.db import get_connection
from app.middleware import register as register_auth_middleware
from app.pages import router as pages_router
from app.tasks import install_error_handlers
from app.tasks import router as tasks_router

app = FastAPI(title="ekotov-wiki", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(tasks_router)
install_error_handlers(app)
register_auth_middleware(app)


@app.get("/api/health")
def health() -> dict:
    """Health-check каркаса (дополнение к sdd.md §3 — см. отчет задачи 1.1)."""
    return {"status": "ok"}


@app.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    """Выход (tasks.md 2.2; sdd.md r4 §3.1): удаляет сессию и куку.

    Доступен только с валидной сессией — exempt-списком не покрыт, путь
    проходит через middleware (app/middleware.py); сюда попадают только
    запросы с действующей сессией.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=True
    )
    return response
