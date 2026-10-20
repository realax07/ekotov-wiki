# Regress p23-fastline — regress-final.md

- change: p23-fastline
- date: 2026-10-20T22:55:21+00:00
- commit: b9718daa4e4a0781509e058cdd05ed0556d5da92
- worktree: /home/openclaw/ekotov-wiki-worktrees/p23-final
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 847.0s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 24
- changed files: 24
  - PRODUCT_BACKLOG.md
  - backend/app/pages.py
  - frontend/static/css/board.css
  - frontend/static/js/board/api.js
  - frontend/static/js/board/cards.js
  - frontend/static/js/board/state.js
  - frontend/static/js/board/task-form.js
  - frontend/templates/board.html
  - openspec/changes/p23-fastline/design.md
  - openspec/changes/p23-fastline/impact.md
  - openspec/changes/p23-fastline/proposal.md
  - openspec/changes/p23-fastline/review-architecture.md
  - openspec/changes/p23-fastline/specs/fastline/spec.md
  - openspec/changes/p23-fastline/specs/p23-fastline/spec.md
  - openspec/changes/p23-fastline/tasks.md
  - test-model/regress/p23-fastline/regress-final.md
  - tests/web/conftest.py
  - tests/web/dnd_helpers.py
  - tests/web/pages/board.py
  - tests/web/test_board_assign_ui.py
  - tests/web/test_board_fastline.py
  - tests/web/test_fastline_ui.py
  - tests/web/test_p12_ui_polish_r8.py
  - tests/web/test_r3_dnd_ui.py
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p23-final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
675 passed, 12 skipped, 2 xfailed, 79 warnings in 845.88s (0:14:05)
```
