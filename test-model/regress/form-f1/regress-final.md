# Regress form-f1 — regress-final.md

- change: form-f1
- date: 2026-11-23T15:42:29+00:00
- commit: 6bff302f31926977b0be9a1b1df5bf921f522c2d
- worktree: /home/openclaw/ekotov-wiki
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 1266.8s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 31
- changed files: 31
  - PLAN-FORM-F1.md
  - backend/app/pages.py
  - design-forge/extra/form-v1/base.css
  - design-forge/extra/form-v1/create.html
  - design-forge/extra/form-v1/edit.html
  - design-forge/extra/form-v1/tokens.css
  - docs/review/review-form-f1-001.md
  - frontend/static/css/board.css
  - frontend/static/js/board/task-form.js
  - frontend/templates/board.html
  - openspec/changes/form-f1/design.md
  - openspec/changes/form-f1/proposal.md
  - openspec/changes/form-f1/requirements.md
  - openspec/changes/form-f1/specs/tasks/spec.md
  - openspec/changes/form-f1/tasks.md
  - test-model/approved/form-f1/TC-form-001.md
  - test-model/approved/form-f1/TC-form-002.md
  - test-model/approved/form-f1/TC-form-003.md
  - test-model/approved/form-f1/TC-form-004.md
  - test-model/approved/form-f1/TC-form-005.md
  - test-model/impact/form-f1.md
  - test-model/reviews/form-f1/review-001.md
  - tests/web/pages/task_form.py
  - tests/web/test_coverage_rich_tools_security.py
  - tests/web/test_p12_ui_polish_r8.py
  - tests/web/test_p14_22_ticket_modal_fullscreen.py
  - tests/web/test_r3_formv3_ui.py
  - tests/web/test_r4_commentfix_ui.py
  - tests/web/test_r6_wave2_ui.py
  - tests/web/test_redesign_console.py
  - tests/web/test_settings_categories_ui.py
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_video_social_ui.py:28
  /home/openclaw/ekotov-wiki/tests/web/test_video_social_ui.py:28: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:28
  /home/openclaw/ekotov-wiki/tests/web/test_video_social_ui.py:28: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_coverage_weather.py::test_tc_weather_005_missing_metric_api_variants
tests/web/test_coverage_weather.py::test_tc_weather_005_missing_metric_api_variants
tests/web/test_coverage_weather.py::test_tc_weather_005_missing_metric_api_variants
tests/web/test_coverage_weather.py::test_tc_weather_006_seven_days_contract
tests/web/test_coverage_weather.py::test_tc_weather_007_today_matches_first_day
tests/web/test_coverage_weather.py::test_tc_weather_015_broken_json_keeps_cache
tests/web/test_coverage_weather.py::test_tc_weather_016_empty_cache_provider_down_is_503
tests/web/test_coverage_weather.py::test_tc_weather_018_exactly_one_retry
tests/web/test_coverage_weather.py::test_tc_weather_025_responsiveness_on_provider_failure
  /home/openclaw/ekotov-wiki/backend/.venv/lib/python3.11/site-packages/starlette/testclient.py:455: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
846 passed, 14 skipped, 2 xfailed, 123 warnings in 1265.61s (0:21:05)
```
