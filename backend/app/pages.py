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

# Кеш-бастинг статики (DEF-003): nginx отдаёт /static/ с expires 7d; при релизах
# URL обязан меняться, иначе браузер держит прошлую версию CSS/JS. Бампать при
# каждом релизе, меняющем статику. r7.0 — 1.5 add-gallery-service: app.css
# (пункт «Галерея» в сайдбаре) + новые gallery.css/gallery.js. r7.1 — релизный
# бамп выката 2.2 (BUG-008/009 фиксы gallery.js уже под r7.0; r7.1 гарантирует
# свежую статику у браузеров, урок R7 3a27aac). r8-polish — релизный бамп
# выкатки 3.2 add-ui-polish-r8: волны A (fastline/кнопки/настройки), B (модалка
# тикета), C+D (комментарии, таг-combobox), F+G (иконки сайдбара, favicon —
# inline data-URI, кеш-маркер `<!--cache:v=1-->` внутри SVG), I (gallery
# rename), J (masonry) — вся кешируемая статика доски/поиска/галереи/профиля
# обновлена; favicon меняет URL через бамп маркера в base.html+login.html
# (data:URI не принимает ?v= — проверено в Chromium, BUG-010/design §3).
templates.env.globals["static_v"] = "r8-polish"


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


@router.get("/settings/profile")
def profile_settings_page(request: Request):
    """Страница настроек пользователя (tasks.md 3.1 пакета
    add-r4-user-profile-ticket-view; FR-39…FR-42, ОГР-20; design §4,
    sdd §3.6): форма профиля, смена пароля, загрузка аватара — данные
    СВОЕГО аккаунта. Отдельная страница от общего раздела /settings
    (ОГР-20: справочник категорий здесь отсутствует). Без сессии —
    редирект на /login middleware'ом (дельта settings, Scenario
    «Негативный: неавторизованный доступ», NFR-7) — здесь не
    дублируется, как у остальных страниц. static_v не бампится:
    единый финальный бамп релиза — задача 6.3 (C-5 ревью review-001).
    """
    return templates.TemplateResponse(
        request=request,
        name="profile-settings.html",
        context={"active_page": "settings-profile"},
    )


@router.get("/gallery")
def gallery_page(request: Request):
    """Страница «Галерея» (tasks.md 1.5 add-gallery-service; FR-83…FR-86,
    дельта navigation — Requirement «Раздел «Галерея» в сайдбаре для всех»):
    сетка превью из GET /api/images, фильтры категория/тег, форма загрузки,
    full-screen просмотр — вся динамика из ES-модуля
    frontend/static/js/gallery.js; вид — по утвержденным мокапам 1.1
    (design/gallery-grid.html, gallery-lightbox.html, gallery-upload.html).
    Доступ общий (ОВ-4): без role-логики; разделение прав MUST NOT
    вводиться (дельта gallery, «Доступ к галерее общий для всех»).
    Без сессии — редирект на /login middleware'ом (sdd.md §3.6,
    дельта gallery, Scenario «Негативный: без сессии страница
    недоступна») — здесь не дублируется, как у остальных страниц."""
    return templates.TemplateResponse(
        request=request, name="gallery.html", context={"active_page": "gallery"}
    )
