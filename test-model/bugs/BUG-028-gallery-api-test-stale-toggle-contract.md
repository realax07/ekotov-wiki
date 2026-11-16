# BUG-028: CI tests красный — TC-GAL-111 ожидает упраздненную toggle-семантику PUT галерейных реакций

## Симптом
CI-джоба tests красная на main:
`tests/api/test_qa21_gallery_api.py::test_tc_gal_111_reaction_toggle_change_independence`
— `assert (1 is None)` на строке 510 (повторный same-sign `PUT /api/images/{id}/like`).

## Диагноз: (б) тест ожидает старый контракт, код продукта корректен
Волна реакций изменила контракт deliberately:

- **BUG-026** (CLOSED 2026-11-01, PR #266): PUT реакции галереи = идемпотентный
  set (тот же голос → 200 no-op, противоположный → перенос), снятие — только
  DELETE /like | /dislike. Мотивация: PUT по семантике HTTP обязан быть
  идемпотентным (TD-5, аудит Kimi 2026-10-31). Волна обновила юнит-тесты
  `services/images/tests/test_images_service.py` (35 passed) и докстринг
  `services/images/app/gallery.py::_set_reaction`, но ПРОПУСТИЛА стендовый
  api-тест TC-GAL-111 — он остался на toggle-семантике исходного TC-GAL-111
  (approved add-gallery-service, до BUG-026).
- **BUG-027** (PR #275) + TD-B/TD-B2: video-сервис приведен к тому же
  контракту (паритет), TC-vid-041 supersedes toggle-версию TC-vid-031.
- Переключение лайк↔дизлайк (перенос голоса) в коде корректно: upsert
  меняет value, `my_reaction` в ответе = −1 (покрыто шагом 3 теста).
  «Не сбрасывается my_reaction» наблюдается ТОЛЬКО на повторе same-sign —
  что и есть задокументированный no-op BUG-026.

## Решение
Тест переписан под актуальный контракт (без правок продукта):
`test_tc_gal_111_reaction_put_idempotent_change_independence` — no-op
повтора same-sign PUT, снятие DELETE /like (+ идемпотентный повтор DELETE),
перенос ровно на один голос, no-op same-sign dislike, независимость
owner/PE, отсутствие дублей (PK upsert), my_reaction/счетчики в списке и
детали. Шапка файловой трассировки обновлена.

Дискриминация: на toggle-мутанте `_set_reaction` (DELETE same-sign строки
после upsert) тест краснеет на шаге 1 (live qa-стенд REPO=/tmp/bug028-wt,
images :8379); на боевом коде — зеленый. Старая версия теста краснела на
боевом коде (`assert (1 is None)`) — воспроизведено локально на main.

## TC
TC-GAL-111 обновлен под актуальный контракт:
`test-model/approved/bug-028/TC-GAL-111.md` (supersedes toggle-версию в
archive/test-model/approved/add-gallery-service/TC-GAL-111.md).

## Попутно замечено (вне зон багфикса)
`frontend/static/js/gallery.js::sendReaction` всегда шлет PUT (рассчитан на
toggle, докстринг :18) — после BUG-026 повторный клик по активной реакции в
лайтбоксе галереи не снимает голос (no-op), хотя aria-метки обещают «Снять
голос». Video-UI эквивалент закрыт TD-B2 (DELETE по клику на активную
реакцию); галерейный аналог открыт — см. BUG-029.

## Статус
FIXED (2026-11-16, PR [BUG-028], ветка pipeline/bug-028): тест приведен к
актуальному контракту, продукт не менялся. Прогоны: TC-GAL-111 красный на
main → зеленый на ветке; tests/api/test_qa21_gallery_api.py 18 passed;
services/images 35 passed; tests/web полный сериал — см. PR-комментарий.
