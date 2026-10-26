# QA-чистка: инвентаризация и решение по кандидатам (qa-cleanup-1026)

> Дата: 2026-10-26 | Роль: qa (Флоу 5, qa-artifact-cleanup) | Ветка
> `chore/qa-cleanup-1026` (worktree /tmp/wt-clean-qa, от origin/main,
> HEAD 88ab4a7). Ручка: `qa_artifact_inventory.py` — разделы «осиротевшие»,
> «без TC-маркера», «дубли», «разрывы покрытия» присутствуют.
> Отчет: кандидат → находка → действие.

## Итог

**Удалений нет.** Ни один кандидат инвентаризации не подтвердился как
мусор; обоснования по каждому разделу ниже. Изменения в tests/ и
test-model/ — только этот отчет.

## (а) Осиротевшие наборы test-model/

Кандидаты ручки (44 позиции) — ложные срабатывания детектора «change не
определен»: скрипт сверяет с активными `openspec/changes/`, а все
помеченные наборы — исторические артефакты закрытых change
(approved/, bugs/, regress/, regression/, reports/, reviews/, impact/),
защищенные правилами чистки (approved/ и APPROVAL.md — не трогать;
regress/reports история — прецеденты и аудит).

- `test-model/new/` — пуст; в git пустые каталоги не трекаются, в
  ветке отсутствует, удалять нечего.
- Наборы только архивного change — нет (ручка: пусто).

Действие: без изменений.

## (б) Тесты без TC-маркера

Ручка: **нет** (85 файлов tests/web + tests/api, все с TC-ID).
Действие: не требуется.

## (в) Дубли имен тестов

Кандидат: `test_reduced_motion_no_transition` в
`tests/web/test_r5_crop_ui.py:849` и `tests/web/test_tooltip_r4.py:325`.

Находка: **однофамильцы, не дубли.** Тела разные и проверяют разные
компоненты: R5 — кроп-виджет аватара (NFR-15/ОГР-17 Р4, computed
transition/animation по всем узлам виджета через CDP), tooltip —
всплывашки доски (TC-vis-105, мгновенный показ, transition 0s на
тултипе). Оба ассерта валидны, ослаблять/удалять нечего; конфликтов
pytest нет (имена на уровне модулей).

Действие: оставить оба; удаления нет.

## (г) Разрывы покрытия (TC-ID из approved, которых нет в tests/web+api)

Сверка полнотекстовым поиском по всему репо + отчетам coverage.

### Ложные срабатывания (автотесты есть, вне зоны скана ручки)

- video-hosting: TC-vid-005…035 — покрыты сервисными тестами
  `services/video/tests/` (test_videos_service, test_converter,
  test_social, test_list_search_order, test_nfr_nonblocking — маркеры
  TC-vid в docstring). TC-vid-004 — живой прогон, зафиксирован как
  BUG-video-001; TC-vid-036 — процессный кейс (мокапы, review-001/002)
  — оба «manual» по REPORT-coverage-matrix.md. Норма.
- weather-service: TC-weather-002…004, 010…014, 020…022 — покрыты
  `services/weather/tests/test_weather_service.py`.
- add-ui-polish-r8: TC-P12G-001/002 — покрыты
  `services/images/tests/test_images_service.py`.

### Осознанный остаток (документирован, норма)

- add-wiki (TC-wiki-4xx): вся матрица в
  `test-model/reports/add-wiki/REPORT-coverage-audit.md` — covered через
  другие TC-ID (например TC-wiki-411→TC-wiki-001/004…006, 412→307/309,
  413→101/102, 417→202/204/205/206), NFR — script-only (402 perf,
  405 migration, 406 DV/кроссбраузер), процессные — 421 smoke /
  422 regress / 423 приемка Заказчика; документированные GAP G1–G5
  (в т.ч. принятый риск G4 «хвост 6.x») — вне гейта этой чистки.

### Реальные разрывы — на решение ПМ (НЕ закрывались этой чисткой)

Автотестов нет нигде в репо (проверено полнотекстово); кейсы Must, кроме
отмеченных:

- add-responsive-mobile: TC-P14-101…110 (10 × Must) — ни маркеров, ни
  reports/ по change.
- add-ui-polish-r8: TC-P12G-008/009/010/011, TC-P12N-005/008/009,
  TC-UIP-102/107/114 (Must) — упомянуты только в reviews/code-reviews.
- p12-rich-tools: TC-rich-001…039 — фигурируют только в
  reports/p12-rich-tools/qa-report-1.md и reviews; автотестов с этими
  маркерами нет (rich-сьют tests/api/test_wiki_rich* маркеров TC-rich не
  несет).
- p23-fastline: TC-p23-109…121 (12 × Must + TC-p23-116 Should) —
  tests/web/test_board_fastline.py покрывает 101–108,
  test_p23_fastline_mobile_ui.py — 122–125; 109–121 нигде.
- weather-service: TC-weather-005…009, 015…019, 023…025 (Must) — только
  в regress-final.md.

Действие: не помечены удалением и не «закрывались» изобретением
трассировки (запрещено). Вынесены ПМ: написать автотесты / зафиксировать
Should-решение в coverage-audit по каждому change. Единственный Should
(TC-p23-116, визуальный ОВ-4) — без автотеста по классификации норма,
помечен здесь.

## Прогон

- Затронутые наборы: `tests/web/test_redesign_console.py` (единственный
  правленный тест) — на изолированном стенде (venv wiki, tmp-БД, свой
  порт, EKOTOV_WIKI_AVATARS_DIR=/tmp/qa-clean-avatars):
  **36 passed** (91.7s).

### Находка прогона: TC-redesign-011 отставал от бампа static_v

- Кандидат: 2 failed в первом прогоне (011, 021) на HEAD origin/main
  (88ab4a7).
- Находка: 021 — средовой flake (rerun solo — passed, прецедент Д2
  coverage-audit). 011 — реальный разрыв: коммит 5d8f249 ([BUG-004],
  2026-10-26) бампнул `static_v` в backend/app/pages.py до
  `redesign-1a`, но гейт-ассерт теста (строка 834) продолжал требовать
  `"redesign-1"` — с closed-quote подстрока не совпадает, тест красный
  на main.
- Действие: ассерт синхронизирован с текущим значением бампа
  (`redesign-1a`), докстринг дополнен ссылкой на 5d8f249. Гейт не
  ослаблен — проверка значения static_v сохранена 1:1, отслеживается
  новый документированный бамп.
