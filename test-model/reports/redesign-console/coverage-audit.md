# Coverage-аудит: сценарий дельты → кейс → автотест (redesign-console, задача 3.5)

> Дата: 2026-10-24 | Роль: qa_coverage_auditor (Флоу 1, задача 3.5,
> прецедент REPORT-coverage-audit) | Ветка `pipeline/redesign-cases`,
> worktree /tmp/wt-red-cases, HEAD 55d2a78 (3.4 закрыт). Независимая
> сверка: парсер дельт + парсер чеклиста/кейсов/тестов + фактические
> прогонами на изолированном автостенде (см. «Факты прогонов»).

## Объем и метод

- Дельты: `openspec/changes/redesign-console/specs/` — 12 capability,
  25 Requirement, **105 Scenario** (парсер `#### Scenario:`; раскладка:
  accessibility 7, auth 7, board 14, design-tokens 9, fastline 5,
  gallery 3, navigation 20, search 13, settings 13, video-ui 2,
  weather-ui 3, wiki 9 = 105).
- Цепочка: сценарий → CHK-NNN (чеклист) → кейс
  `test-model/new/redesign-console/TC-redesign-NNN.md` → автотест
  `tests/web/test_redesign_console.py` (TC-ID в docstring) + существующие
  green-тесты из чеклиста. Сверка программная (нормализация имен,
  точные/подстрочные совпадения), не «на глаз».

## Результат трассировки

- **Кейсы: 36/36** (TC-redesign-001…036), раскладка 1:1 с CHK-001…036,
  приоритет кейса = приоритету CHK (Must 35 / Should 1 — TC-redesign-032).
- **Автотесты: 36/36** — по каждому кейсу ровно один тест, TC-ID в
  docstring, дубликатов и тестов без кейса нет (парсер docstring).
- **Сценарии: 105/105 покрыты** цепочкой; **GAP-блокеров: 0**.

Раскладка сценарий→CHK по группам (полные имена сценариев — в кейсах,
колонка «Источник» чеклиста; сверено парсером):

| CHK (→TC, тест `test_tc_redesign_NNN_*`) | Сценариев дельты | Приоритет |
|---|---|---|
| 001→001 contrast_aa | 2 (программная проверка пар; подписи hover-подложек) | Must |
| 002→002 focus_visible | 2 (таб-фокус; клик без ринга) | Must |
| 003→003 reduced_motion | 2 (глобальный reduce; всплывашки доски — CHK-007) | Must |
| 004→004 skip_link | 2 (первый в таб-порядке; невидим без фокуса) | Must |
| 005→005 login_fn (+test_auth_ui, keep) | 3 (успешный; неверный пароль; несуществующий) | Must |
| 006→006 login_visual | 4 (форма «Пульта»; cyan-фокус; ошибка; хуки) | Must |
| 007→007 board_semantics (+test_board_*, bug014, keep) | 7 (открытие ×2, assigned ×2, tooltip, всплывашки, reduce) | Must |
| 008→008 board_visual | 5 (визуал; LED; приоритеты; fast-карточка; **существующее поведение не деградировало** — см. GAP-1) | Must |
| 009→009 board_effects (+grep-гейт 2.7) | 2 (нет окраски/cyan-декора; hover ступенями) | Must |
| 010→010 tokens_source | 2 (перенос дословно; служебные определены) | Must |
| 011→011 v3_removed_cache | 2 (V3 не используются; `?v=redesign-1`) | Must |
| 012→012 accent_roles | 2 (cyan не декор; amber glow только сигнал) | Must |
| 013→013 techno_language | 3 (HUD; LED-состояния; mono-данные) | Must |
| 014→014 fastline_signal (+test_board_fastline, fixed) | 3 (на доске; янтарный канал; пустая) | Must |
| 015→015 fastline_behavior (+dnd-сьют, keep) | 2 (поведение не изменилось; ≤860px) | Must |
| 016→016 gallery_visual | 2 (сетка dark; лайтбокс) | Must |
| 017→017 gallery_tests (+TC-GAL-122, Д1 fixed) | 1 (тесты без цветовых правок проходят) | Must |
| 018→018 sidebar_hooks (+netdata/navigation_search, keep) | 4 (переходы ×2, все страницы, хуки) | Must |
| 019→019 sidebar_visual | 2 (визуал «Пульта»; актив по cyan) | Must |
| 020→020 settings_nav (+p12n004, keep) | 4 (внизу слева; переход; все страницы; стиль) | Must |
| 021→021 profile_block (+test_r5_profile_card, fixed) | 5 (отображение; display_name; аватар; клик; сессионный) | Must |
| 022→022 profile_constraints | 3 (нет аватарок-файлов/смены пароля; верстку не ломает; визуал) | Must |
| 023→023 mobile_frame | 2 (каркас ≤860px; тач-таргеты) | Must |
| 024→024 search_results (+navigation_search, keep) | 4 (переход; assigned/creator; пустой; dark) | Must |
| 025→025 filters (+поисковые, keep) | 7 (один признак; исполнитель; создатель; «без исполнителя»; подсказки из БД; комбинация; пустой запрос) | Must |
| 026→026 filter_dark (+test_r6_tag_combobox, fixed) | 2 (форма dark; тесты поиска green) | Must |
| 027→027 settings_access | 4 (доступ; негатив; dark; категории) | Must |
| 028→028 user_settings | 7 (единая карточка; функции Р4; открытие; негатив; только свои; одна колонка; независимость) | Must |
| 029→029 profile_crop (+test_r5_crop_ui, keep) | 2 (карточка на токенах; кроп на dark) | Must |
| 030→030 video (+video-сьют, keep) | 2 (список «Пульт»; функциональность) | Must |
| 031→031 weather_readout (+test_weather_ui, keep) | 2 (readout; ошибка/пустые) | Must |
| 032→032 weather_no_edits | 1 (тесты погоды без цветовых правок) | **Should** |
| 033→033 breadcrumb (+test_p15_wiki_tree, fixed) | 3 (цепочка; корень; микролейбл) | Must |
| 034→034 rich_visual | 3 (h2/h3; спойлер; код/таблица) | Must |
| 035→035 rich_sanitize | 1 (санитизация/редактор) | Must |
| 036→036 wiki_visual (+test_p15_wiki_tree, fixed) | 2 (дерево; редактор/история) + hex-гейт | Must |

## GAP-таблица и классификация

Блокеров (Must-сценарий без полной цепочки) — **0**. Найдено два
неблокирующих расхождения документационного слоя:

| # | Суть | Слой | Классификация | Действие |
|---|---|---|---|---|
| GAP-1 | Сценарий board «Существующее поведение доски не деградировало» не назван дословно в «Источнике» CHK-008 чеклиста (перечислены 4 визуальных сценария). Цепочка при этом полная: сценарий в кейсе TC-redesign-008 (строка Scenario), тест 008 проверяет каркас (#board data-loaded, колонки, LED), поведенческая часть — существующие нецветовые сьюты доски (test_board_tasks_ui/assign, bug014 — keep, regress-final) | трассировка чеклиста | минор (документация; цепочка кейс+тест+регресс замкнута, Must закрыт) | дополнить «Источник» CHK-008 четвертым сценарием при следующей правке чеклиста; в 3.5 не правится (кейсы/тесты не трогаем) |
| GAP-2 | TC-redesign-032 — единственный Should, но файловый `pytestmark` ставит `must` всему модулю (маркер уровня файла, не теста) | маркировка автотеста | косметика (приоритет кейса и отчетов считается по кейсам; прогон не искажается) | опционально: снять файловый must / точечный маркер на 032 в попутной правке |

Should-классификация: единственный Should-сценарий (CHK-032, «тесты
погоды без цветовых правок») покрыт полностью (кейс + тест
tc_redesign_032, статическая проверка V3-значений и снимка weather.html)
— принятого риска не требуется, фикс не требуется.

## Сверка правок существующих тестов с impact.md (задача 3.1)

Прогноз impact.md §«Сломающиеся тесты» — 8 web-файлов; фактически
исправлены 8 + 1 (Д1). Сверка коммитов и рецептов:

| Файл | impact п. | Коммит фикса | Рецепт соблюден | Прогон 3.5 |
|---|---|---|---|---|
| test_qa21_netdata_sidebar_ui.py | 1 | 7edd3ff (2.1) | да | green |
| test_r6_tag_combobox_ui.py | 2 | 2697d55 (2.5) | да | green |
| test_board_fastline.py | 3 | c7fdbde (2.2) | да | green |
| test_p12_ui_polish_r8.py | 4 | c7fdbde; Д3-докстринг 55d2a78 | да | green |
| test_p15_wiki_tree.py | 5 | 230c170 (2.3) | да | green |
| test_r5_profile_card_ui.py | 6 | 97035f9 (2.4) | да | green |
| test_r3_vis_ui.py | 7 | c7fdbde; Д3-докстринг 55d2a78 | да (ассерты) | green |
| test_p12_nav_icons_favicon_r8.py | 8 | 7edd3ff (2.1, `%23f0b45c`) | да | green (см. flake ниже) |
| Д1: tests/api/test_qa21_gallery_design.py (TC-GAL-122) | доп. п.9 | 06515ee (3.4) | да: accent `#f0b45c`, soft `--p-amber-900/#3a2c12`, whitelist rgba-баз `{14,22,33}` — ровно рецепт impact.md | tokens-тест **passed**, live-часть корректно skipped без env стенда |

Grep-контроль: V3-значений в ассертах tests/ нет — единственные вхождения
в `test_redesign_console.py` (негативные списки-гейты, по конструкции) и
в докстрингах (поз. 4/7 после Д3 — описание истории маппинга, не ассерты).

Д2 (teardown-гонка route-колбэков, `test_p12_nav_icons_favicon_r8`):
митигирована try/except вокруг `route.fulfill` в tests/web/conftest.py
(06515ee). В прогоне 3.5 флейк воспроизвелся 1 раз из 1 пакетного прогона
(60 passed, 1 error на том же тесте) — средовой, вне дельты, на гейт не
влияет (прецедент прогонов A/B impact.md). Классификация: известный
средовой flake, не GAP дельты.

Д3: докстринги поправлены (55d2a78); в test_r3_vis_ui.py:6 осталась
косметическая шероховатость формулировки («янтарь «Пульта»овый акцент»)
— на ассерты и трассировку не влияет, минор.

## Факты прогонов (3.5, изолированный автостенд, python venvs/wiki)

- `tests/web/test_redesign_console.py` — **36 passed** (85.7s).
- 8 файлов impact-восьмерки одной сессией — **60 passed, 1 error**
  (error = известная teardown-гонка Д2, средовой) — воспроизведение
  факта прогонов A impact.md.
- `tests/api/test_qa21_gallery_design.py` без env стенда —
  **1 passed, 1 skipped** (Д1 закрыт; с «грязным» env
  EKOTOV_WIKI_DB_PATH=/tmp/red-qa.db live-часть падает на живом
  nginx-стенде :18443, который еще серверит V3-статику main, —
  средовое, к дельте не относится).
- Итог зеленого контура дельты: 36 + 60 + 1 = **97 passed** (заявленные
  «40 passed» в статусе головы соответствуют прогону 3.4 иного состава;
  собственной проверкой подтверждено 36/36 нового набора).

## Маппинг на regress-final (задача 4.1)

Дифф дельты — frontend-ассеты + static_v + 1 строка pages.py (смешанный
дифф backend+frontend). По regress-domains.json (rules пустые,
collapse on, прецедент j52-j54-mirror 598 passed) базовый режим —
полный прогон `pytest tests/api tests/web`. Явный обязательный состав:

1. **Новый автонабор дельты**: `tests/web/test_redesign_console.py`
   (36, TC-redesign-001…036).
2. **revalidate-восьмерка + Д1** (9 файлов, таблица выше) — подтверждение
   фиксов на регрессе.
3. **keep-сьюты, названные чеклистом как носители поведенческих
   сценариев**: test_auth_ui; test_board_tasks_ui, test_board_assign_ui,
   test_bug014*, dnd-сьют (test_board_fastline + dnd_helpers + p23-mobile);
   test_qa21_netdata_sidebar_ui, test_navigation_search_ui,
   test_p12n004_sidebar_footer*; test_r5_profile_card_ui,
   test_r5_crop_ui (TC-r5crop-409…414), test_r6_tag_combobox_ui;
   settings/video/weather-сьюты (test_video_rename_ui, test_weather_ui);
   wiki: test_p15_wiki_tree/page/editor/history, tests/api/test_wiki_rich*;
   галерея-keep: test_qa21_gallery_ui, test_p14_41_lightbox_swipe,
   test_p12_gallery_rename_masonry_r8.
4. **Гейты из REPORT волн** (повторный прогон в 4.1): контраст-скрипт
   (гейт 1.1, NFR-41), hex/var()-гейты 2.7 (board/wiki/gallery.css) —
   в автонаборе закрыты тестами 001/009/011/036, сверка REPORT-фактов —
   шаг 4.1.
5. Средовые flake'и при приемке 4.1 не смешивать с дельтовыми: Д2-teardown
   (p12_nav_icons), live-часть TC-GAL-122 (только при redeploy стенда
   веткой; до того — skip по env — норма).

## Вердикт

**Блокеров нет.** Трассировка «сценарий → кейс → автотест» полная:
105/105 сценариев, 36/36 кейсов, 36/36 автотестов, приоритеты 1:1;
правки существующих тестов соответствуют impact.md (8/8 + Д1 по рецептам,
прогоны зеленые). Два минора документационного слоя (GAP-1, GAP-2) — вне
гейта. Готово к regress-final (4.1) по маппингу выше.
