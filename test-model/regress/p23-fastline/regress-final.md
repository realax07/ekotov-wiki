# Regress p23-fastline — regress-final.md

- change: p23-fastline
- run: p23-fastline-2 final (финальный перегон на head 92a21c1 после static_v-бампа p23-fastline-2; полный сериал, канонический контур nginx:18443, свежая БД reset стенда; 679 passed / 12 skipped / 2 xfailed, pytest exit 0; контрольный прогон mobile-сьюта test_p23_fastline_mobile_ui 4/4 PASSED; desktop не менялся — покрыт desktop-сьютами сериала; дельта head vs 9a30b23 — только TC-маркеры rule 6 и static_v бамп)
- date: 2026-10-21T06:49:26+00:00
- commit: 92a21c1c2b2b84aa7bee05b533e2cba08fa0ca8b
- worktree: /tmp/wt-p23mob
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 883.8s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 55
- changed files: 55
  - PRODUCT_BACKLOG.md
  - backend/app/pages.py
  - design/p23-fastline/mobile/after-empty-390.png
  - design/p23-fastline/mobile/after-occupied-390.png
  - design/p23-fastline/mobile/before-empty-390.png
  - design/p23-fastline/mobile/before-occupied-390.png
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
  - … и еще 5
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_video_convert_ui.py:26
  /tmp/wt-p23mob/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /tmp/wt-p23mob/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /tmp/wt-p23mob/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /tmp/wt-p23mob/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /tmp/wt-p23mob/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /tmp/wt-p23mob/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /tmp/wt-p23mob/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /tmp/wt-p23mob/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /tmp/wt-p23mob/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /tmp/wt-p23mob/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /tmp/wt-p23mob/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /tmp/wt-p23mob/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
679 passed, 12 skipped, 2 xfailed, 81 warnings in 882.46s (0:14:42)
```
