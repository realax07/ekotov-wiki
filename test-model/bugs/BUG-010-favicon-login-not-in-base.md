# BUG-010: /login без favicon — login.html не наследует base.html (FR-95)

- **Статус:** ПОЧИНЕНО (2026-10-07, ветка `fix/bug-010-favicon-login`, вариант (б) —
  дословная копия favicon-`<link>` из base.html в login.html; xfail с
  `test_favicon_present_on_login` снят; фикс-коммит `2622979`).

- **ID:** BUG-010
- **Дата:** 2026-10-07
- **Окружение:** репозиторий `/home/openclaw/ekotov-wiki`, ветка main `e26855c` (add-ui-polish-r8, волна 2.4 в main); QA-стенд nginx :18443 (app :8080); Chromium (Playwright); venv `/home/openclaw/venvs/wiki`.
- **Severity:** minor (favicon отсутствует только на странице входа — бренд/полировка, функциональность входа не затронута; при этом кейс TC-P12N-003 шаг 5 требует presence «на всех страницах», включая /login)
- **Корреляция flowctl:** d9fbb05459f5429a86953719c01edeca (fix-цикл QA 3.1 по review-004-3.1)
- **Источник:** задача 3.1 пакета add-ui-polish-r8 (правило «падения — баг-репортами в test-model/bugs/»); найден QA-автоматизацией TC-P12N-003, помечен xfail в `tests/web/test_p12_nav_icons_favicon_r8.py` (коммит 225ebd1, «кандидат BUG-010»), карточка не заводилась до review-004-3.1 (major-2).

## Трассировка

- Затронут: FR-95 (favicon data-URI SVG на страницах; кейс TC-P12N-003 шаг 5 — presence на /login тоже, «base-механизм head»).
- Файл-источник: `frontend/templates/login.html` — standalone-разметка `<head>` (charset/viewport/title/stylesheet login.css), без `{% extends "base.html" %}`; favicon-`<link>` зашит в `base.html` (волна 2.4, коммит волны 2.4, `<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,…">` с маркером `<!--cache:v=1-->`).

## Шаги воспроизведения

1. Открыть `/login` (стенд :18443 или прод).
2. В DOM проверить наличие `link[rel="icon"]`:
   `page.locator('link[rel="icon"]')` → **count = 0** (на /board…/settings — ровно 1).
3. Таб-фавикон вкладки — дефолтная иконка браузера.

Автотест: `tests/web/test_p12_nav_icons_favicon_r8.py::test_favicon_present_on_login`
(сейчас под `@pytest.mark.xfail(strict=False, reason="BUG-010 (кандидат)…")`).

## Ожидание (TC-P12N-003 шаг 5, FR-95)

На /login — ровно один `<link rel="icon" type="image/svg+xml">` с тем же data-URI, что и на страницах функционала (тот же SVG: терракотовый лист, `cache:v=1`, `#a8432c`), т.е. favicon декодируется и кеш-политика design §3 действует на всех страницах.

## Факт

```
GET /login → 200
document.querySelectorAll('link[rel="icon"]').length === 0
GET /board → 200
document.querySelectorAll('link[rel="icon"]').length === 1  (data:image/svg+xml,…cache:v=1…)
```

## Анализ

- Причина: `login.html` исторически standalone (стим входа до каркаса `base.html`); волна 2.4 добавила favicon только в базовый шаблон.
- Варианты лечения (зона dev волны фронтенда, на усмотрение ПМ):
  (а) перенести favicon-`<link>` (и статические head-элементы общего характера) в include/partial, подключаемый обоими шаблонами;
  (б) продублировать `<link rel="icon" …>` в `<head>` login.html (минимальная правка, но вторая точка правды для кеш-маркера — бамп v придется делать в двух местах);
  (в) перевести login.html на extends base.html (шире дифф: тащит сайдбар/app.js — на страницу входа каркас не нужен, вариант не рекомендуется).
- Риск варианта (б) для тестов: одинаковость URI на всех страницах (ассерт `len(set(hrefs)) == 1` в TC-P12N-003) сохранится, пока копия дословная.

## Критерий починки (снятие xfail)

1. На /login — ровно один `link[rel="icon"]`, type=image/svg+xml, href — data-URI с `cache:v=1` и `%23a8432c`.
2. URI на /login побайтно совпадает с URI на /board (единый маркер кеша).
3. Декодируемость: `naturalWidth > 0` (рендер в изолированном документе).
4. Снять `@pytest.mark.xfail` с `test_favicon_present_on_login` (`tests/web/test_p12_nav_icons_favicon_r8.py:185-200`), тест зеленый; регресс TC-P12N-003 целиком зеленый на стенде.
