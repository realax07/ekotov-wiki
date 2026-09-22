"""Страницы (не API): GET /login, /board, /search, /wiki (sdd.md §3.6).

/login — задача 2.3: рендер Jinja2-шаблона, отправка формы — POST
/api/auth/login из статики (frontend/static/js/login.js).

/board, /search, /wiki — каркас интерфейса (tasks.md 3.1, FR-13, дельта
navigation): базовый layout frontend/templates/base.html с сайдбаром
(Доска, Поиск, «Wiki» с пометкой todo). Содержимое разделов — заглушки:
реальные страницы доски/поиска — задачи 4.x/7.x, раздел Wiki — заглушка без
функций (дельта navigation, Requirement «Пустой раздел Wiki с пометкой
todo»: Won't для wiki-функционала). Активный раздел сайдбара подсвечивается
классом `active` в base.html через переменную active_page. Кнопка «Выйти»
(base.html + frontend/static/js/app.js) — POST /api/auth/logout → redirect
/login (sdd.md §3.1).

Без сессии страницы /board, /search, /wiki редиректятся на /login
middleware'ом (app/middleware.py, sdd.md §3.6) — здесь не дублируется.
Статика раздается nginx'ом (design.md §8) и здесь не монтируется.
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


@router.get("/board")
def board_page(request: Request):
    """Доска — заглушка каркаса (FR-13; задачи 4.x — реальное содержимое)."""
    return templates.TemplateResponse(
        request=request, name="board.html", context={"active_page": "board"}
    )


@router.get("/search")
def search_page(request: Request):
    """Поиск — заглушка каркаса (FR-13; задачи 7.x — реальное содержимое)."""
    return templates.TemplateResponse(
        request=request, name="search.html", context={"active_page": "search"}
    )


@router.get("/wiki")
def wiki_page(request: Request):
    """Wiki — заглушка без функций с пометкой todo (FR-13, дельта navigation)."""
    return templates.TemplateResponse(
        request=request, name="wiki.html", context={"active_page": "wiki"}
    )


@router.get("/settings")
def settings_page(request: Request):
    """Настройки (tasks.md 2.1 пакета add-r2-categories-settings; FR-23,
    дельта settings): управление справочником категорий через
    /api/categories. Без сессии — редирект на /login middleware'ом
    (дельта settings, Scenario «Негативный: неавторизованный доступ»),
    здесь не дублируется. Настройки общие (FR-24): состояние — общая
    таблица categories, user_id не используется; состав — только категории
    (FR-25, Won't остального)."""
    return templates.TemplateResponse(
        request=request, name="settings.html", context={"active_page": "settings"}
    )
