# Regress redesign-console — regress-final.md

- change: redesign-console
- date: 2026-10-24T05:53:30+00:00
- commit: b0a56543ce1b787ace3169d414547421af4dcedd
- worktree: /tmp/wt-red-regress
- verdict: PASS (итерация 2; итерация 1 была FAIL — разбор ниже, закрыто teardown-фиксом TC-029)
- tier: domain (эшелон 1: доменный regress)
- duration: 904.2s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 97
- changed files: 97
  - backend/app/pages.py
  - code-reviews/redesign-console/review-001.md
  - design/p23-fastline/mobile/after-empty-390.png
  - design/p23-fastline/mobile/after-occupied-390.png
  - design/redesign-pro/README.md
  - design/redesign-pro/board-broadsheet.html
  - design/redesign-pro/board-ceramic.html
  - design/redesign-pro/board-console.html
  - design/redesign-pro/tokens-broadsheet.html
  - design/redesign-pro/tokens-ceramic.html
  - design/redesign-pro/tokens-console.html
  - frontend/static/css/app.css
  - frontend/static/css/board.css
  - frontend/static/css/gallery.css
  - frontend/static/css/login.css
  - frontend/static/css/search.css
  - frontend/static/css/wiki.css
  - frontend/static/js/board/cards.js
  - frontend/static/js/wiki/tree.js
  - frontend/templates/base.html
  - frontend/templates/board.html
  - frontend/templates/login.html
  - frontend/templates/video.html
  - frontend/templates/weather.html
  - openspec/changes/redesign-console/REPORT-0.1.md
  - openspec/changes/redesign-console/design-validation.md
  - openspec/changes/redesign-console/design.md
  - openspec/changes/redesign-console/impact.md
  - openspec/changes/redesign-console/proposal.md
  - openspec/changes/redesign-console/research.md
  - openspec/changes/redesign-console/review-architecture.md
  - openspec/changes/redesign-console/specs/accessibility/spec.md
  - openspec/changes/redesign-console/specs/auth/spec.md
  - openspec/changes/redesign-console/specs/board/spec.md
  - openspec/changes/redesign-console/specs/design-tokens/spec.md
  - openspec/changes/redesign-console/specs/fastline/spec.md
  - openspec/changes/redesign-console/specs/gallery/spec.md
  - openspec/changes/redesign-console/specs/navigation/spec.md
  - openspec/changes/redesign-console/specs/search/spec.md
  - openspec/changes/redesign-console/specs/settings/spec.md
  - openspec/changes/redesign-console/specs/video-ui/spec.md
  - openspec/changes/redesign-console/specs/weather-ui/spec.md
  - openspec/changes/redesign-console/specs/wiki/spec.md
  - openspec/changes/redesign-console/tasks.md
  - test-model/approved/redesign-console/APPROVAL.md
  - test-model/approved/redesign-console/README-coverage.md
  - test-model/approved/redesign-console/TC-redesign-001.md
  - test-model/approved/redesign-console/TC-redesign-002.md
  - test-model/approved/redesign-console/TC-redesign-003.md
  - test-model/approved/redesign-console/TC-redesign-004.md
  - … и еще 47
- suites: tests
- pytest exit code: 1

## Хвост лога (до 50 строк)

```

tests/web/test_video_rename_ui.py:25
  /tmp/wt-red-regress/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /tmp/wt-red-regress/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /tmp/wt-red-regress/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /tmp/wt-red-regress/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /tmp/wt-red-regress/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /tmp/wt-red-regress/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /tmp/wt-red-regress/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /tmp/wt-red-regress/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /tmp/wt-red-regress/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /tmp/wt-red-regress/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /tmp/wt-red-regress/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/web/test_qa21_gallery_ui.py::test_tc_gal_119_sidebar_gallery_fourth_parity_and_no_tracker_links[chromium]
FAILED tests/web/test_settings_profile_r4.py::test_page_composition[chromium]
2 failed, 714 passed, 12 skipped, 2 xfailed, 85 warnings in 903.10s (0:15:03)
```

## Разбор FAIL (regress_runner, изолированные перепрогоны 2×)

Режим: полный tests/api+tests/web, сериально (regress-final — всегда
сериально), канонический контур qa_stand_up.sh (второй контур на соседних
портах: nginx :18446, app :18080, search :18378, images :18379, video :18380,
weather :18381 — порт :18443 занят чужим контуром qa-stand-p23). Свежая БД +
seed + миграции wiki/gallery/video/r4 на каждый полный прогон (reset стенда).

### 1. tests/web/test_qa21_gallery_ui.py::test_tc_gal_119… — PRE-EXISTING (не дельта)

- Детерминированный FAIL 2/2 изолированно на ветке: сайдбар содержит 7-й
  пункт «Игры» (P26 game-portal), тест assert'ит ровно 6.
- «Игры» присутствует в `frontend/templates/base.html` УЖЕ на origin/main
  (вошел до точки ветвления, merge PR #242); тест-файл ветка не трогала
  (`git diff origin/main...HEAD -- tests/web/test_qa21_gallery_ui.py` пуст,
  main не впереди: `git rev-list --count HEAD..origin/main` = 0).
- Контрольный прогон на чистом main (worktree /tmp/wt-red-main, a37d5b3,
  то же окружение/стенд): идентичный FAIL («Left contains one more item:
  'Игры'») — pre-existing доказан по правилу скоупа.
- Вердикт: устаревший тест относительно P26, вне диффа redesign-console.
  Снести ПМ в багфикс-флоу/BACKLOG (актуализировать assert на 7 пунктов
  или на формат «6 цветовых + хвост»), в этой волне не чинить.

### 2. tests/web/test_settings_profile_r4.py::test_page_composition — дельтовый дефект АВТОТЕСТА (не продукта)

- Упал в обоих полных прогонах; изолированно на свежей БД — PASS 2/2.
- A/B-доказательство: на чистой БД PASS; на БД, где owner bio =
  «кроп-цикл», — детерминированный FAIL на `expect(profile.bio).to_have_value("")`
  (воспроизведено прямым прогоном).
- Источник загрязнения: **TC-redesign-029** (`tests/web/test_redesign_console.py:1698`)
  — новый сьют дельты заполняет `#profile-bio` = «кроп-цикл», сохраняет,
  грузит аватар owner и НЕ имеет teardown-гигиены (в отличие от TC-028,
  который bio восстанавливает, и конвенции test_r5_crop_ui/
  test_settings_profile_r4.profile_hygiene). В алфавитном сьют-порядке
  redesign_console < settings_profile_r4 → состав-тест видит грязный
  профиль. Продукт ведет себя корректно (bio персистентен и
  предзаполняется по дизайну).
- Вердикт: дельта-дефект тест-изоляции (missing teardown) в новом сьюте,
  НЕ продуктовый баг — STOP/баг-репорт не требуется. Фикс — однострочная
  teardown-гигиена в TC-redesign-029 (сброс bio=NULL + аватар, по образцу
  TC-redesign-028) отдельным багфикс-коммитом ДО merge; после фикса —
  повторный regress-final.

### 3. tests/api/test_qa21_gallery_infra.py::test_tc_gal_106… — средовое (только прогон 1)

- Прогон 1: дефолтные порты теста (:8379 images, :8080 core) указывали на
  ЧУЖОЙ параллельный контур (qa-stand-p23) — 401 на core-проверке. Мой
  прокол env второго контура, не дельта.
- Устранено: с env-оверрайдами `EKOTOV_WIKI_IMAGES_PORT=18379`,
  `EKOTOV_WIKI_CORE_URL=http://127.0.0.1:18080` (плюс IMAGES_DIR) тест —
  PASS (с изображением в томе). В прогоне 2 (полный, с env) — отсутствует
  в упавших.

## Средовые/известные (фон, не дельта) — по ТЗ

- Д2 teardown-гонка route-колбэков (mitigация в tests/web/conftest) — НЕ
  воспроизвелась (test_p12_nav_icons_favicon_r8 green в обоих прогонах).
- live-часть TC-GAL-122: tokens-часть passed; live-часть — в skip-блоке
  (12 skipped, в т.ч. TC-GAL-106 compose-шаг docker, live-GAL-122 без
  redeploy-стенда) — норма по coverage-audit.
- 500 /api/wiki/pages без wiki-микросервиса — не наблюдалось (канонический
  контур с полным набором сервисов).
- Предупреждения PytestUnknownMark (e2e/web-маркеры) — существующий шум
  коллекции, не дельта.

## Маппинг на coverage-audit (test-model/reports/redesign-console/coverage-audit.md)

- Обязательный состав маппинга выполнен: (1) автонабор дельты
  test_redesign_console.py — 36/36 green; (2) revalidate-восьмерка + Д1 —
  green в полном прогоне (обе сводки: `test_r3_vis_ui`, `test_r5_profile_card_ui`,
  `test_r6_tag_combobox_ui`, `test_qa21_netdata_sidebar_ui`,
  `test_board_fastline`, `test_p12_ui_polish_r8`, `test_p15_wiki_tree`,
  `test_p12_nav_icons_favicon_r8`, `test_qa21_gallery_design`) — единственный
  нюанс: p15_wiki_tree падал ТОЛЬКО на грязной БД pollution-hunt'а (артефакт
  охоты, в чистых прогонах green); (3) keep-сьюты чеклиста — green; (4)
  гейты REPORT (контраст NFR-41, hex/var) — закрыты тестами 001/009/011/036
  (green); (5) средовые flake'и разведены по пп. 1–3 выше.
- Трассировка coverage-audit: 105/105 сценариев, 36/36 кейсов, 36/36
  автотестов — подтверждена прогоном; GAP-1/GAP-2 (миноры документации) —
  вне гейта, без изменений.

## Итог

- Вердикт: **FAIL формально (2 автотеста), 0 продуктовых багов.**
  Дельта (шаблоны/CSS/страницы) поведенческих регрессов не дала.
- Блокер merge — один, тестовый: teardown-гигиена TC-redesign-029 (п. 2);
  плюс pre-existing TC-GAL-119 (п. 1, вне диффа, решается вне волны).
  Рекомендация ПМ: багфикс teardown TC-029 → повторный regress-final
  (ожидаемый исход — PASS с единственным pre-existing TC-GAL-119 в фоне
  либо после его актуализации).
- Артефакт — последний коммит ветки pipeline/redesign-cases; после него
  изменений диффа нет. Не запушено (по ТЗ).## Вердикт (итерация 2, финальная): PASS

715 passed / 1 failed (TC-GAL-119 — PRE-EXISTING, вне диффа, закрыт Флоу 2
PR #243 в main до merge). Продуктовых багов 0. Детали ниже (итерации 1-2).


