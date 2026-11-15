# TC-vid-059 — Снятие реакции из UI: клик по активной реакции = DELETE

- **Change:** video-hosting / PLAN-TD-CLOSEOUT (TD-B2, follow-up BUG-027)
- **Источник:** эскалация из BUG-027 (PR #275): после идемпотентного PUT (TD-B/TD-5, TC-vid-041) повторный клик по активной реакции больше не снимает голос — снятие переехало в явный DELETE /api/videos/{id}/reaction по образцу галереи (DELETE /api/images/{id}/like | /dislike). Решение Заказчика 2026-11-15 — PLAN-TD-CLOSEOUT TD-B2
- **Тип:** позитивный | **Приоритет:** Must
- **Среда/предусловия:** поднятый стенд (`GET {BASE_URL}/api/health` → 200); owner авторизован (seed `owner/QaOwner_Pass_1!`); видео T13 существует; owner УЖЕ поставил лайк (счетчики 1/0, `my_reaction=1`); HTTP-клиент с сессией owner (API); вторая сессия (PE) — для независимости пользователей
- **Шаги (API):**
  1. `DELETE {BASE_URL}/api/videos/<T13>/reaction` с `{"value": 1}` — зафиксировать ответ.
  2. Повторить шаг 1 дословно (имитация ретрая / двойного клика).
  3. Проверить строки БД по паре (T13, owner).
  4. `PUT ... {"value": -1}` (дизлайк), затем `DELETE ... {"value": 1}` (чужой знак), затем `DELETE ... {"value": -1}`.
  5. `DELETE ... {"value": 0}` и `DELETE ... {}` (невалидный value); `DELETE /api/videos/no-such/reaction`; те же DELETE без сессии.
- **Шаги (UI, просмотр видео):** открыть видео с поставленным лайком → кнопка «Нравится» имеет `aria-pressed=true` и класс `my-vote` → клик по ней → кнопка возвращается в `aria-pressed=false`, счетчик обнулен, хинт скрыт; клик по НЕактивной кнопке ставит голос (PUT).
- **Ожидаемый результат:** шаг 1 — 200 `{my_reaction: null, likes: 0, dislikes: 0}`; шаг 2 — снова 200 и то же состояние (DELETE идемпотентен, состояние не меняется); шаг 3 — в БД нет строки на пару (user+video); шаг 4 — DELETE с несовпадающим знаком — no-op (голос не задет, лайк PE сохраняется), DELETE совпадающего знака снимает; шаг 5 — 422 на невалидный value (запись не задета), 404 на несуществующее видео, 401 без сессии (состояние не изменилось). Инвариант: снятие голоса возможно ТОЛЬКО явным DELETE по совпадающему знаку; PUT-ретрай голос не снимает (TC-vid-041).
- **Тестовые данные:** видео T13 с голосом owner; эндпоинты `PUT|DELETE /api/videos/{id}/reaction`; автоматизация — `services/video/tests/test_social.py::test_reaction_delete_removes_vote`, `::test_reaction_delete_errors` (TestClient), 401-ветка — `::test_social_endpoints_unauthorized_401`; UI-каркас — `tests/web/test_video_social_ui.py::test_player_view_social_blocks_by_mockup` (TC-vid-106).
