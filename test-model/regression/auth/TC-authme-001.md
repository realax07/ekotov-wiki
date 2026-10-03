# TC-authme-001 — GET /api/auth/me: 200 с логином своей сессии

- **CHK:** CHK-148
- **Change:** add-r3-visual-foundation
- **Источник:** auth: «API текущего пользователя» (FR-33, NFR-7); Сценарии «Текущий пользователь определен по сессии», «Второй пользователь получает свой логин»
- **Тип:** поз. | **Приоритет:** Must
- **Среда/предусловия:** тестовый стенд tests/api (`EKOTOV_WIKI_BASE_URL`); seed-пользователи owner и wife заведены (константы conftest).
- **Шаги:**
  1. Войти owner: `POST {BASE_URL}/api/auth/login` с `{"login": "owner", "password": "QaOwner_Pass_1!"}` — сессия A.
  2. `GET {BASE_URL}/api/auth/me` в сессии A.
  3. Войти wife: тот же POST с `{"login": "wife", "password": "QaWife_Pass_2!"}` — сессия B.
  4. `GET /api/auth/me` в сессии B; затем повторно в сессии A.
- **Ожидаемый результат:** шаг 2 — 200, тело ТОЧНО `{"user": "owner"}`; шаг 4 — 200 `{"user": "wife"}` в B и снова 200 `{"user": "owner"}` в A: сессии не смешиваются, каждый получает логин своей сессии.
- **Тестовые данные:** login `owner` / `QaOwner_Pass_1!`; login `wife` / `QaWife_Pass_2!` (тестовые значения констант conftest, NFR-7).
