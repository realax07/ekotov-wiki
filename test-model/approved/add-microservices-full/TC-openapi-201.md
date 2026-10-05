# TC-openapi-201 — Search-сервис: контракт заморожен, ядро без маршрутов поиска

- **Change:** add-microservices-full
- **Источник:** services (ADDED): «Поиск работает отдельным сервисом» — ядро не содержит маршрутов; deploy: контракт первичен (tasks 0.1/0.3/1.5; design §2–§4); CHK-P12-2, CHK-P12-3
- **Тип:** ФТ, API | **Приоритет:** Must
- **Маркер:** автоматизирован — `tests/api/test_openapi_search_service.py` (гейт, xfail снят задачей 1.5)
- **Предусловия:** репозиторий с `contracts/openapi-search.json` и `contracts/openapi.json`; код ядра на ветке пакета
- **Шаги:**
  1. `scripts/export_openapi_search.py` на тестовой сессии ядра — экспорт маршрутов `/api/search*`, `/api/suggestions`.
  2. Сравнить экспорт с `contracts/openapi-search.json` (пути, операторы, схемы ответов — программно).
  3. Проверить `backend/app/main.py`: не импортирует search_router/suggestions_router (гейт «ядро без маршрутов поиска»).
- **Ожидаемый результат:** шаг 2 — экспорт байт-в-байт равен замороженному файлу (гейт «экспорт = файл» green); шаг 3 — маршруты поиска в монолите отсутствуют, обслуживаются сервисом `services/search/` (юниты 12 passed).
