# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T14:38:53+00:00
- commit: 43ad3aa258951aa724dc09821485bf46d2ab7fe5
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7
- verdict: FAIL
- diff source: git diff main...HEAD
- changed files: 10
  - code-reviews/video-hosting/review-003.md
  - code-reviews/video-hosting/review-mapping.json
  - frontend/static/js/video.js
  - frontend/templates/video.html
  - openspec/changes/video-hosting/proposal.md
  - openspec/changes/video-hosting/specs/video-service/spec.md
  - openspec/changes/video-hosting/tasks.md
  - services/video/app/videos.py
  - services/video/tests/test_videos_rename.py
  - tests/web/test_video_rename_ui.py
- suites: tests
- pytest exit code: 1

## Разбор regress_runner (прогоны 1–4, финальная классификация)

Механический вердикт FAIL (pytest exit 1) — 2 упавших web-теста, оба ВНЕ
диффа ветки; продуктовых регрессий диффа не вскрыто. История прогонов
(все — worktree 43ad3aa, изолированные, свежий стенд /tmp/vh7-stand):

1. FAIL 9 failed / 290 errors — инфраструктура раннера: стенд не был поднят
   перед прогоном (flowctl стенд не поднимает), session-фикстура base_url
   не дождалась app:8080 → пачечные RuntimeError по всем api-тестам.
2. FAIL 9 failed / 289 errors — тот же почерк (подтверждение инфра-причины,
   не флака диффа).
3. FAIL 26 failed / 30 errors / 571 passed — стенд поднят (reset.sh + nginx),
   но неполный env pytest-процесса: без EKOTOV_WIKI_AVATARS_DIR тесты
   аватаров падают (os.environ[] → TypeError), без EKOTOV_WIKI_IMAGES_DIR
   галерея сверяется с дефолтным /tmp/qa21-gallery/images; упавшие аватарные
   тесты оставили аватары в БД → каскад по профильным тестам (avatar_url
   не None). Урок №6 (неполный env + БД-замусоривание) воспроизведен 1:1.
4. FAIL 2 failed / **595 passed** / 12 skipped / 2 xfailed / 0 errors за
   776s — канонический контур nginx:18443→app:8080+search:8378+images:8379+
   video:8380, свежая БД + seed + миграции wiki/gallery/video/r4, полный env
   (BASE_URL=18443, DB_PATH, AVATARS_DIR, IMAGES_DIR).

Классификация хвоста прогона 4 (обоих тестов код и проверяемый продукт
байт-в-байт идентичны main — дифф ветки не затрагивает search/board/
task-detail; video.js/video.html в их контуре не участвуют):

- tests/web/test_r3_dnd_ui.py::test_dnd_success_after_409_hides_board_error —
  флейк связки: изолированно green 2/2; известный класс гонки
  dnd_helpers/async refreshBoard.
- tests/web/test_bug014_search_task_view.py::test_search_task_view_computed_styles_match_board —
  детерминированно красный в этой среде (4/4, вкл. изолированные): снятие
  computed styles через page.evaluate СРАЗУ после открытия модалки без
  предварительного expect — гонка рендера task-detail.js (класс BUG-016
  «evaluate без автожиданий», прецедент регресса №3 «strict-heading,
  tree.js empty-state уже на main»). Кандидат в багфикс тест-хелпера,
  вне скоупа regress-final.

Вердикт по диффу: ЧИСТО — полный регресс 595 passed / 2 failed (0 из
диффа) / 0 errors; видео-сьюты: services/video/tests 94 passed (вкл.
TC-vid-090…099 переименование, прогон regress-final-vh7 на том же коммите),
tests/web/test_video_rename_ui.py green в составе 595.

## Хвост лога (до 50 строк)

```

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh7/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/web/test_bug014_search_task_view.py::test_search_task_view_computed_styles_match_board
FAILED tests/web/test_r3_dnd_ui.py::test_dnd_success_after_409_hides_board_error
2 failed, 595 passed, 12 skipped, 2 xfailed, 74 warnings in 776.22s (0:12:56)
```
