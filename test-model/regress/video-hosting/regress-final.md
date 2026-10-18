# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T05:45:11+00:00
- commit: 6568ca8d92731f5c95d952b1a4e8a9cb201ee653
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh3
- verdict: FAIL
- diff source: git diff main...HEAD
- changed files: 110
  - PLAN-video-hosting.md
  - architecture/map.md
  - backend/app/migrate_video.py
  - backend/app/pages.py
  - code-reviews/video-hosting/dev-report-A-escalations.md
  - code-reviews/video-hosting/dev-report-B.md
  - code-reviews/video-hosting/dev-report-C.md
  - code-reviews/video-hosting/dev-report-D-wave2.md
  - code-reviews/video-hosting/review-001.md
  - code-reviews/video-hosting/review-002.md
  - code-reviews/video-hosting/review-mapping.json
  - conftest.py
  - contracts/openapi.json
  - deploy/compose.test.yaml
  - deploy/compose.yaml
  - design/video-hosting/video-list.html
  - design/video-hosting/video-upload.html
  - design/video-hosting/video-view.html
  - frontend/static/js/video.js
  - frontend/templates/base.html
  - frontend/templates/video.html
  - openspec/changes/video-hosting/design.md
  - openspec/changes/video-hosting/proposal.md
  - openspec/changes/video-hosting/requirements.md
  - openspec/changes/video-hosting/review-architecture.md
  - openspec/changes/video-hosting/sdd.md
  - openspec/changes/video-hosting/specs/video-service/spec.md
  - openspec/changes/video-hosting/tasks.md
  - scripts/flowctl.py
  - scripts/pr_validate.py
  - scripts/session_check.py
  - services/frontend/Dockerfile
  - services/frontend/nginx/ekotov-wiki.conf
  - services/frontend/nginx/videos-headers.inc
  - services/frontend/nginx/videos-proxy.inc
  - services/video/Dockerfile
  - services/video/app/__init__.py
  - services/video/app/converter.py
  - services/video/app/db.py
  - services/video/app/main.py
  - services/video/app/middleware.py
  - services/video/app/social.py
  - services/video/app/storage.py
  - services/video/app/videos.py
  - services/video/install_ffmpeg.py
  - services/video/tests/__init__.py
  - services/video/tests/conftest.py
  - services/video/tests/test_converter.py
  - services/video/tests/test_list_search_order.py
  - services/video/tests/test_nfr_nonblocking.py
  - … и еще 60
- suites: tests
- pytest exit code: 1

## Хвост лога (до 50 строк)

```
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh3/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh3/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/api/test_archive.py::test_msk_midnight_boundary_done_2358_archives_next_day
FAILED tests/api/test_gaps_r4.py::test_profile_r4_101_role_desync_read_and_heal
FAILED tests/web/test_p12_ui_polish_r8.py::test_combobox_three_tags_and_one_by_one_removal[chromium]
FAILED tests/web/test_qa21_gallery_ui.py::test_tc_gal_115_grid_and_filters_owner_vs_pe[chromium]
FAILED tests/web/test_qa21_gallery_ui.py::test_tc_gal_116_lightbox_nav_reactions_comment_download[chromium]
FAILED tests/web/test_r3_profile_ui.py::test_profile_badge_and_login_on_all_pages[chromium]
FAILED tests/web/test_r3_profile_ui.py::test_profile_after_logout_and_sections_clickable[chromium]
FAILED tests/api/test_tasks.py::test_rename_task - ImportError: cannot import...
FAILED tests/test_flowctl.py::TestPrepareDryRun::test_dry_run_no_side_effects
FAILED tests/test_flowctl.py::TestPrepareDryRun::test_dry_run_denied_action_shows_reasons
FAILED tests/test_flowctl.py::TestPrepareRun::test_prepare_then_run_manual_adapter
FAILED tests/test_flowctl.py::TestPrepareRun::test_run_idempotent_no_second_session
FAILED tests/test_flowctl.py::TestPrepareRun::test_run_stale_snapshot_after_new_commit
FAILED tests/test_flowctl.py::TestPrepareRun::test_prepare_idempotent_same_payload
FAILED tests/test_flowctl.py::TestPrepareRun::test_prepare_duplicate_payload_rejected
FAILED tests/test_flowctl.py::TestPrepareRun::test_prepare_zone_conflict_denied
FAILED tests/test_flowctl.py::TestFinish::test_finish_accepted_in_zone_gates_pass
FAILED tests/test_flowctl.py::TestFinish::test_finish_returned_on_out_of_zone
FAILED tests/test_flowctl.py::TestFinish::test_finish_returned_on_gate_fail
FAILED tests/test_flowctl.py::TestFinish::test_finish_blocked_on_gate_error
FAILED tests/test_flowctl.py::TestFinish::test_finish_pm_resume_after_gate_error
FAILED tests/test_flowctl.py::TestFinish::test_finish_pm_resume_rejected_on_substantive_defects
FAILED tests/test_flowctl.py::TestFinish::test_finish_requires_report - KeyEr...
FAILED tests/test_flowctl.py::TestFinish::test_finish_blocked_before_run_no_promotion
FAILED tests/test_flowctl.py::TestFinish::test_finish_idempotent_after_verdict
FAILED tests/test_flowctl.py::TestRecovery::test_crash_after_reservation_reconcile_no_redelegation
FAILED tests/test_flowctl.py::TestRecovery::test_reconcile_stale_marks_registry
FAILED tests/test_flowctl.py::TestRecovery::test_worktree_survives_crash - As...
FAILED tests/test_flowctl.py::TestStatusAudit::test_status_shows_runs_and_sessions
FAILED tests/test_flowctl.py::TestStatusAudit::test_audit_events_no_secrets
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_gates_subset_of_required_is_rejected_with_list
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_gates_only_adds_to_required_set
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_finish_without_additions_runs_policy_gates
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_diagnostic_never_gives_accepted
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_diagnostic_incompatible_with_gates
FAILED tests/test_flowctl.py::TestFinishRequiredGatesPolicy::test_unknown_gate_rejected
ERROR tests/web/test_r5_textarea_polish_ui.py::test_textarea_resets_after_form_clear[chromium]
36 failed, 558 passed, 11 skipped, 2 xfailed, 72 warnings, 1 error in 815.55s (0:13:35)
```

## Разбор хвоста regress_runner (36 failed + 1 error)

Условия прогона: worktree regress-final-vh3 @6568ca8, канонический контур
nginx:18443 → app:8080 + search:8378 + images:8379 + video:8380 (полный
прод-паритет services/frontend/nginx/ekotov-wiki.conf: include-семейства
search/images/videos с X-Service и лимитами 12m/520m, /videos/ c authcheck,
netdata-заглушка с basic-auth; отклонения стенда — только TLS→http и
server-лимит 2m→64m ради avatar-границ, прецеденты REPORT-regress-21 §2-3,
qa41-fix, предыдущий regress-final). БД на сессию: свежая схема →
migrate_wiki/gallery/video/r4 → seed owner/wife (bcrypt) → категории
«Дом/Работа/Личное». env: EKOTOV_WIKI_BASE_URL/DB_PATH/AVATARS_DIR/IMAGES_DIR/
IMAGES_PORT/VIDEOS_DIR. Интерпретатор venv wiki (3.11, pytest 9.1).

Первый механический прогон этого runner (тот же commit, 05:03 UTC, 6568ca8)
дал 39 failed + 289 ERROR — 100% tests/api упали на fixed-уровне «Приложение
http://127.0.0.1:8080 не готово» (стенд не поднят: flowctl regress стенды не
поднимает), т.е. окруженческий FAIL, не дифф. После подъема канонического
контура — прогон выше; все 9 api-фейлов того промежуточного прогона (упрощенный
nginx-конф без include-семейств) — green на паритетном (26 passed, 2 skipped
эталонных), подтверждено: дефект стенда, не дифф.

Классификация 36 failed + 1 error (вне диффа продуктовых регрессий НЕТ):

1. **28 × tests/test_flowctl.py — pre-existing дрейф, НЕ дифф.** Контрольный
   прогон на чистом main (ec6c253, worktree /tmp/vh3-main-check, тот же venv):
   28 failed, 11 passed — состав совпадает ПОИМИТЕННО (diff списков пуст:
   /tmp/vh3-flowctl-main.txt vs /tmp/vh3-flowctl-branch.txt). Учитывая, что
   scripts/flowctl.py в диффе (зеркало) — сведение проведено заново, счетчик
   и состав идентичны чистому main.
2. **3 × tests/api (test_tasks::test_rename_task, test_archive::test_msk_
   midnight_boundary, test_gaps_r4::test_profile_r4_101_role_desync) —
   латентный дефект тест-механики комбинированной коллекции, НЕ дифф.**
   Runtime-импорт `from conftest import db_update/db_select_one/...` (голый
   `conftest`) в api-тестах; при полной коллекции tests/ sys.modules['conftest']
   затирается tests/web/conftest.py (импорт-prepend без пакетов) → ImportError.
   Изолированно 3/3 green; tests/api целым контуром — green (297 passed);
   tests/web+троица одним процессом — green. Воспроизводится детерминированно
   полной коллекцией даже с -k (605 deselected, 3 failed, 3.1s) — механика
   импорта, не состояние БД. На чистом main комбинированный прогон не собирался
   вовсе (pytest 8 запрещал pytest_plugins в tests/web/conftest — снято диффом
   ветки), т.е. краснота вскрыта починкой коллекции, а не создана ею. Чинить
   тест-механикой импорта (зона tests/ — вне зоны regress_runner): PM.
3. **tests/web/test_p12_ui_polish_r8::test_combobox_three_tags — pre-existing**
   (детерминированный 2/2; идентичен предыдущему артефакту: красный на чистом
   main; файл вне диффа).
4. **2 × tests/web/test_r3_profile_ui (test_profile_badge_and_login_on_all_
   pages, test_profile_after_logout_and_sections_clickable) — pre-existing
   тест-долг синка, НЕ дифф.** Strict-матчинг `get_by_role("heading",
   name="Wiki")` ловит ДВА заголовка на пустой wiki-БД (h1 «Wiki» + empty-state
   h2 «В Wiki пока нет страниц») — тот же класс, что снятый синком 6568ca8
   TC-UI-016 (exact=True), но test_r3_profile_ui синком не накрыт. Источник
   (empty-state в tree.js) уже на чистом main; tree.js и test_r3_profile_ui
   в диффе отсутствуют (git diff main...HEAD: 0 файлов).
5. **2 × tests/web/test_qa21_gallery_ui (tc_gal_115, tc_gal_116) — зеленые
   изолированно 2/2** (свежая БД, оба прогона идентичны); в полном порядке
   галерею засоряет хвост test_p15_wiki_editor (заливает картинку редактора —
   pre-existing долг очистки, p15 вне диффа). Файл в диффе (синк 6568ca8),
   но сами кейсы и их локаторы после синка корректны.
6. **1 ERROR tests/web/test_r5_textarea_polish_ui::test_textarea_resets —
   известный класс флейка playwright** (in-flight /static-запросы в teardown
   Browser.close; лечится networkidle-фиксом теста, вне диффа). В изолированных
   прогонах не воспроизвелся.

Дифф-зона зеленая: видео-сьюты (test_video_ui, test_video_convert_ui,
test_video_social_ui, test_video_wiki_isolation_ui), синк-кейсы
(test_navigation_search_ui, TC-GAL-119, TC-UI-016), test_rich_editor,
test_rich_blocks, test_p12_nav_icons — все в числе 558 passed.

## Итог

- Механический вердикт FAIL определяется хвостом 36+1, из них 0 дифф-регрессий:
  28 pre-existing дрейф flowctl-тестов (идентичен чистому main покомпонентно),
  3 латентная коллизия голого импорта conftest (вскрыта починкой коллекции),
  3 pre-existing тест-долг web (combobox + 2 × strict-heading профиля),
  2 порядко-зависимых галерейных (green 2/2 изолированно),
  1 известный флейк teardown.
- Продуктовых багов диффа video-hosting НЕ выявлено; видео-фича на контуре
  работает (сайдбар 5 пунктов, /api/videos через nginx, конвертация,
  социальные механики, изоляция wiki — сьюты green).
- Вне зоны regress_runner (PM): (а) тест-механика голого `from conftest
  import` в tests/api (перевести на пакетный импорт/общий хелпер);
  (б) досинхронизировать test_r3_profile_ui (exact=True по классу TC-UI-016);
  (в) 28 дрейфовых test_flowctl — решение о фиксе/изоляции на чистом main.

