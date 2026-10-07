# Улучшения: design_validator

## 2026-10-07 — прогоны web-сьюта на VPS-окружении

**Проблема:** сьюты `tests/web` падают не из-за продукта, а из-за окружения:

1. Поисковые кейсы (`test_view_modal_r4::test_search_card_click_opens_view`,
   `test_p12_ui_polish_r8` — advanced-выдача, `/api/search` для ассертов)
   получают 404/KeyError: авто-стенд conftest поднимает только uvicorn ядра —
   `/api/search*` живет в search-сервисе :8378 (nginx-контур). На машине без
   nginx-контура эти кейсы красные.
2. На этой же машине подожжены посторонние демо-процессы (ядра :8080 + search
   :8378 + images :8379 над tmp-БД `/tmp/qa31-app.db`) — авторегресс
   combobox-кейсов ловит чужие теги (`KeyError: 'results'` — совпадение в
   наименовании тега чужой задачи).

**Решение:** для design-валидации computed-styles изоляция не нужна —
проверять на подожженных вручную процессах (ядро + search) с Playwright-скриптом
(route /static/* → отдельный http.server), а падающие env-зависимые кейсы
смоука помечать в отчете как «дефект стенда, не продукта» (прецедент README §
mime.types). Для строгого прогона смоука — поднимать весь nginx-контур по
deploy/RUNBOOK или глушить посторонние uvicorn-процессы на время прогона.

**Предложение:** в tests/web/conftest — env-флаг
`EKOTOV_WIKI_SEARCH_URL` с route-проксированием `/api/search*` на внешний
search-сервис (сейчас route только для статики), либо маркер
`requires_search_service` для точечной селекции.
