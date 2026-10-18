# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T03:07:02+00:00
- commit: 2416f7751b5821b41d532c84c56fd65d37f952df
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh
- verdict: FAIL
- diff source: git diff main...HEAD
- changed files: 103
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
  - services/video/tests/test_social.py
  - services/video/tests/test_storage.py
  - services/video/tests/test_videos_service.py
  - test-model/approved/video-hosting/TC-vid-001.md
  - … и еще 53
- suites: tests/api, tests/web, tests
- pytest exit code: 2

## Хвост лога (до 50 строк)

```
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_tooltip_r4.py:38
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_tooltip_r4.py:38: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/api/test_auth.py
ERROR tests/api/test_auth_me.py
ERROR tests/api/test_authme_r3.py
ERROR tests/api/test_profile_r4.py
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!!
71 warnings, 4 errors in 1.31s
```
## Разбор regress_runner (изолированный перепрогон, 2 прогона на каждый упавший)

Механический прогон flowctl прерван на КОЛЛЕКЦИИ (exit 2, до исполнения тестов):
аргумент-список маппинга `tests/api tests/web tests` рождает коллизию модуля
`conftest` — bare-импорты `from conftest import ...` в tests/api/test_auth.py,
test_auth_me.py, test_authme_r3.py, test_profile_r4.py резолвятся в
tests/web/conftest.py. Воспроизводится на интерпретаторах 3.14/pytest 8 и
3.11/pytest 9.1, а также на чистом main в том же окружении — дефект маппинга
J51.2 при первом применении (дубль домена `tests` поверх `tests/api`+`tests/web`),
не регресс диффа. Фактический регресс выполнен эквивалентным одиночным
вызовом `pytest tests -q` (608 тестов) + изолированный перепрогон всех 145
упавших/ошибочных на каноническом контуре (прецедент REPORT-2.1-gallery-qa §1):
nginx :18443 → app :8080 + search :8391 + images :8392.

- Полный прогон (монолит-стенд :8080 без сервисов): 608 collected —
  100 failed, 50 errors, 419 passed, 42 skipped, 2 xfailed (11:08).
- Перепрогон 145 на контуре: 114 ушли в green, 31 остался; разобраны поштучно
  (каждый — 2 прогона, все детерминированы, ФЛАКОВ НЕТ):
  - 28 × tests/test_flowctl.py — pre-existing: идентичный падеж на чистом main
    (28 failed там же, тем же окружением); дрейф scripts/flowctl.py, вне диффа.
  - tests/api: tc_gal_106 (нужен env EKOTOV_WIKI_IMAGES_PORT — канонический
    :8379 занят чужим процессом), suggestions ×3 (загрязнение QAT-* категорий
    в БД стенда от ранних оборванных прогонов) — после устранения PASS.
  - tests/api: gaps_r5/avatar_r4 boundary «ровно 2 МБ» — по дизайну требуют
    direct-app стенд + EKOTOV_WIKI_DB_PATH (через nginx 2m-лимит multipart
    дает 413); в каноническом для них виде — PASS. Наблюдение вне скоупа:
    через nginx прод-паритета граница «ровно 2 МБ» аватара 413 —
    напряжка лимит/спека старше диффа.
  - tests/web: test_tc_gal_119_sidebar_gallery_fourth_parity — ЕДИНСТВЕННЫЙ
    дифф-зависимый падеж: тест фиксирует сайдбар [Доска, Поиск, Wiki, Галерея],
    дифф добавляет «Видео» (сама фича TC-vid-001 работает) — тест устарел,
    требует обновления в пакете (зона test-model, вне зоны regress_runner).
    Детерминирован 2/2.
  - tests/web: test_combobox_three_tags_and_one_by_one_removal — pre-existing
    (воспроизведен на чистом main), детерминирован 2/2.
  - tests/web: test_profile_badge_and_login_on_all_pages — артефакт стенда:
    strict-матчинг заголовка «Wiki» ловит пустой wiki-стенд БД контура
    («В Wiki пока нет страниц»); на каноническом self-стенде ветки PASS,
    на main PASS. Регресса диффа нет; латентный флак теста (нет exact=True).

Итог разбора: продуктовых багов диффа video-hosting не выявлено;
1 устаревший тест (TC-GAL-119) требует синхронизации с фичей;
ворота merge сейчас блокирует дефект маппинга flowctl regress (дубль
домена `tests`) — чинить в ai-factory/scripts/flowctl.py (дедуп доменов,
покрываемых `tests`) либо в test-layout bare-импортов, после чего перегнать
regress --final.
