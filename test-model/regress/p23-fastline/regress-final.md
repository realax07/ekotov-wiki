# Regress p23-fastline — regress-final.md

- change: p23-fastline
- run: p23-fastline-1 финал (полный сериал на head 9559987; от PASS-прогона на 7a96698 продукт-дельты нет — только test-model/impact H5 + регресс-мета; цифры идентичны: 675 passed / 12 skipped / 2 xfailed)
- date: 2026-10-21T00:56:18+00:00
- commit: 9559987347e3a8d3b88af8a0112757405cca3f3d
- worktree: /home/openclaw/ekotov-wiki-worktrees/p23final
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 812.4s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 50
- changed files: 50
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
  - test-model/approved/p23-fastline/APPROVAL.md
  - test-model/approved/p23-fastline/README.md
  - test-model/approved/p23-fastline/TC-p23-100.md
  - test-model/approved/p23-fastline/TC-p23-101.md
  - test-model/approved/p23-fastline/TC-p23-102.md
  - test-model/approved/p23-fastline/TC-p23-103.md
  - test-model/approved/p23-fastline/TC-p23-104.md
  - test-model/approved/p23-fastline/TC-p23-105.md
  - test-model/approved/p23-fastline/TC-p23-106.md
  - test-model/approved/p23-fastline/TC-p23-107.md
  - test-model/approved/p23-fastline/TC-p23-108.md
  - test-model/approved/p23-fastline/TC-p23-109.md
  - test-model/approved/p23-fastline/TC-p23-110.md
  - test-model/approved/p23-fastline/TC-p23-111.md
  - test-model/approved/p23-fastline/TC-p23-112.md
  - test-model/approved/p23-fastline/TC-p23-113.md
  - test-model/approved/p23-fastline/TC-p23-114.md
  - test-model/approved/p23-fastline/TC-p23-115.md
  - test-model/approved/p23-fastline/TC-p23-116.md
  - test-model/approved/p23-fastline/TC-p23-117.md
  - test-model/approved/p23-fastline/TC-p23-118.md
  - test-model/approved/p23-fastline/TC-p23-119.md
  - test-model/approved/p23-fastline/TC-p23-120.md
  - test-model/approved/p23-fastline/TC-p23-121.md
  - test-model/impact/p23-fastline.md
  - test-model/regress/p23-fastline/regress-final.md
  - test-model/reviews/p23-fastline/review-001.md
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
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p23final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
675 passed, 12 skipped, 2 xfailed, 79 warnings in 811.20s (0:13:31)
```
