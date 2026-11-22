# Regress redesign-ui-a — regress-final.md

- change: redesign-ui-a
- date: 2026-11-22T03:04:42+00:00
- commit: a9d279ef1b531eec8d2a6479c2cc78070072d358
- worktree: /home/openclaw/ekotov-wiki
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 1248.4s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 254
- changed files: 254
  - PLAN-REDESIGN-UI-A.md
  - backend/app/pages.py
  - design-context/GUIDE.md
  - design-context/assets/fonts/ejrsqgyozzy2vcfuvant66qcvyvhpa-fe24eb27.woff2
  - design-context/assets/fonts/ejrsqgyozzy2vcfuvant66qfvyvhpa-bba3db27.woff2
  - design-context/assets/fonts/ejrsqgyozzy2vcfuvant66qsvys-0480db00.woff2
  - design-context/assets/fonts/ejrsqgyozzy2vcfuvant66qwvyvhpa-845fc18b.woff2
  - design-context/assets/fonts/ejrvqgyozzy2vcfuvafbzr-tdg-19d702fe.woff2
  - design-context/assets/fonts/ejrvqgyozzy2vcfuvafszr-tdg-2d73e1c0.woff2
  - design-context/assets/fonts/ejrvqgyozzy2vcfuvafwzr8-12e1e0d3.woff2
  - design-context/assets/fonts/ejrvqgyozzy2vcfuvafyzr-tdg-d198c382.woff2
  - design-context/assets/fonts/q5ucsoe9lv5t7meb31ecex18hlxr-e3bbd782.woff2
  - design-context/assets/fonts/q5ucsoe9lv5t7meb31ecex58hlxr-6a3bedff.woff2
  - design-context/assets/fonts/q5ucsoe9lv5t7meb31ecexd8hlxr-720bcf67.woff2
  - design-context/assets/fonts/q5ucsoe9lv5t7meb31ecexn8ha-6e2de38e.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-06ad3600.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-326a88b4.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-4f27206c.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-9d8db2e8.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-bcedb9e2.woff2
  - design-context/assets/fonts/tdbv2o-fleeny0fzhsfku5wu4zr3e-bx0pnt8rd8-feae5721.woff2
  - design-context/assets/icons/icon-14iobj.svg
  - design-context/assets/icons/icon-1pzp4oi.svg
  - design-context/assets/icons/icon-u7ty99.svg
  - "design-context/assets/icons/\320\277\320\265\321\200\320\265\320\272\320\273\321\216\321\207\320\270\321\202\321\214-\321\202\320\265\320\274\321\203-1q6mmt3.svg"
  - design-context/assets/tokens.css
  - design-context/compositions/board.html.md
  - design-context/compositions/kit.html.md
  - design-context/compositions/task.html.md
  - design-context/foundations.md
  - design-context/parts/badges.md
  - design-context/parts/buttons.md
  - design-context/parts/cards.md
  - design-context/parts/components.md
  - design-context/parts/inputs.md
  - design-context/parts/links.md
  - design-context/plan.json
  - design-context/reference/README.md
  - design-context/reference/_catalog.html
  - design-context/reference/_css/styles.css
  - design-context/reference/_media/ejrsqgyozzy2vcfuvant66qcvyvhpa-fe24eb27.woff2
  - design-context/reference/_media/ejrsqgyozzy2vcfuvant66qfvyvhpa-bba3db27.woff2
  - design-context/reference/_media/ejrsqgyozzy2vcfuvant66qsvys-0480db00.woff2
  - design-context/reference/_media/ejrsqgyozzy2vcfuvant66qwvyvhpa-845fc18b.woff2
  - design-context/reference/_media/ejrvqgyozzy2vcfuvafbzr-tdg-19d702fe.woff2
  - design-context/reference/_media/ejrvqgyozzy2vcfuvafszr-tdg-2d73e1c0.woff2
  - design-context/reference/_media/ejrvqgyozzy2vcfuvafwzr8-12e1e0d3.woff2
  - design-context/reference/_media/ejrvqgyozzy2vcfuvafyzr-tdg-d198c382.woff2
  - design-context/reference/_media/q5ucsoe9lv5t7meb31ecex18hlxr-e3bbd782.woff2
  - design-context/reference/_media/q5ucsoe9lv5t7meb31ecex58hlxr-6a3bedff.woff2
  - … и еще 204
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
846 passed, 14 skipped, 2 xfailed, 123 warnings in 1247.31s (0:20:47)
```

## История итераций (разбор FAIL итераций 1–4, закрыто фикс-коммитами до финального прогона)

Каждая итерация — полный сериальный прогон tests/ (tests/api+tests/web одним
вызовом, канонический контур qa_stand_up.sh на дефолтных портах, env по
tests/README §«чистая БД на сессию», reset стенда перед итерацией 5).

### Итерация 1 — FAIL: Interrupted: 1 error during collection (2.8s)

- `tests/web/test_coverage_weather.py:56` — `ImportError: cannot import name
  'provider' from 'app'`: tests/api импортируют монолит backend/app как пакет
  `app` на этапе коллекции, файл (coverage-backfill-1, 10-26 — ПОСЛЕ
  последнего regress-full 10-24, прецедентная дыра) импортирует погодный
  пакет `app` in-process. Фикс 3f3df4e: выселение backend `app` из
  sys.modules на окно импорта погодного пакета.
- Все остальные тесты не стартовали (collection-ошибка) — тестовая база
  не удостоверена.

### Итерация 2 — FAIL: 2 failed, 803 passed, 41 errors (1241s)

- 41 setup-error в tests/api (`import error in app.config`): фикс итерации 1
  выселял backend `app` НА ВЕСЬ хвост сессии — ленивые runtime-импорты
  API-фикстур получали погодный пакет. Фикс 61e60a5 (п.1): выселение только
  на окно импорта, связывание объектов (weather_asgi_app/weather_routes/
  provider_mod), восстановление монолита; monkeypatch-строки
  "app.provider.fetch" → setattr по объекту.
- FAILED `test_games_nav::test_games_sidebar_munchkin_after_games`:
  `base_url` (pytest-base-url) = None без --base-url → «invalid URL» —
  детерминированный дефект теста, вне дельты (апстрим «Манчкин»).
  Фикс 61e60a5 (п.3): web_base_url, паритет соседнего теста.
- FAILED `test_qa21_gallery_design::test_tc_gal_122_live`: accent_var
  '#b7842e' (light-блок) ≠ '#d6a85c' — след дельты ADDED (тумблер темы):
  fresh-контекст headless = prefers-color-scheme: light. Фикс 61e60a5
  (п.2): color_scheme="dark" в контексте (класс фикс-а `_redesign_a_theme`).
- 803 passed включает все средовые :18443-кейсы QA-отчета (p14_22, p14_41,
  p12_gallery_rename, TC-GAL-119, games TC-games-web-001) — на каноническом
  контуре green, классификация QA §2.2 подтверждена.

### Итерация 3 — FAIL: 4 failed, 801 passed, 41 errors (1248s)

- 41 errors те же (до фикса п.1), плюс FAILED 2×`test_p15_wiki_tree::
  test_wiki_empty_state_*` — недетерминизм от загрязнения БД:
  test_rich_tools.py создает страницы UI-save'ом (editor.save_button →
  /wiki/<id>) в обход wiki_api.register — хвосты выживают teardown сессии
  и ломают wiki-empty-state СЛЕДУЮЩЕГО полного прогона на той же БД.
  Фикс 61e60a5 (п.4): session-autouse cleanup (снапшот id → удаление
  созданных файлом страниц, листья раньше родителей). A/B-доказательство:
  итерация 2 (свежая БД) — empty-state green; итерация 3 (БД после
  итерации 2) — red; на свежей БД итерации 5 — green.

### Итерация 4 — FAIL: 0 failed, 820 passed, 26 errors (1190s)

- 26 errors = весь test_rich_tools.py: cleanup-фикстура на голом
  requests.Session — Secure-cookie не отправляется по http, GET после
  login-200 дает 401 (dict вместо списка → TypeError). Фикс a9d279e:
  LocalhostSession (паритет web_owner_session) + shape
  `/api/wiki/pages` = {"pages": [...]} (TC-wiki-007). Локальная
  верификация: 2 rich_tools passed, pages после прогона = 0.

### Итерация 5 (финальная) — PASS

846 passed / 0 failed / 0 errors / 14 skipped (плановые) / 2 xfailed,
свежая БД (reset стенда). Средовые :18443-отклонения QA-отчета (25 шт,
§2.2) на каноническом контуре не воспроизвелись — ни одного FAIL.
Продуктовых багов дельта не дала: все фиксы 3f3df4e/61e60a5/a9d279e —
тест-изоляция, прод-код (frontend/backend) после коммита QA (ae9745b)
не менялся. Коммит артефакта — последний ветки; после него изменений
диффа нет.
