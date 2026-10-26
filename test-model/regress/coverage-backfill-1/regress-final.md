# Regress coverage-backfill-1 — regress-final.md

- change: coverage-backfill-1
- date: 2026-10-26T18:26:51+00:00
- commit: 89c85f8cb71eb7baf665e61fbfbfbc7543bb68d3 (origin/chore/sa-coverage-backfill, HEAD = 89c85f8 «[coverage-backfill-1] тест-изоляция: teardown QAP14L-загрузок, restore display_name, сеящая фикстура категорий»)
- worktree: /tmp/wt-reg-cov2 (детач от origin/chore/sa-coverage-backfill)
- verdict: FAIL (итерация 2 — формально: 3 красных полной серии tests/web, все 3 green в пересценарии на свежем стенде — тест-изоляция/зависимость от сьют-порядка, 0 продуктовых багов; итерация 1 была FAIL — изоляция, исправлено 89c85f8)
- tier: full regress-final (tests/api + tests/web полностью, СЕРИАЛЬНО)
- duration: tests/api 122.38s + tests/web 1012.03s (+ пересценарий 3 красных 6.97s)
- diff source: git diff origin/main...HEAD
- pytest exit code: tests/api 0; tests/web 1

## Итерация 2 (этот прогон)

### Окружение

- Стенд пересоздан на свежем стенде после багфикса изоляции 89c85f8:
  `scripts/qa_stand_up.sh reset` из worktree /tmp/wt-reg-cov2, REPO=worktree,
  PY=/home/openclaw/venvs/wiki/bin/python, SECRET_KEY единый на контур.
- Порты (свободный диапазон 18495+; 18443/18445 заняты чужими контурами):
  nginx :18495, app :18496, search :18497, images :18498, video :18499,
  weather :18500; STAND_DIR=/tmp/qa-stand-reg-cov2. Health всех 6 точек — 200
  до прогона; БД проверена до прогона: 2 seed-пользователя (owner display_name
  NULL — restore из 89c85f8 работает), image_categories засеяны (Дом/Работа/
  Личное), схема wiki/gallery/video/r4 на месте.
- env прогона: EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18495,
  EKOTOV_WIKI_DB_PATH=/tmp/qa-stand-reg-cov2/app.db,
  EKOTOV_WIKI_AVATARS_DIR=/tmp/qa-stand-reg-cov2/avatars,
  EKOTOV_WIKI_IMAGES_DIR=/tmp/qa-stand-reg-cov2/images-data,
  EKOTOV_WIKI_IMAGES_PORT=18498, EKOTOV_WIKI_CORE_URL=http://127.0.0.1:18496.
- Проверка исправлений 89c85f8 по месту: TC-P14-108 green и QAP14L-* удалены
  из БД (галерейных count-ассертов каскад не поймал — все 21 красный итерации 1
  из этой волны теперь green); TC-P14-107 green, display_name владельца после
  сьюта не изменён; TC-UIP-107 дошёл до POST задачи — 201 (сеящая фикстура
  категорий работает, 422 итерации 1 не воспроизвёлся).

### Счет

| сьют | green | red | skip | xfail | время |
|---|---|---|---|---|---|
| tests/api | 327 | 0 | 11 | 2 | 122.38s |
| tests/web (полная серия) | 428 | 3 | 3 | 0 | 1012.03s |
| tests/web (пересценарий 3 красных, свежий стенд) | 3 | 0 | 0 | 0 | 6.97s |

- Итого по полной серии: 755 passed / 3 failed / 14 skipped / 2 xfailed;
  после пересценария — 758 passed / 0 failed.
- Известные по ТЗ skip'ы на месте (11 api + 3 web, счет 1:1 с итерацией 1):
  TC-weather-019 (docker-стенд), TC-P14-110 (@pytest.mark.manual) — норма;
  xfail'ы — как ожидалось. Неожиданных skip'ов нет.

### Хвост лога (полная серия, tests/web)

```
FAILED tests/web/test_coverage_uip.py::test_tc_uip_107_ticket_modal_view[chromium]
FAILED tests/web/test_p15_wiki_tree.py::test_wiki_empty_state_create_first_page[chromium]
FAILED tests/web/test_p15_wiki_tree.py::test_wiki_empty_state_button_opens_editor[chromium]
3 failed, 428 passed, 3 skipped, 10 warnings in 1012.03s (0:16:52)
```

### Разбор красных (regress_runner, пересценарий 1× на свежем стенде)

Протокол: после красной полной серии стенд погашен и поднят заново
(qa_stand_up.sh reset — свежая БД/тома), все 3 красных теста перезапущены
одним вызовом, тот же env. Результат: **3 passed / 0 failed** (6.97s).
Продуктовых багов круг 2 не обнаружил; оба дефекта — тест-изоляция/зависимость
от сьют-контекста в ПОЛНОЙ серии (пересценарий малым набором их не ловит).

1. test_p15_wiki_tree.py::test_wiki_empty_state_create_first_page +
   test_wiki_empty_state_button_opens_editor (TC-wiki-004/005)
   - Тесты требуют ПУСТУЮ wiki (`.wiki-empty`); в полной серии к моменту их
     запуска в БД 11 страниц («Спойлер insert-rename», «Спойлер в ячейке»,
     «Табы лимит», «Таблица rNcM», … — aria-snapshot в логе).
   - Источник: tests/web/test_coverage_rich_tools.py (новый дельта-сьют,
     идёт РАНЬШЕ test_p15_wiki_tree по алфавиту) создает эти страницы через
     editor и НЕ удаляет их — teardown-гигиены нет. В итерации 1 эти же 2
     теста красились и были ошибочно отнесены к каскаду TC-P14-108 (карточки
     галереи); пересценарий итерации 1 их «зеленил» только потому, что сьют
     coverage_rich_tools в наборе пересценария отсутствовал. Дефект изоляции
     НЕ был покрыт фиксом 89c85f8 и воспроизвёлся в круге 2.
   - Вердикт: дельта-дефект тест-изоляции (missing teardown созданных
     wiki-страниц в test_coverage_rich_tools.py), НЕ продуктовый баг.
     Фикс: удалять созданные сьютом страницы в teardown (по конвенции
     web_cleanup_created/wiki_api) отдельным багфикс-коммитом ДО merge.

2. test_coverage_uip.py::test_tc_uip_107_ticket_modal_view
   - В полной серии дошёл до финального шага (все композиционные ассерты —
     201 POST, модалка, бейджи, комментарий «owner» — green; фиксы 89c85f8
     работают) и упал на проверке возврата фокуса после Esc:
     `{'tag': 'BUTTON', 'inOverlay': True}` — ожидался НЕ-оверлей.
   - В пересценарии на свежем стенде (тест один в наборе) — PASS. В обоих
     кругах тест падал в полной серии и зеленел малым набором, но КАЖДЫЙ раз
     на другом шаге (ит.1: display_name-загрязнение и 422 категорий — оба
     закрыты 89c85f8; ит.2: фокус после Esc). Зависимость от сьют-контекста
     порядка тестов: rememberViewTrigger/фокус-менеджмент модалки ведет себя
     по-разному в полной серии (вероятная причина — предшествующие тесты
     доски/фокуса в той же странице браузера); точный механизм требует
     разбора с трассировкой.
   - Вердикт: НЕ продуктовый баг в наблюдаемых точках (изолированно
     воспроизводится green), но дельта-тест нестабилен в полной серии —
     третий дефект семьи изоляции/порядка. Фикс: сделать тест
     самодостаточным по фокусу (явное `page.evaluate("document.activeElement.blur()")`
     или перезагрузка доски перед открытием модалки) ЛИБО разобрать
     rememberViewTrigger; проверять повторным ПОЛНЫМ regress-final.

### Итог итерации 2

- Вердикт: **FAIL формально (3 автотеста полной серии; все 3 green в
  пересценарии), 0 продуктовых багов.** Исправления изоляции 89c85f8
  подтвердились: каскад 21 красного итерации 1 не воспроизвёлся, tests/api
  полностью зелен (327/327), собственные кейсы дельта-сьютов green.
- Остаточный хвост — 2 изоляционных дефекта дельты (круг 3):
  (1) test_coverage_rich_tools.py: teardown созданных wiki-страниц;
  (2) test_tc_uip_107_ticket_modal_view: нестабильность фокус-ассерта
  в полной серии. Рекомендация ПМ: багфикс-коммит по пп. 1–2 → повторный
  ПОЛНЫЙ regress-final на свежем стенде (малый пересценарий этих дефектов
  не ловит — проверять полной серией).
- Артефакт — последний коммит ветки [coverage-backfill-1]; после него
  изменений диффа нет. Не запушено (по ТЗ). Стенд погашен.

## Итерация 1 (история — коммит 02a6366, worktree /tmp/wt-reg-cov; НЕ в ветке)

- change: coverage-backfill-1
- date: 2026-10-26T17:16:40+00:00
- commit: aa126681a2916114a90c29c1ca45e5c0be6626b6 (HEAD = aa12668 «[coverage-backfill-1] approved-индекс пакета»)
- verdict: FAIL (формально — 1 красный дельта-тест; 0 продуктовых багов. Каскад из 20 fallback-красных — внутри-серийное загрязнение от нового TC-P14-108, детерминированный красный — TC-UIP-107 от отсутствия teardown в TC-P14-107)
- Счет: tests/api 327/0/11/2 (122.75s); tests/web прогон 1: 410/21/3 (1095.25s);
  пересценарий 21 красного: 20/1 (91.87s). Итого после пересценария
  757 passed / 1 failed.
- Разбор: (1) каскад 20 красных — TC-P14-108 грузил 3 изображения QAP14L-*
  без teardown → count-ассерты галереи видели +3 карточки; (2) TC-UIP-107 —
  TC-P14-107 не восстанавливал display_name владельца («QAP14 Дисплей-нейм»),
  плюс на чистом стенде POST задачи давал 422 `category "Дом" not in
  categories` (тест зависел от чужого сеяния категорий).
- Исход: блокер merge — тест-изоляция дельты; рекомендован багфикс
  (teardown QAP14L-*, restore display_name, сеящая фикстура категорий) —
  выполнен коммитом 89c85f8 и проверен в итерации 2.
