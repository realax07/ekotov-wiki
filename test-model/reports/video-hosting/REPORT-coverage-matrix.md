# REPORT — автоматизация approved-кейсов video-hosting (qa_automation, flow=1)

- **Дата:** 2026-10-18; ветка `pipeline/video-hosting` (HEAD ef0103f + коммиты qa_automation)
- **Кейсы:** `test-model/approved/video-hosting/` TC-vid-001…040 (40/40)
- **Покрытие:** 40/40 (37 — автотесты, 2 — живые прогоны на стенде из этого же цикла, 1 — процессный)
- **Тест-каунт:** services/video/tests — **72 passed** (66 было + 6 новых); tests/web видео-сьют — **11 passed** (10 было + 1 новый)

## Запуски

| Набор | Команда | Результат |
|---|---|---|
| services/video/tests | `python3 -m pytest tests/ -q` (из services/video/) | **72 passed**, ~29 c |
| web видео-сьют | `pytest tests/web/test_video_{ui,convert_ui,social_ui,wiki_isolation_ui}.py -q` | **11 passed**, ~31 c |

NFR-замеры (unit + живой стенд) — ниже; смоук живого стенда: health 200, вход seed, upload → converting → ready, playback/preview 200, delete 200 → список пуст.

## Матрица кейс → тест

| Кейс | Тест(ы) | Статус |
|---|---|---|
| TC-vid-001 | tests/web/test_video_ui.py::test_sidebar_video_item_after_gallery | автотест, green |
| TC-vid-002 | tests/web/test_video_ui.py::test_video_page_redirects_anonymous_to_login | автотест, green |
| TC-vid-003 | tests/web/test_video_wiki_isolation_ui.py::test_wiki_editor_has_no_video_insert (**новый**) | автотест, green |
| TC-vid-004 | живой прогон (деградация docker stop) — см. BUG-video-001 | прогон, условный fail по времени → BUG |
| TC-vid-005 | test_videos_service::test_upload_happy_path; test_storage.py (изоляция путей, том) | автотест, green |
| TC-vid-006 | test_videos_service::test_endpoints_require_session | автотест, green |
| TC-vid-007 | test_videos_service::test_upload_boundary_exact_500mb (**новый**) + test_upload_too_large_422_no_volume_dir + test_upload_precheck_rejects_huge_content_length | автотест, green |
| TC-vid-008 | test_nfr_nonblocking.py::test_nfr37_uploads_during_conversion (**новый**) + живой замер (77–90 мс) | автотест, green |
| TC-vid-009 | test_videos_service::test_file_served_for_ready (+ 401 без сессии — TC-vid-038) | автотест, green |
| TC-vid-010 | test_videos_service::test_file_409_not_ready + web TC-vid-108 (плейсхолдер без `<video>`) | автотест, green |
| TC-vid-011 | test_videos_service::test_delete_removes_volume_and_row + test_delete_parity_both_users | автотест, green |
| TC-vid-012 | test_converter::test_delete_cancel_discards_artifacts + test_videos_service::test_delete_of_unfinished_removes_original | автотест, green |
| TC-vid-013 | test_videos_service::test_file_and_preview_404_missing (+ 401 без сессии) | автотест, green |
| TC-vid-014 | test_converter::test_convert_mkv_to_mp4_happy_path + web test_list_auto_refresh_polling (UI без перезагрузки) | автотест, green |
| TC-vid-015 | test_converter::test_fail_stub_exactly_one_retry_then_error + test_convert_error_keeps_original (реальное видео) | автотест, green |
| TC-vid-016 | test_converter::test_timeout_kills_process_and_retries | автотест, green |
| TC-vid-017 | test_nfr_nonblocking.py::test_nfr37_list_p95_during_conversion (**новый**) + живой p95 | автотест, green |
| TC-vid-018 | test_converter::test_convert_mkv_to_mp4_happy_path (оригинал удален, size = mp4) | автотест, green |
| TC-vid-019 | test_converter::test_convert_error_keeps_original + test_videos_service::test_delete_error_status_video_removes_volume (**новый**) | автотест, green |
| TC-vid-020 | test_converter::test_convert_mkv_to_mp4_happy_path (preview.jpg) + живая проверка (200, image/jpeg) | автотест, green |
| TC-vid-021 | test_converter::test_mp4_source_skips_transcode_preview_only | автотест, green |
| TC-vid-022 | web test_video_convert_ui.py::test_status_badges_by_mockup + test_preview_409_until_frame_exists | автотест, green |
| TC-vid-023 | test_list_search_order::test_search_substring_case_insensitive_cyrillic + test_order_by_name_asc_desc (TC-vid-081/082) | автотест, green |
| TC-vid-024 | test_list_search_order::test_unicode_names_upload_search_sort (**новый**: №/«»/—, emoji, 255 байт) | автотест, green |
| TC-vid-025 | test_social::test_comment_add_list_author | автотест, green |
| TC-vid-026 | test_social::test_comment_empty_and_whitespace_422 (расширен: без поля text) | автотест, green |
| TC-vid-027 | test_social::test_comment_delete_only_own (свой — 200) | автотест, green |
| TC-vid-028 | test_social::test_comment_delete_only_own (чужой — 403, E-3) | автотест, green |
| TC-vid-029 | test_social::test_reaction_two_users_independent (инвариант ≤ 1 голоса) | автотест, green |
| TC-vid-030 | test_social::test_reaction_put_toggle_move (перенос) | автотест, green |
| TC-vid-031 | test_social::test_reaction_put_toggle_move (повторный клик снимает) | автотест, green |
| TC-vid-032 | test_social::test_reaction_race_single_vote (**новый**, 5 гонок) | автотест, green |
| TC-vid-033 | test_social::test_upload_with_valid_category + test_upload_without_category_defaults_none | автотест, green |
| TC-vid-034 | test_social::test_list_filter_by_category (+ web TC-vid-104, UI-тулбар) | автотест, green |
| TC-vid-035 | test_social::test_upload_unknown_category_422 (422 — решение ПМ, review-002/E-4) + test_categories_list_is_gallery_catalog | автотест, green |
| TC-vid-036 | процессный кейс (дизайн-фаза) — автоматизация нецелесообразна; свидетельства утверждения мокапов — review-001/002, design/video-hosting/*.html | process/manual |
| TC-vid-037 | живой прогон: docker inspect/stats (см. NFR-35 ниже) | прогон, PASS |
| TC-vid-038 | test_videos_service::test_endpoints_require_session + живая проверка (/videos/ без сессии → 302 /login; API → 401) | автотест + прогон, green |
| TC-vid-039 | живой замер p95 на стенде (см. NFR-37 ниже) + unit-NFR тесты | прогон, PASS |
| TC-vid-040 | test_social::test_social_endpoints_unauthorized_401 (все D-эндпоинты + categories, состояние не меняется) | автотест, green |

## NFR-35 (TC-vid-037) — здоровье и лимиты контейнера video (стенд wiki-test)

- `docker inspect wiki-test-video-1`: **mem_limit 512 MiB** (536870912), **healthcheck** `python -c … http://127.0.0.1:8380/api/health` (interval 30s, timeout 10s, retries 3, start_period 15s), **LogConfig json-file max-size 10m max-file 3** — по конфигурации compose.test.yaml, все три пункта шага 1 подтверждены.
- В ходе конвертации фикстурного видео (246–402 МБ, 12000–18000 кадров): `docker stats --no-stream` — **236–243 MiB / 512 MiB** (CPU 175–330%), healthcheck — **healthy** на всех срезах.
- Суммарные mem_limit стека wiki-test: video 512m + остальные сервисы по compose.test.yaml (см. `deploy/compose.test.yaml`; host 8 GB, резерв > 2 GB соблюден).
- Существенное: контейнер был пересобран (`docker compose -p wiki-test -f deploy/compose.test.yaml build/up video`) — образ стенда (21:42) отставал от ветки (куски A–D, 22:56–01:20): сервис отвечал `status=ready` сразу, без фоновой конвертации, схема БД без category_id/video_comments/video_reactions (досозданы идемпотентной `app.migrate_video` на томе wiki-test_wiki-test-data). После пересборки поведение соответствует HEAD.

## NFR-37 (TC-vid-017/039) — p95 при фоновой конвертации

Живой стенд, фикстурное видео 402 МБ (1280x720, 18000 кадров), в статусе converting:

| Замер | Значение | Порог |
|---|---|---|
| p95 20× GET /api/videos | **18.4 мс** (max 18.4, mean 9.6; повторный прогон 20.8 мс) | < 500 мс — PASS |
| p95 5× upload 2.3 МБ при конвертации | **90.2 мс** (max 90.2, mean 83.4; каждая < 5 c) | < 500 мс — PASS |
| docker stats в ходе конвертации | 236–243 MiB / 512 MiB | лимит — PASS |
| healthcheck в ходе конвертации | healthy | PASS |

Unit-уровень (services/video/tests/test_nfr_nonblocking.py, ffmpeg-заглушка с контролируемой длительностью): p95 списка и p95 загрузок в пороге, тесты фиксируют значения в stdout.

## Найденное

- **BUG-video-001** (minor): деградация 503 при `docker stop` — при теплом upstream-пуле nginx первые запросы висят ~5.01 c (`proxy_connect_timeout 5s`), кейс требует < 2 c; в холодном состоянии — 503 за <50 мс. test-model/bugs/BUG-video-001-degradation-warm-upstream-5s.md.
- Устаревший образ video:test на стенде (см. NFR-35) — env-дрейф, устранен пересборкой; зафиксировано как фон.
- Наблюдение: после POST фикс took ~60–90 c до старта конвертации при простаивающем воркере (однократно, между прогонами; в основных замерах старт конвертации ≤ 1 c). К воспроизведению не стабилизировался — не файл.

## Фон (вне видео-домена, не чинилось)

- API-набор tests/api по README требует поднятый app на :8080 — в этой среде не поднимался (паритет волн B/C/D: pretестовый фон).
- Web-фрейки вне видео-домена — не воспроизводились и не чинились (вне скоупа задачи).

## Измененные/новые файлы

- services/video/tests/test_nfr_nonblocking.py (**новый**, TC-vid-008/017/039)
- services/video/tests/test_videos_service.py (+2 теста, аннотации TC-vid-005/006/009/010/011/013/019/038)
- services/video/tests/test_social.py (+race-тест TC-vid-032, missing-field в TC-vid-026, аннотации 025/027/028/029/030/031/033/034/035/040)
- services/video/tests/test_list_search_order.py (+unicode-тест TC-vid-024, аннотация 023)
- services/video/tests/test_converter.py (аннотации 012/014/015/016/018/019/020/021)
- tests/web/test_video_wiki_isolation_ui.py (**новый**, TC-vid-003)
- tests/web/test_video_ui.py (аннотации 001/002), tests/web/test_video_convert_ui.py (аннотация 022)
- test-model/bugs/BUG-video-001-degradation-warm-upstream-5s.md (**новый**)
