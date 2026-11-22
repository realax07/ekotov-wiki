# Regress redesign-ui-a — regress-final.md

- change: redesign-ui-a
- date: 2026-11-22T09:00:50+00:00
- commit: 32933b300c4a4041c17a38c88508899ab1d7e4f2
- worktree: /home/openclaw/ekotov-wiki
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 1254.2s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 19
- changed files: 19
  - backend/app/pages.py
  - design-forge/extra/mobile-v1/base.css
  - design-forge/extra/mobile-v1/board.html
  - design-forge/extra/mobile-v1/gallery.html
  - design-forge/extra/mobile-v1/task.html
  - design-forge/extra/mobile-v1/tokens.css
  - design-forge/extra/mobile-v1/video.html
  - design-forge/extra/mobile-v1/wiki.html
  - docs/qa/qa-mobile-v1.md
  - frontend/static/css/app.css
  - frontend/static/css/board.css
  - frontend/static/js/mobile-tabbar.js
  - frontend/templates/base.html
  - frontend/templates/video.html
  - tests/web/dev_smoke_p14_21_board_swipe.py
  - tests/web/test_coverage_p14_mobile.py
  - tests/web/test_p23_fastline_mobile_ui.py
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
  /home/openclaw/venvs/wiki/lib/python3.11/site-packages/starlette/testclient.py:455: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
846 passed, 14 skipped, 2 xfailed, 122 warnings in 1253.11s (0:20:53)
```

## История итераций (перегон на свежий HEAD после мобайл-волны V1)

### Итерация A (HEAD 00e937b) — FAIL: 2 failed, 844 passed, 14 skipped, 2 xfailed (1252s)

- FAILED `tests/unit/test_impact_rules_p20.py::test_p20_cli_clean_head_no_deny`
  и `tests/unit/test_impact_rules_p20_gate.py::test_p20_gate_cli_clean_head_no_deny`
  — гейт IR-03 (pr_validate J58): дифф мобайл-волны (fa7c8e6/00e937b) трогает
  frontend/templates/base.html и статику (app.css/board.css/mobile-tabbar.js —
  НОВЫЙ файл) без касания backend/app/pages.py → J58-DENY на чистом HEAD.
  Классификация: РЕГРЕСС волны (нарушена release-дисциплина static_v), не средовой.
  Фикс 32933b3: бамп static_v → redesign-a-m1 (+ changelog-комментарий в
  pages.py, литерал ассерта TC-redesign-011 синхронизирован). Верификация:
  pr_validate CLI на HEAD без DENY; test_redesign_console (36) + p20 unit
  (16) — 52 passed.
- Средовых :18443-отклонений НЕ было: канонический контур qa_stand_up.sh,
  свежая БД на сессию (reset перед каждым полным прогоном), засорение
  мобайл-QA (p14_41 ×6, QAGAL-маркеры qa21_gallery_ui/p12_rename) снято
  reset'ом — класс «count-ассерты ловят хвосты» из qa-mobile-v1.md §2.2
  не воспроизвелся (0 FAIL в обоих прогонах, включая галерейные сьюты).

### Итерация B (HEAD 32933b3, финальная) — PASS

846 passed / 0 failed / 0 errors / 14 skipped (плановые) / 2 xfailed,
1254s, свежая БД (reset стенда). Продуктовых багов дельта не дала.
