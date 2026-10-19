# Regress weather-service — regress-final.md

- change: weather-service
- date: 2026-10-19T19:02:47+00:00
- commit: 35d4b77a3fb9ef74f10040bbe1e05ba2fa36a69d
- worktree: /home/openclaw/ekotov-wiki-worktrees/wfinal
- verdict: FAIL
- tier: domain (эшелон 1: доменный regress)
- duration: 757.9s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 31
- changed files: 31
  - backend/app/pages.py
  - deploy/RUNBOOK.md
  - deploy/deploy.sh
  - test-model/approved/weather-service/APPROVAL.md
  - test-model/approved/weather-service/README.md
  - test-model/approved/weather-service/TC-weather-001.md
  - test-model/approved/weather-service/TC-weather-002.md
  - test-model/approved/weather-service/TC-weather-003.md
  - test-model/approved/weather-service/TC-weather-004.md
  - test-model/approved/weather-service/TC-weather-005.md
  - test-model/approved/weather-service/TC-weather-006.md
  - test-model/approved/weather-service/TC-weather-007.md
  - test-model/approved/weather-service/TC-weather-008.md
  - test-model/approved/weather-service/TC-weather-009.md
  - test-model/approved/weather-service/TC-weather-010.md
  - test-model/approved/weather-service/TC-weather-011.md
  - test-model/approved/weather-service/TC-weather-012.md
  - test-model/approved/weather-service/TC-weather-013.md
  - test-model/approved/weather-service/TC-weather-014.md
  - test-model/approved/weather-service/TC-weather-015.md
  - test-model/approved/weather-service/TC-weather-016.md
  - test-model/approved/weather-service/TC-weather-017.md
  - test-model/approved/weather-service/TC-weather-018.md
  - test-model/approved/weather-service/TC-weather-019.md
  - test-model/approved/weather-service/TC-weather-020.md
  - test-model/approved/weather-service/TC-weather-021.md
  - test-model/approved/weather-service/TC-weather-022.md
  - test-model/approved/weather-service/TC-weather-023.md
  - test-model/approved/weather-service/TC-weather-024.md
  - test-model/approved/weather-service/TC-weather-025.md
  - test-model/reports/weather-service/qa-report-1.md
- suites: tests
- pytest exit code: 1

## Хвост лога (до 50 строк)

```
tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/api/test_openapi_r11.py::test_openapi_with_session_200_and_matches_contract
FAILED tests/web/test_navigation_search_ui.py::test_sidebar_all_pages_and_wiki_stub[chromium]
FAILED tests/web/test_qa21_gallery_ui.py::test_tc_gal_119_sidebar_gallery_fourth_parity_and_no_tracker_links[chromium]
3 failed, 607 passed, 12 skipped, 2 xfailed, 76 warnings in 756.70s (0:12:36)
```

## Примечание regress_runner (прогон 2, вердикт FAIL — не флейк)

- Прогон 1 (18:34 UTC, stand /tmp/vh9-stand после reset): 28 failed / 582 passed / 12 skipped / 30 errors
  — НЕГАТИВЕН НЕ ГОДЕН: в env отсутствовал EKOTOV_WIKI_AVATARS_DIR (тесты читают именно его,
  сервис — AVATARS_DIR); TypeError os.path.join(None). Стенд пересобран, прогон повторен с полным env.
- Прогон 2 (финальный, выше): 3 failed / 607 passed / 12 skipped / 2 xfailed. Все 3 отказа
  детерминированы (одиночный изолированный перепрогон — воспроизведение 3/3), это НЕ флейки
  и НЕ baseline:
  1. tests/api/test_openapi_r11::test_openapi_with_session_200_and_matches_contract — живой
     /openapi.json содержит лишний путь /weather, contracts/openapi.json не перегенерирован
     (scripts/export_openapi.py) — пропуск ДОСТАВКИ пакета weather-service.
  2. tests/web/test_navigation_search_ui.py::test_sidebar_all_pages_and_wiki_stub — сайдбар
     теперь 6 пунктов (+«Погода»), ассерт ждёт 5 — тест до-weather семантики (класс «тест vs фича»).
  3. tests/web/test_qa21_gallery_ui.py::test_tc_gal_119_... — аналогично, ждёт
     [Доска, Поиск, Wiki, Галерея, Видео], факт [..., Видео, Погода].
- Окружение: nginx:18443 → app:8080 + search:8378 + images:8379 + video:8380 + weather:8381,
  свежая БД + seed owner/wife + миграции wiki/gallery/video/r4, env по tests/README
  (BASE_URL/DB_PATH/AVATARS_DIR/EKOTOV_WIKI_AVATARS_DIR/IMAGES_DIR/VIDEOS_DIR), ffmpeg на PATH.
- Особенность: ветка chore/weather-release в ходе прогона продвинулась 555f6b0 → 35d4b77
  (кейсы weather → approved); тестовое дерево прогона = 555f6b0 + env (разница — только
  test-model/approved/*.md, на поведение тестов не влияет).
