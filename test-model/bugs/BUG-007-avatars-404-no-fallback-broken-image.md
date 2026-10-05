# BUG-007: QA-стенд web/api — nginx-локация `/avatars/` отдает 404 при отсутствии файла (нет fallback в app)

- **ID:** BUG-007
- **Дата:** 2026-10-05
- **Окружение:** worktree `/home/openclaw/ekotov-wiki-worktrees/qa-21-netdata`, ветка `add-netdata-monitoring`, HEAD `2e6efb5`; локальный QA-стенд nginx 1.24.0 (:18443, паритет `services/frontend/nginx/ekotov-wiki.conf`) → app :8080; Python 3.11.16, venv `/home/openclaw/venvs/wiki`.
- **Severity:** minor (в прод-топологии `/avatars/` — named volume, файл существует после успешной загрузки; краевой случай: запись об аватаре в БД есть, файла в томе нет → сломанная картинка вместо fallback на кружок-фоллбек)
- **Корреляция flowctl:** 97a81b928f744dd6a76cdce801802699 (QA 2.1 add-netdata-monitoring)

## Трассировка

- Затронут: FR-42/сценарий «Аватар отображается в блоке профиля» (fallback-ветка), UX сайдбара; к падениям сьютов 2.1 НЕ привел (web 171p/1s — аватар-тесты используют upload через UI, файл создается).
- Замечен в `error_log` QA-стенда: повторяющийся `open() "/tmp/nginx-qa21/avatars/1.png" failed (2: No such file or directory)` при наличии в БД `avatar_path` без файла.

## Шаги воспроизведения

1. Поднять стенд: nginx-паритет + app; в БД `users.avatar_path='1.png'`, файла в avatars-каталоге нет.
2. `curl -I http://<nginx>/avatars/1.png` → **404** (текстовая страница nginx, без fallback).

## Ожидание (по духу FR-42/Д-10)

Фронтенд при `avatar_url` из `/api/auth/me` ставит `src` и ожидает файл; при отсутствии файла браузер показывает сломанную картинку. Fallback-ветка (кружок с первой буквой) есть только при `avatar_url = null`. Серверная сторона 404 для битого пути — норма nginx (`alias` без `try_files`/`error_page`), НО: app при выдаче `avatar_url` не проверяет существование файла → рассинхрон БД/тома дает permanent broken image в сайдбаре у пользователя.

## Факт

```
2026-10-05 19:29:37 [error] ... open() ".../avatars/1.png" failed (2: No such file or directory)
GET /avatars/1.png → 404
```

## Анализ

- Рассинхрон возможен только при ручном удалении файла из тома/восстановлении БД без тома (сценарий отката deploy §6 не затрагивает avatars — том общий).
- Варианты лечения (вне зоны QA 2.1, на усмотрение ПМ): (а) `avatar_url` выдавать только при существующем файле (проверка в app при чтении профиля); (б) onerror-fallback на клиенте в `fillProfile` (замена `<img>` на кружок при ошибке загрузки); (в) `error_page 404` в nginx-локации `/avatars/` на transparent-pixel.

## Рекомендация

Зафиксировать как кандидата в бэклог полировки (не блокер пакета add-netdata-monitoring: аватары пакетом не затрагиваются; воспроизведено на синтетическом рассинхроне стенда).
