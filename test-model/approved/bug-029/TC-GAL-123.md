# TC-GAL-123 — Снятие реакции из UI: клик по активной = DELETE, по неактивной = PUT

- **Change:** BUG-029 (фикс красного TC-GAL-117; паритет видео TD-B2/BUG-027, PR #279)
- **Источник:** test-model/bugs/BUG-029-gallery-ui-cannot-remove-reaction.md (ветка pipeline/bug-028, PR #286 — карточка в момент фикса еще не слита на main). Контракт — BUG-026 (PR #266): PUT = идемпотентный set, снятие — только DELETE /like | /dislike (services/images/app/gallery.py:371/386, совпадающий знак; несовпадение/нет голоса — no-op 200)
- **Тип:** ФТ, UI/e2e, поз. + регр. | **Приоритет:** Must
- **Маркер:** автоматизирован — `tests/web/test_qa21_gallery_ui.py::test_tc_gal_123_reaction_click_active_deletes_inactive_puts` (стенд, реальный backend images) + `services/images/tests/test_images_service.py::test_reaction_flow`, `::test_reaction_put_idempotent` (семантика DELETE: снятие СВОЕГО голоса с совпадающим знаком, чужой знак не задет, повторный DELETE no-op), TC-GAL-117 (сквозной сценарий, шаг «повторный same-sign — снятие»)
- **Предусловия:** qa-стенд поднят (`GET {BASE_URL}/api/health` → 200, nginx :18443); сессия owner; gallery.js исполняется (BUG-008-guard пройден); image без голосов owner'а
- **Шаги:**
  1. Открыть лайтбокс, клик «Нравится» (неактивная кнопка) — запрос **PUT** `/api/images/{id}/like`: `aria-pressed=true`, `likes=1`.
  2. Повторный клик по той же (теперь АКТИВНОЙ) кнопке — запрос **DELETE** `/api/images/{id}/like`: `aria-pressed=false`, `likes=0` (голос снят; до фикса BUG-029 уходил PUT → no-op, снятие невозможно).
  3. Клик по неактивной — снова PUT, голос возвращается.
  4. Клик по «Не нравится» (неактивная) — PUT-перенос: дизлайк активен, лайк снят.
  5. Повторный клик по активному дизлайку — DELETE `/api/images/{id}/dislike`: `aria-pressed=false`, `dislikes=0`.
- **Ожидаемый результат:** метод запроса определяется состоянием `my_reaction`: активная реакция → DELETE, неактивная → PUT; aria-метки («…Снять голос») и подсветка соответствуют фактическому запросу; снятие из UI возможно для обоих знаков; счетчики и бейдж карточки сетки актуальны после каждого шага.
- **Дискриминация:** на диффе до фикса (sendReaction всегда PUT) тест краснеет на шаге 2 (метод PUT, `aria-pressed` остается `true`, `likes=1`); на фиксе — зеленый. Регрессия toggle-семантики PUT (до BUG-026) ловится TC-GAL-111.
