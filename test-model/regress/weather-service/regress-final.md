# Regress weather-service — regress-final.md

- change: weather-service
- date: 2026-10-19T19:28:02+00:00
- commit: 784e4f01c08c9c00e59fe7bf4ecc06e278edff9c
- worktree: /home/openclaw/ekotov-wiki-worktrees/wfinal
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 758.0s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 36
- changed files: 36
  - backend/app/pages.py
  - contracts/openapi.json
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
  - test-model/regress/weather-service/regress-final.md
  - test-model/reports/weather-service/qa-report-1.md
  - tests/web/pages/auth.py
  - tests/web/test_navigation_search_ui.py
  - tests/web/test_qa21_gallery_ui.py
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/wfinal/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

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
610 passed, 12 skipped, 2 xfailed, 76 warnings in 756.84s (0:12:36)
```
