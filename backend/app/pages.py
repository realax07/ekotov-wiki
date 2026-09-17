"""Страницы (не API): GET /login (tasks.md 2.3; sdd.md §3.6, §1).

Страница входа доступна без сессии — middleware (app/middleware.py) пропускает
GET /login отдельно (sdd.md §3.6: «страница входа… должна быть достижима»).
Здесь только рендер Jinja2-шаблона: отправка формы — POST /api/auth/login из
статики (frontend/static/js/login.js, sdd.md §1: «ванильный JS (fetch к API)»).

Прочие страницы (/board, /search, /wiki) — задачи 3.x; статика раздается
nginx'ом (design.md §8) и здесь не монтируется.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

# backend/app/pages.py -> backend/ -> корень репозитория -> frontend/templates
_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "frontend" / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/login")
def login_page(request: Request):
    """Форма входа (FR-14; дельта auth, Requirement «Вход по логину и паролю»)."""
    return templates.TemplateResponse(request=request, name="login.html")
