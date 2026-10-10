# TC-openapi-101 — Машинная схема OpenAPI: 200 под сессией, экспорт = зафиксированный файл

- **Change:** add-containerization
- **Источник:** deploy: «Машинный контракт OpenAPI включен и зафиксирован» — Scenario «Схема доступна под сессией» и «Зафиксированная схема соответствует коду» (FR-68); tasks 0.2/0.3; design §4
- **Тип:** ФТ, API | **Приоритет:** Must
- **Маркер:** автоматизирован — `tests/api/test_openapi_r11.py::test_openapi_with_session_200_and_matches_contract`
- **Предусловия:** приложение поднято (стенд/локально), seed-юзер owner заведен; `contracts/openapi.json` в репозитории
- **Шаги:**
  1. Войти seeded-юзером (owner) — кука session.
  2. `GET /openapi.json` под сессией.
  3. Сравнить тело ответа с зафиксированным `contracts/openapi.json` (канонизация: sort_keys, indent 2).
- **Ожидаемый результат:** шаг 2 — 200, валидный OpenAPI-документ, описывающий маршруты `/api/*`; шаг 3 — экспорт из живого приложения идентичен зафиксированному файлу (пустой git-дифф после `scripts/export_openapi.py`).
