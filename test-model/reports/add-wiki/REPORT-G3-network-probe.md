# REPORT-G3-network-probe — закрытие GAP G3: внешние сетевые запросы раздела Wiki

- **Дата:** 2026-10-10. Репо: /home/openclaw/ekotov-wiki, ветка main @ 5f7f36a.
- **Закрывает:** GAP **G3** (Must, Low-Medium) из REPORT-coverage-audit.md —
  «Редактор без внешних зависимостей» (ОГР-8, NFR-34): REPORT-4.4 §(в) мерял
  только pageerror, сетевые запросы не перехватывались.
- **Метод:** playwright-проба с перехватом СЕТИ `page.on('request')` +
  `responsefinished` (MIME-контроль ES-модулей) + `requestfailed`, против
  автостенда tests/web/conftest (uvicorn app + http.server static, tmp-БД
  `app.db` + `migrate_wiki` + seed owner; playwright-маршрутизация «роль
  nginx» — единый origin). Проба: `scripts/g3_probe_wiki_network.py`
  (одноразовая, в коммит не входит).
- **Страницы (4/4 реально отрисованы — заголовки в логе пробы):** `/wiki`
  (дерево, ≥1 узел — sanity-ассерт), `/wiki?create=1` (редактор: клик в
  contenteditable + ввод текста + клики по кнопкам тулбара), `/wiki/{id}`
  (статья), `/wiki/{id}/history` (история).

## Факт

- **Запросов перехвачено всего:** 120 (document/script/css/fetch/xhr).
- **Внешних запросов (host ≠ 127.0.0.1/localhost/::1): 0.**
  Единственный host в логе — `127.0.0.1` (app + static, playwright-роутинг).
- **Домены: пусто** — внешних доменов не обнаружено.
- **MIME-ошибки ES-модулей:** 0 — все `static/js/wiki/*.js` отданы с
  content-type `application/javascript` (контроль по `responsefinished`).
- **requestfailed:** 0 (нет оборванных/заблокированных запросов).
- **Статика (DV, вне браузера):** grep `https?://` по `frontend/templates/`
  — только Jinja-комментарий в login.html (не исполняется); по
  `frontend/static/js/wiki/` — только placeholder ссылки в editor.js:518
  (не запрос); `wiki.css` — `@import`/`url()` внешних нет.

## Вердикт

**G3 ЗАКРЫТ — подтверждено.** Ни одна страница раздела Wiki (дерево, статья,
редактор с активным вводом и тулбаром, история) не порождает ни одного
запроса за пределы 127.0.0.1/localhost. Требование «contenteditable без CDN,
никаких внешних библиотек» (ОГР-8, NFR-34) выполнено; попутно подтверждена
корректность MIME статики ES-модулей. Пробу целесообразно переложить в
автотест `tests/web` (request-interception assert по паттерну пробы) —
рекомендация 6.1.
