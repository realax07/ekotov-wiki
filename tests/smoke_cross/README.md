# tests/smoke_cross — cross-domain smoke (эшелон 2, J54)

Смоук полного контура: роутинг/авторизация/health/представитель сервиса.
Гоняется `flowctl regress --change C --tier smoke` ПЕРЕД code_review и
перед merge (2–3 мин). Список сьютов проекта — манифест
`test-model/smoke-cross/manifest.json` (`{"suites": ["tests/...", ...]}`);
пустой манифест → WARN и exit 0. Требования к тестам: быстрые,
стендонезависимые где возможно, детерминированные при `--xdist`
(session-фикстуры не делятся между воркерами).

## Контур и сьюты

Канонический контур vh9: nginx:18443 → app:8080 + search:8378 + images:8379 +
video:8380. Подъем: `bash /tmp/vh9-stand/reset.sh` (чистая БД + seed
owner/wife + старт; перед смоук-прогоном обязателен — переиспользуемый стенд
копит мусор прошлых сессий). Базовый URL — env `EKOTOV_WIKI_BASE_URL`
(дефолт `http://127.0.0.1:18443` — вход через nginx).

Сьюты (по домену карты `test-model/regress-domains.json`, 1–2 теста на домен):

| Файл | Домен | Что проверяет |
|---|---|---|
| `test_smoke_health.py` | (весь контур) | TC-smoke-001/002: health app/search/images/video + роутинг nginx→app |
| `test_smoke_auth_search.py` | auth-search | TC-smoke-003/004: login 200/401, аноним 401, поиск через nginx |
| `test_smoke_wiki.py` | wiki | TC-smoke-005: /wiki — 302 анонимно, 200 с сессией |
| `test_smoke_gallery.py` | gallery | TC-smoke-006: /gallery 200 с сессией |
| `test_smoke_video.py` | video | TC-smoke-007: /video 200 с сессией |

Тесты read-only (логин создает только сессию), requests-based — без
playwright; api-часть смоука безопасно гоняется с `--xdist 4`.

## Запуск

```bash
bash /tmp/vh9-stand/reset.sh                      # свежий стенд перед прогоном
/home/openclaw/venvs/wiki/bin/python scripts/flowctl.py regress \
  --repo . --change <change-id> --tier smoke      # эшелон 2 (артефакт + вердикт)
# точечно: pytest tests/smoke_cross -q            # (~15–20 c, см. отчет)
```

## Baseline известных фейлов main (правило ведения)

`test-model/regress/baseline.json` — список записей
`{"test": "<nodeid>", "reason": "<причина>", "added": "<ISO-дата>"}`.
На старте (2026-10-19) — **пустой**: зафиксированных флейков на main нет.

Правила ведения:

1. Запись добавляет **только ПМ** после триажа падения: падение воспроизведено
   на чистом main в том же окружении и признано флейком/фоном (не регрессом
   диффа). Dev падение в baseline не вносит — предлагает через
   `flowctl regress --suggest-baseline` (пишет в
   `test-model/regress/baseline-suggestions.json`, перенос — ручное решение ПМ).
2. Тест из baseline, упавший на regress (без `--final`), вердикт не красит —
   в артефакте помечается «baseline: ожидаемо-падающий (reason)».
3. На `--final` (regress-final, эшелон 3) baseline игнорируется — полный
   честный прогон, фон красит наравне с остальными.
4. Запись удаляется, когда тест перестал падать (зеленый на нескольких
   прогонах подряд) — baseline не росыпь «вечных» скипов, а короткий
   актуальный список; причина в записи обязательна.
