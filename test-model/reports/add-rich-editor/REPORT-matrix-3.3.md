# REPORT-matrix-3.3: матрица approved-кейсов ↔ автотесты (change add-rich-editor)

- **Ветка:** `pipeline/add-rich-editor` | **Этап:** Флоу 1, 3.3 (qa_automation)
- **Approved:** `test-model/approved/add-rich-editor/` — 47 TC (blocks 20, compat 9, security 16, perf 2)
- **Дата:** 2026-10-16 (UTC)
- **Прогон:** см. §Прогон в конце; стенд — прод-топология процессами (nginx :18443 → app :8093, search :8378, images :8379; БД /tmp/qa33_app.db с полной схемой+seed), интерпретатор `/home/openclaw/venvs/wiki/bin/python` (прецедент test-model/reports/add-wiki/REPORT-4.1-api.md §1).
- **Статусы:** **covered** — покрывается существующим тестом(ами); **ДОБАВЛЕНО** — тест добит на этапе 3.3; **partial** — автоматизирована часть шагов кейса (остаток — НФТ-процедура/ручной шаг, причина указана).

## Реестр тест→TC, добавленных на этапе 3.3 (rule 6)

| Файл | Тест | TC |
|---|---|---|
| tests/api/test_sanitize_rich.py | test_script_sweep_across_block_types | TC-sec-304 |
| tests/api/test_sanitize_rich.py | test_iframe_sweep_across_block_types | TC-sec-306 |
| tests/api/test_sanitize_rich.py | test_object_embed_sweep_across_block_types | TC-sec-307 |
| tests/api/test_sanitize_rich.py | test_event_handler_sweep_across_block_types | TC-sec-309 |
| tests/api/test_sanitize_rich.py | test_javascript_url_sweep_spoiler_case_and_data_links | TC-sec-311 |
| tests/api/test_sanitize_rich.py | test_dangerous_attributes_sweep_across_block_types | TC-sec-312 |
| tests/api/test_sanitize_rich.py | test_sanitizer_bypass_classes_neutralized | TC-sec-315 |
| tests/api/test_sanitize_rich.py | test_sanitizer_encoded_and_control_char_urls_inert | TC-sec-315 |
| tests/api/test_rich_blocks.py | test_table_cell_content_boundaries | TC-blocks-103 |
| tests/api/test_rich_blocks.py | test_columns_count_boundaries | TC-blocks-105/106 |
| tests/api/test_wiki_api.py | test_structural_error_new_content_fallback_no_422 | TC-compat-207 (+ TC-blocks-107 API-половина, шаг 2 TC-blocks-106) |
| tests/api/test_wiki_api.py | test_image_scale_survives_other_edits_and_re_save | TC-blocks-115 |
| tests/web/test_rich_editor.py | test_table_structure_edit_no_content_loss | TC-blocks-102 |
| tests/web/test_rich_editor.py | test_callout_type_change_keeps_text | TC-blocks-109 |
| tests/web/test_rich_editor.py | test_columns_view_order_and_boundaries | TC-blocks-105/106 |
| tests/web/test_rich_editor.py | test_block_combinations_in_containers | TC-blocks-119/120 |

Инфра-правка (не тест): `pytest_plugins = ["pytest_playwright"]` перенесен из
tests/web/conftest.py в корневой conftest.py — pytest 9 собирает `pytest tests/`
с ошибкой «pytest_plugins in a non-top-level conftest» (документированная
миграция pytest; поведение набора не меняется).

## Матрица blocks (20)

| Approved TC | Автотест(ы) | Статус |
|---|---|---|
| TC-blocks-101 | test_rich_editor::test_view_table_3x2_and_two_columns (TC-rich-104) | covered |
| TC-blocks-102 | test_rich_editor::test_table_structure_edit_no_content_loss | ДОБАВЛЕНО |
| TC-blocks-103 | test_rich_blocks::test_table_cell_content_boundaries (1×1/10×10/пустая/`\|`/псевдо-GFM) + test_parse_gfm_table + test_serialize_canonicalizes_table_spacing | ДОБАВЛЕНО |
| TC-blocks-104 | test_rich_editor::test_view_table_3x2_and_two_columns (TC-rich-104, две колонки) | covered |
| TC-blocks-105 | test_rich_blocks::test_columns_count_boundaries (порядок 3 колонок) + test_rich_editor::test_columns_view_order_and_boundaries (DOM-порядок) | ДОБАВЛЕНО |
| TC-blocks-106 | test_rich_blocks::test_columns_count_boundaries (1/6/8 колонок, круговая преобразуемость) + test_rich_editor::test_columns_view_order_and_boundaries (6/8 на просмотре) + test_wiki_api::test_structural_error_new_content_fallback_no_422 (пустая колонка → fallback) | ДОБАВЛЕНО; см. Дивергенцию D-1 |
| TC-blocks-107 | test_rich_editor::test_editor_blocks_save_on_structural_error (TC-rich-110, ошибка до сохранения) + test_wiki_api::test_structural_error_new_content_fallback_no_422[незакрытый :::columns → 200] | covered + ДОБАВЛЕНО (API-половина) |
| TC-blocks-108 | test_rich_editor::test_view_callout_types_aside_spoiler_code_image (TC-rich-105) | covered |
| TC-blocks-109 | test_rich_editor::test_callout_type_change_keeps_text (info→success→warn→info, текст цел) | ДОБАВЛЕНО |
| TC-blocks-110 | test_rich_editor::test_view_callout_types_aside_spoiler_code_image (TC-rich-105, врезка отличима) | covered |
| TC-blocks-111 | test_rich_editor::test_spoiler_hidden_reveal_reload (TC-rich-106) | covered |
| TC-blocks-112 | test_rich_editor::test_spoiler_hidden_reveal_reload (TC-rich-106: раскрытие без reload, сокрытие после reload) | covered |
| TC-blocks-113 | test_rich_editor::test_view_callout_types_aside_spoiler_code_image (TC-rich-105, код на просмотре) + test_rich_blocks::test_parse_code_block_literal (whitespace/спецсимволы) | covered |
| TC-blocks-114 | test_rich_blocks::test_parse_image_with_width (первичный критерий {width=50}) + test_rich_editor::test_editor_opens_rich_page_and_preserves_content (style.width == "50%" на рендере) | covered |
| TC-blocks-115 | test_wiki_api::test_image_scale_survives_other_edits_and_re_save | ДОБАВЛЕНО |
| TC-blocks-116 | test_rich_blocks::test_parse_image_width_outside_whitelist_dropped + test_sanitize_rich::test_image_width_whitelist_10_100 (9/10/50/100/101) + test_wiki_api::test_structural_error_new_content_fallback_no_422[width=9 → fallback] | covered + ДОБАВЛЕНО (API-половина) |
| TC-blocks-117 | test_rich_editor::test_editor_opens_rich_page_and_preserves_content (TC-rich-108) + test_parser_matches_backend_on_grammar_fixtures (TC-rich-101) | covered |
| TC-blocks-118 | test_rich_editor::test_table_inside_column_view (TC-rich-107) + test_rich_blocks::test_parse_nested_two_levels | covered |
| TC-blocks-119 | test_rich_editor::test_block_combinations_in_containers (врезка > код-блок) | ДОБАВЛЕНО |
| TC-blocks-120 | test_rich_editor::test_block_combinations_in_containers (callout>таблица, колонка>спойлер с раскрытием, врезка>callout) | ДОБАВЛЕНО |

### Дивергенция D-1 (TC-blocks-106 шаг 2 — эскалация ПМ/reviewer)

Approved шаг 2: «Пустая колонка: 2 колонки, вторая без содержимого — пустая
колонка сохраняет позицию (правая колонка существует, пустая)» (на просмотре).
Фактическая реализация: строгий валидатор диалекта (design §1) отвергает
«колонку без содержимого» (`RichSyntaxError`, тест test_validate_empty_column_raises,
TC-richb-120) → при сохранении срабатывает толерантный fallback A-2 (200, диалект
не разбирается, `<<<` экранируется, контент — plain text; автоматизировано в
test_wiki_api::test_structural_error_new_content_fallback_no_422). Толерантный
ПАРСЕР пустую колонку сохраняет (assert в test_columns_count_boundaries), но до
просмотра она не доходит. Ни 422, ни потери контента нет; расхождение — в
ожидании «колонка существует на просмотре». Требуется решение: правка шага кейса
(«пустая колонка = структурная ошибка → fallback-текст, ОР 200/не-422») либо
доработка реализации. Автотесты зафиксировали фактическое поведение по design §1.

## Матрица compat (9)

| Approved TC | Автотест(ы) | Статус |
|---|---|---|
| TC-compat-201 | test_render_compat::test_render_matches_pre_wave_reference (TC-richc-101, эталон до внедрения) + test_legacy_render_path_unchanged_m4 (TC-richc-102, M-4) | covered |
| TC-compat-202 | test_render_compat::test_render_matches_pre_wave_reference (фиксированный набор rich_compat fixtures, NFR-36) | covered |
| TC-compat-203 | полный регресс-прогон tests/ без правок существующих сьютов (счетчики в §Прогон); сматчено с базой REPORT-4.1 (274 passed) | covered (регресс) |
| TC-compat-204 | test_render_compat::test_re_save_pathological_page_no_422[case4_lookalike_colons] (TC-richc-105) | covered |
| TC-compat-205 | test_render_compat::test_re_save_pathological_page_no_422[case6_lookalike_fence] | covered |
| TC-compat-206 | test_render_compat::test_re_save_pathological_page_no_422[case5_lookalike_gfm] | covered |
| TC-compat-207 | test_wiki_api::test_structural_error_new_content_fallback_no_422 (незакрытый спойлер / unknown callout / лишний `:::` / незакрытый columns / пустая колонка — POST+PUT без 422) | ДОБАВЛЕНО |
| TC-compat-208 | test_render_compat::test_mixed_content_legacy_part_rendered_as_before (TC-richc-104) + test_re_save_valid_rich_page_200 (TC-richc-106) + test_sanitize_rich::test_mixed_content_legacy_segment_passthrough (TC-richs-122) + test_sanitize_rich::test_sanitize_is_idempotent (TC-richs-119, re-save идемпотентен); версии/дифф — существующий сьют wiki (test_wiki_api, регресс п. TC-compat-203) | covered |
| TC-compat-209 | test_sanitize_rich::test_m4_invariant_legacy_passthrough (TC-richs-121, юнит) + test_render_compat::test_legacy_render_path_unchanged_m4 + test_re_save_pathological_page_no_422 (сквозной, content identical) | covered |

## Матрица security (16)

| Approved TC | Автотест(ы) | Статус |
|---|---|---|
| TC-sec-301 | test_sanitize_rich::test_script_in_callout_neutralized (TC-richs-101) + test_rich_editor::test_renderer_xss_vectors_no_executable_elements (TC-rich-103) | covered |
| TC-sec-302 | sanitize-сьют (нейтрализация НА ЗАПИСИ: test_sanitize_rich, TC-richs-101…120) + test_rich_editor::test_renderer_xss_vectors_no_executable_elements (структурная безопасность рендера, createElement/textContent) | covered |
| TC-sec-303 | test_script_in_callout_neutralized (TC-richs-101) | covered |
| TC-sec-304 | test_sanitize_rich::test_script_sweep_across_block_types (ячейка/колонка/врезка/спойлер-контент/спойлер-заголовок/подпись изображения) | ДОБАВЛЕНО |
| TC-sec-305 | test_iframe_in_table_neutralized (TC-richs-102) | covered |
| TC-sec-306 | test_sanitize_rich::test_iframe_sweep_across_block_types (callout/врезка/колонка/спойлер/подпись) | ДОБАВЛЕНО |
| TC-sec-307 | test_sanitize_rich::test_object_embed_sweep_across_block_types (врезка + object/embed × callout/колонка/таблица/спойлер(заголовок+контент)/подпись + код-блок литерально) | ДОБАВЛЕНО (спец-кейс задачи: ранее был только TC-richs-103 object-в-врезке) |
| TC-sec-308 | test_onerror_in_table_cell_neutralized (TC-richs-104) | covered |
| TC-sec-309 | test_onclick_in_spoiler_title_neutralized + test_onclick_in_callout_text_neutralized (TC-richs-105/106) + test_sanitize_rich::test_event_handler_sweep_across_block_types (onmouseover/onfocus/onclick/onload/onerror × типы) | covered + ДОБАВЛЕНО (sweep) |
| TC-sec-310 | test_javascript_link_in_callout_neutralized (TC-richs-107) | covered |
| TC-sec-311 | test_javascript_link_in_table_cell_neutralized (TC-richs-108) + test_javascript_image_src_neutralized + test_javascript_image_inline_in_callout_neutralized (TC-richs-109/110, src) + test_data_url_in_image_neutralized (TC-richs-111) + test_sanitize_rich::test_javascript_url_sweep_spoiler_case_and_data_links (спойлер-контент, JAVASCRIPT:/JavaScript: регистр, data:text/html-ссылка) | covered + ДОБАВЛЕНО (спец-кейс задачи: javascript:-URL в спойлере/регистре/data-ссылке — ранее не покрыты) |
| TC-sec-312 | test_sanitize_rich::test_dangerous_attributes_sweep_across_block_types (style-with-javascript / formaction / srcset / form action / meta refresh × callout/таблица/врезка/колонка/спойлер + позитив-контроль whitelist width) | ДОБАВЛЕНО |
| TC-sec-313 | test_script_in_table_inside_column_neutralized (TC-richs-113) + test_vector_inside_nested_callout_in_column (TC-richs-114) | covered |
| TC-sec-314 | test_script_in_code_block_is_literal_text (TC-richs-115) | covered |
| TC-sec-315 | test_sanitize_rich::test_sanitizer_bypass_classes_neutralized (ScRiPt / scr<script>ipt мутация / незакрытый / caps-атрибуты / повтор в ячейке; идемпотентность) + test_sanitizer_encoded_and_control_char_urls_inert (&#106;avascript:, таб-в-схеме — инертный текст, блок цел; DOM-граница — структурный рендер TC-rich-103) | ДОБАВЛЕНО |
| TC-sec-316 | tests/api/test_sanitize.py (37 тестов) в полном прогоне БЕЗ правок; sanitize.py не изменен (git diff пуст) | covered (регресс) |

## Матрица perf (2)

| Approved TC | Автотест(ы) | Статус |
|---|---|---|
| TC-perf-401 | tests/web/test_rich_perf_50_blocks.py::test_page_with_50_rich_blocks_opens_under_2s (TC-rich-perf-001; замер + отчет REPORT-perf.md) | covered |
| TC-perf-402 | точка «50 блоков» перекрывается TC-rich-perf-001; границы 49/51 и повторные круги (холодный/прогретый) — НФТ-процедура на стенде с генератором страниц, порог ОВ-4 | partial (Should): автоматизация границы 49/51 дала бы ×3 время E2E-перф-сьюта без нового покрытия требования (тот же замер, другие N); шаги в кейсе исполняются после реализации, при невыполнении — эскалация ПМ |

## Прогон (2026-10-16, финальные числа)

- **Целевой rich-сьют** (`tests/web/test_rich_editor.py`,
  `tests/api/test_rich_blocks.py`, `tests/api/test_sanitize_rich.py`,
  `tests/api/test_render_compat.py`, `tests/web/test_rich_perf_50_blocks.py`,
  `tests/api/test_wiki_api.py`, `tests/api/test_sanitize.py`):
  **230 passed, 0 failed** (43.7 с; стенд :18443).
- **Полный регресс** (`python -m pytest tests/ -q`, search/images через nginx;
  `test_search.py`/`test_search_r4.py` исключены — известный фон после отрезки
  search-маршрутов от монолита f0fe4ec, прецедент REPORT-4.1-api.md §6):
  **687 passed, 41 failed, 12 skipped, 2 xfailed** (12:47).
  Фон 41 failed НЕ касается rich-editor (проверено прогоном на чистом HEAD —
  идентичен): 28 × tests/test_flowctl.py (KeyError 'verdict' — инструментарий
  flowctl, вне продукта), 5 × qa21_gallery_* (известный фон), 8 × одиночные
  web/api-кейсы (test_archive 1, test_tasks 1, test_gaps_r4 1, test_bug014 1,
  test_navigation_search_ui 1, test_p12_ui_polish_r8 1, test_r3_profile_ui 2).
  Все rich-сьюты — 0 failed; TC-perf-401 PASS 0.18–0.20 с (порог 2 с, строки
  13:53/13:58 в REPORT-perf.md); существующий sanitize-сьют (TC-sec-316) —
  37 passed без правок.
- **Стенд** (прецедент REPORT-4.1-api.md §1, процессы вместо docker):
  app :8093 (`DB_PATH=/tmp/qa33_app.db`, `AVATARS_DIR=/tmp/qa33/avatars`),
  search :8378, images :8379 (`EKOTOV_WIKI_IMAGES_DIR=/tmp/qa33/images_vol`),
  nginx :18443 (конфиг /tmp/qa33/nginx-stand.conf: search/images-семейства с
  X-Service, static/avatars/images-alias, body 64m); БД — полная схема
  (app.db → seed owner/wife → migrate_r4 → migrate_gallery → migrate_wiki).
  Env прогона: `EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443`,
  `EKOTOV_WIKI_DB_PATH=/tmp/qa33_app.db`, `EKOTOV_WIKI_AVATARS_DIR`,
  `EKOTOV_WIKI_IMAGES_DIR`; интерпретатор `/home/openclaw/venvs/wiki/bin/python`.
- **TC-perf-402**: не автоматизирован (см. матрицу, partial) — шаги кейса
  исполняются на стенде после реализации.
