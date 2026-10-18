# Regress video-hosting — regress-final.md

- change: video-hosting
- date: 2026-10-18T12:07:25+00:00
- commit: f950db19fb56e18b139b16a9b7382a53c3d7334b
- worktree: /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6
- verdict: PASS
- diff source: git diff main...HEAD
- changed files: 120
  - .github/workflows/flow.yml
  - PLAN-video-hosting.md
  - architecture/map.md
  - backend/app/migrate_video.py
  - backend/app/pages.py
  - code-reviews/video-hosting/dev-report-A-escalations.md
  - code-reviews/video-hosting/dev-report-B.md
  - code-reviews/video-hosting/dev-report-C.md
  - code-reviews/video-hosting/dev-report-D-wave2.md
  - code-reviews/video-hosting/review-001.md
  - code-reviews/video-hosting/review-002.md
  - code-reviews/video-hosting/review-mapping.json
  - conftest.py
  - contracts/openapi.json
  - deploy/compose.test.yaml
  - deploy/compose.yaml
  - design/video-hosting/video-list.html
  - design/video-hosting/video-upload.html
  - design/video-hosting/video-view.html
  - frontend/static/js/video.js
  - frontend/templates/base.html
  - frontend/templates/video.html
  - openspec/changes/video-hosting/design.md
  - openspec/changes/video-hosting/proposal.md
  - openspec/changes/video-hosting/requirements.md
  - openspec/changes/video-hosting/review-architecture.md
  - openspec/changes/video-hosting/sdd.md
  - openspec/changes/video-hosting/specs/video-service/spec.md
  - openspec/changes/video-hosting/tasks.md
  - scripts/flowctl.py
  - scripts/pr_validate.py
  - scripts/session_check.py
  - scripts/session_worktree.sh
  - services/frontend/Dockerfile
  - services/frontend/nginx/ekotov-wiki.conf
  - services/frontend/nginx/videos-headers.inc
  - services/frontend/nginx/videos-proxy.inc
  - services/video/Dockerfile
  - services/video/app/__init__.py
  - services/video/app/converter.py
  - services/video/app/db.py
  - services/video/app/main.py
  - services/video/app/middleware.py
  - services/video/app/social.py
  - services/video/app/storage.py
  - services/video/app/videos.py
  - services/video/install_ffmpeg.py
  - services/video/tests/__init__.py
  - services/video/tests/conftest.py
  - services/video/tests/test_converter.py
  - … и еще 70
- suites: tests
- pytest exit code: 0

## Хвост лога (до 50 строк)

```
tests/web/test_settings_categories_ui.py:30
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_settings_categories_ui.py:30: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_settings_profile_r4.py:52
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_settings_profile_r4.py:52: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_tooltip_r4.py:38
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_tooltip_r4.py:38: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_convert_ui.py:26
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_convert_ui.py:26: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_social_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_social_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_ui.py:22
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_ui.py:22: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_video_wiki_isolation_ui.py:16
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_video_wiki_isolation_ui.py:16: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.e2e, pytest.mark.web, pytest.mark.must]

tests/web/test_view_modal_r4.py:43
  /home/openclaw/ekotov-wiki-worktrees/regress-final-vh6/tests/web/test_view_modal_r4.py:43: PytestUnknownMarkWarning: Unknown pytest.mark.web - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    pytestmark = [pytest.mark.web, pytest.mark.must]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
594 passed, 12 skipped, 2 xfailed, 72 warnings in 786.43s (0:13:06)
```
