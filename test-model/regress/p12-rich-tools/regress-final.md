# Regress p12-rich-tools — regress-final.md

- change: p12-rich-tools
- run: 2 (перегон финала на финальном head; прогон №1 — adbd485, продукт идентичен: различия только test-model/** и static_v-строка)
- date: 2026-10-20T16:56:01+00:00
- commit: 9d452acb06c496c6c3d27fc99749a3a28a2cd7a8
- worktree: /home/openclaw/ekotov-wiki-worktrees/p12-final
- verdict: PASS
- tier: domain (эшелон 1: доменный regress)
- duration: 800.4s
- diff source: git diff main...HEAD
- domain map: project map test-model/regress-domains.json задана, правил нет — применен дефолт
- changed files: 71
- changed files: 71
  - backend/app/pages.py
  - backend/app/sanitize.py
  - code-reviews/chore-p12-dev/review-001.md
  - code-reviews/chore-p12-dev/review-002.md
  - frontend/static/css/wiki.css
  - frontend/static/js/wiki/editor.js
  - frontend/static/js/wiki/page.js
  - frontend/static/js/wiki/rich/codeblock.js
  - frontend/static/js/wiki/rich/headings.js
  - frontend/static/js/wiki/rich/highlight.js
  - frontend/static/js/wiki/rich/model.js
  - frontend/static/js/wiki/rich/spoiler.js
  - frontend/static/js/wiki/rich/tabletools.js
  - frontend/static/js/wiki/rich/tabs.js
  - openspec/changes/p12-rich-tools/design.md
  - openspec/changes/p12-rich-tools/impact.md
  - openspec/changes/p12-rich-tools/proposal.md
  - openspec/changes/p12-rich-tools/review-architecture.md
  - openspec/changes/p12-rich-tools/specs/p12-rich-tools/spec.md
  - openspec/changes/p12-rich-tools/specs/wiki/spec.md
  - openspec/changes/p12-rich-tools/tasks.md
  - test-model/approved/p12-rich-tools/APPROVAL.md
  - test-model/approved/p12-rich-tools/README.md
  - test-model/approved/p12-rich-tools/TC-rich-001.md
  - test-model/approved/p12-rich-tools/TC-rich-002.md
  - test-model/approved/p12-rich-tools/TC-rich-003.md
  - test-model/approved/p12-rich-tools/TC-rich-004.md
  - test-model/approved/p12-rich-tools/TC-rich-005.md
  - test-model/approved/p12-rich-tools/TC-rich-006.md
  - test-model/approved/p12-rich-tools/TC-rich-007.md
  - test-model/approved/p12-rich-tools/TC-rich-008.md
  - test-model/approved/p12-rich-tools/TC-rich-009.md
  - test-model/approved/p12-rich-tools/TC-rich-010.md
  - test-model/approved/p12-rich-tools/TC-rich-011.md
  - test-model/approved/p12-rich-tools/TC-rich-012.md
  - test-model/approved/p12-rich-tools/TC-rich-013.md
  - test-model/approved/p12-rich-tools/TC-rich-014.md
  - test-model/approved/p12-rich-tools/TC-rich-015.md
  - test-model/approved/p12-rich-tools/TC-rich-016.md
  - test-model/approved/p12-rich-tools/TC-rich-017.md
  - test-model/approved/p12-rich-tools/TC-rich-018.md
  - test-model/approved/p12-rich-tools/TC-rich-019.md
  - test-model/approved/p12-rich-tools/TC-rich-020.md
  - test-model/approved/p12-rich-tools/TC-rich-021.md
  - test-model/approved/p12-rich-tools/TC-rich-022.md
  - test-model/approved/p12-rich-tools/TC-rich-023.md
  - test-model/approved/p12-rich-tools/TC-rich-024.md
  - test-model/approved/p12-rich-tools/TC-rich-025.md
  - test-model/approved/p12-rich-tools/TC-rich-026.md
  - test-model/approved/p12-rich-tools/TC-rich-027.md
  - … и еще 21
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_weather_ui.py:35
  /home/openclaw/ekotov-wiki-worktrees/p12-final/tests/web/test_weather_ui.py:35: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
663 passed, 12 skipped, 2 xfailed, 78 warnings in 798.67s (0:13:18)
```
