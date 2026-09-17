"""Точка входа ekotov-wiki (FastAPI, sdd.md §2)."""

from fastapi import FastAPI

from app.auth import router as auth_router
from app.config import settings  # noqa: F401 — валидация конфига на старте

app = FastAPI(title="ekotov-wiki", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict:
    """Health-check каркаса (дополнение к sdd.md §3 — см. отчет задачи 1.1)."""
    return {"status": "ok"}
