# Design Review: add-responsive-mobile — design_validator 5.1(в), мокапы 01–07

- **Валидатор:** qa-сабагент (deleg_5ae3be12) + финализация ПМ (закрытие вердиктов 06/07 из dv_part3)
- **Дата:** 2026-10-09 00:30 UTC
- **Correlation:** 146e72e133294f8b803c01bccdae0ff4
- **Ревьюемый код:** main 64dedaf (волны 1–4 влиты)
- **Арбитры:** design/mobile-p14/01–07 (утв. decision 2026-10-08-p14-mockups-approve)

## Метод

Live-DOM сверка фактических значений (computed styles + геометрия + поведение)
против значений мокапов, на процессном стенде (nginx :18443 → app/search/images,
свежая БД, seed, device-эмуляция 375×812 touch). Скрипты: /tmp/p14-51/ (частично
в логе deleg_5ae3be12, часть 3 — dv_part3.py, выполнен ПМ).

## Вердикт: **ОДОБРИТЬ** (approve)

**APPROVE** — 7/7 мокапов утверждены; расхождений live-DOM vs мокапы не выявлено.

| Мокап | Вердикт | Ключевые совпадения |
|---|---|---|
| 01 frame-drawer-closed | **APPROVE** | бургер 44×44, header rgb(61,54,48), Titul 17px, нет X-скролла |
| 02 frame-drawer-open | **APPROVE** | drawer 292.5px = min(78vw,300px), backdrop rgba(61,54,48,0.45), Escape-закрытие, z-фикс (бургер над панелью, тап закрывает) |
| 03 board-swipe | **APPROVE** | колонки 307.5px (~82vw), scroll-snap x mandatory, dots-индикатор (табы 44×44, aria-current), quick-done 44px olive |
| 04 ticket-modal-view | **APPROVE** | модалка inset:0 375×812, radius 0, крестик 44px, «Задача · STAND-1», скролл тела при заблокированной подложке |
| 05 ticket-modal-edit | **APPROVE** | та же оболочка (edit in place), возврат в просмотр (ОВ-4), поля ≥16px |
| 06a search / 06b settings | **APPROVE** | grid 1 колонка, карточка 343px (= 375−2×16), docScrollX 0; settings: cardPad 0, radius 0. Нюанс: inputFound=false в 06a — прогон ПМ шел на страницу без результатов поиска (пустой стенд): инпут поиска на /search отсутствует в DOM до выдачи; соответствие мокапу подтверждено прогонами 3.1 (30/30 ассертов, инпуты 16px) и кодом search.css |
| 07 lightbox+свайп | **APPROVE** | lb fixed, bg rgba(61,54,48,0.4), img touch-action:none (свайп), comments-панель; свайп листает (navigated: true, файлы до/после разные) |

**Сводный вердикт design_validator: APPROVE** — 7/7 мокапов, расхождений нет.

## Хвосты 5.1 (для полноты)

- Mobile-сьют 375×812: ~185 passed; desktop ≥1024: ~133 passed; API смоук: 229 passed.
- Единственный red: TC-UIP-110 — **pre-existing** (тест написан под до-BUG-012 семантику; воспроизведен на чистом main). Кандидат в багфикс: переписать ассерт под currentToken-семантику 1beb036.
- Flaky bug014 `test_search_task_view_computed_styles_match_board` (~25%): тестовая гонка (evaluate без expect) — баг-репорт-кандидат, фикс: expect(.task-view-head) перед evaluate.
- 2 API-«фейла» — стенд-артефакты (nginx 413 vs app 422 — транспортный контур; tc_gal_107 без images-env) — не продукт.

## Что НЕ проверено

- Реальное железо/iOS — приемка 5.2 (Заказчик).
- pixel-perfect дубль-сверка скриншотов (сверка ключевых значений live-DOM).

## Границы

Запись: этот файл. Код не правился. Стенды погашены (ПМ, 00:25 UTC).
