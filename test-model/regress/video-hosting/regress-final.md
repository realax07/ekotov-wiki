# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T16:29:20+00:00
- commit: f1f40d0430521ea39c77af6f99244e7c5841a0da
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8
- verdict: PASS
- diff source: git diff main...HEAD
- changed files: 15
  - code-reviews/video-hosting/review-003.md
  - code-reviews/video-hosting/review-mapping.json
  - frontend/static/js/video.js
  - frontend/templates/video.html
  - openspec/changes/video-hosting/proposal.md
  - openspec/changes/video-hosting/specs/video-service/spec.md
  - openspec/changes/video-hosting/tasks.md
  - services/video/app/videos.py
  - services/video/tests/test_videos_rename.py
  - test-model/regress/video-hosting/regress-final.md
  - tests/web/dnd_helpers.py
  - tests/web/test_bug014_search_task_view.py
  - tests/web/test_p12_ui_polish_r8.py
  - tests/web/test_r3_dnd_ui.py
  - tests/web/test_video_rename_ui.py
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_tooltip_r4.py:38
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_tooltip_r4.py:38: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_rename_ui.py:25
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_rename_ui.py:25: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh8/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
597 passed, 12 skipped, 2 xfailed, 74 warnings in 792.01s (0:13:12)
```
