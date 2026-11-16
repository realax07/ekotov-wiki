# TC-GAL-111 — Реакции: идемпотентный PUT (no-op повтора), снятие DELETE, смена голоса, независимость пользователей

- **Change:** BUG-028 (фикс красного CI tests); контракт — BUG-026 (PR #266) + паритет BUG-027/TD-B
- **Источник:** BUG-026 (TD-5, аудит Kimi 2026-10-31): «PUT = идемпотентный set, снятие — DELETE» (test-model/bugs/BUG-026-reaction-put-not-idempotent.md); паритет видео TC-vid-041. **Supersedes** toggle-версию TC-GAL-111 (`archive/test-model/approved/add-gallery-service/TC-GAL-111.md`: «повторный same-sign PUT снимает голос» — упразднена решением BUG-026, PUT по семантике HTTP идемпотентен)
- **Тип:** ФТ, API, поз. + гран. | **Приоритет:** Must
- **Маркер:** автоматизирован — `tests/api/test_qa21_gallery_api.py::test_tc_gal_111_reaction_put_idempotent_change_independence` (стенд) + `services/images/tests/test_images_service.py::test_reaction_put_idempotent`, `::test_reaction_flow` (юниты)
- **Предусловия:** qa-стенд поднят (`GET {BASE_URL}/api/health` → 200, nginx :18443); сессии двух пользователей (owner и PE, seed owner/wife); изображение с нулевыми счетчиками; `EKOTOV_WIKI_DB_PATH` задан (проверка строк `image_reactions`)
- **Шаги:**
  1. owner: `PUT /api/images/<id>/like` — 200, `my_reaction=1`, `likes=1`; повторить тот же PUT (имитация ретрая сети/двойного клика) — 200 **no-op**: `my_reaction=1`, `likes=1` (голос НЕ снят, счетчик не вырос); дамп `image_reactions` — ровно одна строка (1, +1) (PK upsert, дублей нет).
  2. owner: `DELETE /api/images/<id>/like` — снятие голоса: `my_reaction=null`, `likes=0`; повторный DELETE — идемпотентный no-op 200 (то же состояние).
  3. owner: `PUT .../like`, затем `PUT .../dislike` (смена голоса с чистого состояния) — `my_reaction=-1`, `likes=0`, `dislikes=1` (смещение счетчика ровно на один голос, CHK-GAL-17).
  4. owner: повторный same-sign `PUT .../dislike` — no-op: `my_reaction=-1`, `dislikes=1`.
  5. PE: ставит свой лайк; owner проверяет деталь `GET /api/images/<id>` — голоса независимы: `likes=2`, у каждого свой `my_reaction`; дамп — ровно две строки (1, +1), (2, +1).
  6. `GET /api/images` (список) — карточка несет `likes=2` и `my_reaction` вызывающего (базис подсветки «мой голос» в UI).
- **Ожидаемый результат:** повтор same-sign PUT любого знака не меняет состояние (идемпотентность PUT, сетевой ретрай не снимает голос); снятие — только DELETE /like | /dislike (повторный DELETE тоже идемпотентен); смена голоса — суммарное смещение счетчиков ровно на один голос (инвариант «≤ 1 голоса на пользователя на изображение», PK(image_id, user_id)); голоса двух пользователей независимы; счетчики и собственный голос корректны в детали и списке.
- **Дискриминация:** на toggle-реализации `_set_reaction` (до BUG-026 / мутант) тест краснеет на шаге 1 (`my_reaction` None после повтора); на актуальном коде — зеленый.
