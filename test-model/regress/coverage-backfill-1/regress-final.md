# Regress coverage-backfill-1 — regress-final.md

- change: coverage-backfill-1
- date: 2026-10-26T19:27:52+00:00
- commit: bb547a75b085d436eb742042ad71683641aa91c3 (HEAD = bb547a7 «[coverage-backfill-1] круг 3 тест-гигиены: teardown wiki-страниц rich_tools (register editor-страниц), самодостаточность фокуса UIP-107 (blur+wait перед ассертом, ассерт не ослаблен)»)
- worktree: прогон — /tmp/wt-cov-iso3 (fix/cov-backfill-isolation-3 @ bb547a7); артефакт — /tmp/wt-cov-art (chore/cov-artifact)
- verdict: PASS (итерация 3: полная серия 431/0/3 на свежем стенде @ bb547a7; итерации 1-2 были FAIL — изоляция, исправлено 89c85f8+bb547a7)
- tier: full regress-final (tests/api + tests/web полностью, СЕРИАЛЬНО)
- duration: tests/web 1019.08s (полная серия); tests/api в том же контуре (326 passed + 1 средовый, эффективно 327/0)
- diff source: git diff origin/main...HEAD
- pytest exit code: tests/web 0; tests/api 0 (единственный средовый красный test_avatar_r4 — после согласования AVATARS_DIR и перезапуска app модуль green 9/9)

## Итерация 3 (этот прогон)

### Окружение

- Стенд пересоздан на свежем стенде в worktree /tmp/wt-cov-iso3 @ bb547a7
  (круг 3 тест-гигиены: teardown wiki-страниц rich_tools + самодостаточность
  фокуса UIP-107; прод-код не тронут — только tests/web):
  `scripts/qa_stand_up.sh reset`, PY=/home/openclaw/venvs/wiki/bin/python,
  SECRET_KEY единый на контур.
- Порты: nginx :18505, app :18506, search :18507, images :18508, video :18509,
  weather :18510; STAND_DIR=/tmp/qa-stand-cov-iso3. Health всех 6 точек — 200
  до прогона; БД чистая (3 seed-пользователя, схема на месте).
- Порядок (канонический regress): сначала tests/api (сеет справочник категорий
  r2_seed_categories), затем полная серия tests/web, тот же env.
- env прогона: EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18505,
  EKOTOV_WIKI_DB_PATH=/tmp/qa-stand-cov-iso3/app.db,
  EKOTOV_WIKI_IMAGES_DIR=/tmp/qa-stand-cov-iso3/images-data,
  EKOTOV_WIKI_IMAGES_PORT=18508, EKOTOV_WIKI_CORE_URL=http://127.0.0.1:18506;
  EKOTOV_WIKI_AVATARS_DIR согласован со стендом после дотяжки (см. замечание
  ниже).

### Замечание: AVATARS_DIR в scripts/qa_stand_up.sh (симптом, вне скоупа)

- Скрипт стартует app с жёстко зашитым `AVATARS_DIR=${STAND_DIR}/avatars`
  (строка start_all-блока), не учитывая внешний `EKOTOV_WIKI_AVATARS_DIR`
  тестового контура: при расхождении тесты, сверяющие путь аватара строкой
  (tests/api/test_avatar_r4.py), краснеют средово
  (`'/tmp/qa-stand-.../avatars/1.png' != '<внешний>/1.png'`).
- Симптом воспроизводится только при несовпадении двух путей; в этом прогоне
  устранён перезапуском app с тем же AVATARS_DIR, что в тестовом env (модуль
  green 9/9). Фикс скрипта — отдельным изменением, вне скоупа
  coverage-backfill-1.

### Счет

| сьют | green | red | skip | xfail | время |
|---|---|---|---|---|---|
| tests/api | 326 (+1 средовый, см. замечание — эффективно 327) | 0 | 11 | 2 | в том же контуре |
| tests/web (полная серия, свежий стенд) | 431 | 0 | 3 | 0 | 1019.08s (0:16:59) |

- Итого: tests/web 431 passed / 0 failed / 3 skipped; tests/api эффективно
  327 passed / 0 failed. Продуктовых багов не обнаружено.
- Известные по ТЗ skip'ы на месте: TC-weather-019 (docker-стенд),
  TC-P14-110 (@pytest.mark.manual), +1 штатный — норма. Неожиданных
  skip'ов и красных нет.
- Хвост лога: `431 passed, 3 skipped, 10 warnings in 1019.08s (0:16:59)`.

### Проверка исправлений круга 3 (bb547a7) по месту

- Teardown wiki-страниц rich_tools: 11 editor-страниц (TC-rich-001/003/004/
  005/006/011/012/018/019/020/021) регистрируются через wiki_api.register —
  test_p15_wiki_tree empty-state кейсы (TC-wiki-004/005) green в ПОЛНОЙ серии.
- UIP-107 фокус: blur перед открытием + polling-ожидание возврата фокуса
  (ассерт не ослаблен) — test_tc_uip_107_ticket_modal_view green в ПОЛНОЙ серии.

### Итог итерации 3

- Вердикт: **PASS — полная серия 431/0/3 на свежем стенде @ bb547a7.**
  Оба остаточных дефекта итерации 2 закрыты коммитом bb547a7; исправления
  изоляции 89c85f8 подтверждены повторно (каскад галереи, display_name,
  сеящая фикстура категорий — все green в полной серии).
- Блокер merge снят. Артифакт — последний коммит ветки [coverage-backfill-1];
  после него изменений диффа нет.

## Итерация 2 (история — коммит 7da8fc7)

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
