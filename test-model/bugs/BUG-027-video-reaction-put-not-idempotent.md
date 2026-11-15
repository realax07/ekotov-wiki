# BUG-027: PUT реакции video-сервиса не идемпотентен — сетевой повтор снимает голос

## Симптом
Повторный (ретрай сети / двойной клик) `PUT /api/videos/{id}/reaction` с тем же
`value` снимает только что поставленный голос (DELETE строки, `my_reaction=null`).
PUT по семантике HTTP обязан быть идемпотентным по ключу user+target
(PK(video_id, user_id)).

## Root cause
`services/video/app/social.py` — `put_reaction` реализован как toggle: ветка
`row.value == value → DELETE FROM video_reactions` (до фикса — строки 175-181,
задокументирована в докстрингах модуля и хендлера). Галерейный аналог закрыт
BUG-026 (PR #266); video-сервис остался toggle-ом — закрыт пакетом TD-B
(TD-5, PLAN-TD-CLOSEOUT, решение Заказчика 2026-11-15).

## Решение
PUT = идемпотентная установка голоса: тот же value → 200 no-op (состояние не
меняется); противоположный → UPDATE-перенос. Атомарность BEGIN IMMEDIATE
сохранена. Обновлены докстринги и автотесты; дискриминация — на дефектном
исходнике 3 теста краснеют (проверено подменой).

## Автотесты
`services/video/tests/test_social.py`: `test_reaction_put_idempotent` (новый),
`test_reaction_put_toggle_move`, `test_reaction_two_users_independent` —
103 passed (services/video), 35 passed (services/images). Живой smoke на
qa-стенде (nginx :18445): PUT like x2 → оба 200, likes=1.

## TC
TC-vid-041 (новый, `test-model/approved/video-hosting/TC-vid-041.md`);
TC-vid-031 — SUPERSEDED (toggle-семантика упразднена решением Заказчика).

## Эскалация ПМ (вне зоны dev)
`frontend/static/js/video.js sendReaction` и UX «повторный клик снимет»
(хинт + aria-метки) зависят от toggle; снятие голоса из UI требует решения
(DELETE /api/videos/{id}/reaction по образцу галереи + правка video.js) —
отдельным пакетом.

## Статус
CLOSED (2026-11-15, PR #275, ветка pipeline/td-b-reactions): PUT = идемпотентный
set, смена — перенос; dev (Флоу 2, TD-B), regress-final — полная серия tests/web
(числа в PR-теле/комментарии).
