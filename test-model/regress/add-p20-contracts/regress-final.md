# Regress add-p20-contracts — regress-final.md

- change: add-p20-contracts
- date: 2026-11-16T14:43:01+00:00
- commit: 50b19602bee6f678d971aacecfae202e9cef91a3
- worktree: /tmp/p20-qa-wt (ветка pipeline/p20-qa)
- verdict: PASS
- tier: final (эшелон 3: regress-final перед PR)
- duration: ~1345s (web 1101.7s + unit 23.6s + api 114.4s + сервисные 46.3s)
- diff source: git diff main...HEAD (QA-контур: TC-p20-001 + автотест + ревью кейса; код продукта не менялся)
- changed files: 4
  - services/video/tests/test_videos_service.py
  - test-model/approved/p20-contracts/TC-p20-001.md
  - test-model/reviews/add-p20-contracts/review-001.md
  - tests/unit/test_p20_map_contracts.py
- suites: tests (web полная серия + unit + api + integration) + services/*/tests (4 сервиса)
- pytest exit code: 0

## Факты прогонов (qa_stand_up.sh, стенд /tmp/qa-stand-p20qa, nginx :18443, health OK)

| Набор | Результат | Время |
|---|---|---|
| tests/web (ПОЛНАЯ серия, playwright, стенд) | **437 passed, 3 skipped** | 1101.7s (18:21) |
| tests/unit (вкл. 2 новых TC-p20-001) | **72 passed** | 23.6s |
| tests/api | **329 passed, 11 skipped, 2 xfailed** | 114.4s |
| tests/integration | нет тестов (каталог = README) | — |
| services/search/tests | 17 passed | 2.06s |
| services/video/tests (вкл. TC-vid-115 переименованный) | 111 passed | 29.42s |
| services/images/tests | 42 passed | 11.35s |
| services/weather/tests | 26 passed | 3.47s |

Итог: **1008 passed + 14 skipped + 2 xfailed, 0 failed**.

## Базлайн-сверка

Ожидание на main: tests-джоба зеленая (pre-existing фейлов нет; TC-GAL-111/117 закрыты). Факт: полный green, ни одного падения/флака — расхождений с базлайном нет, изолированный перепрогон не потребовался. 3 skipped / 2 xfailed — штатные маркеры сьюта.

## М-заметки (NFR-46)

- Гейт дрейфа (CLI pr_validate, локальный прогон на HEAD): **0.25s** — порог ≤ 30s выполнен с запасом (×120).
- Сервисные сьюты со схемной валидацией: сумма pytest-времени 2.06+29.42+11.35+3.47 = **46.30s** против базлайна волны 5 **46.1s** (tasks.md факт 5.5) — прирост **+0.4%**, порог ≤ 20% выполнен.
- Стоимость поддержки: 2 новых юнит-теста TC-p20-001 — файловые ассерты, стенд не нужен, 0.02s.

## Хвост лога (до 50 строк)

```
tests/web: 437 passed, 3 skipped, 10 warnings in 1101.74s (0:18:21)
WEB_EXIT=0
tests/unit: 72 passed in 23.56s
tests/api: 329 passed, 11 skipped, 2 xfailed, 1 warning in 114.38s (0:01:54)
services/{search,video,images,weather}/tests: 17/111/42/26 passed (46.30s суммарно)
```
