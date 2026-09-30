# TC-ava-env-101 — РУЧНАЯ (деплой-проверка): nginx location /avatars/ — alias и кеш-заголовки

- **CHK:** CHK-R4-100
- **Change:** add-r4-user-profile-ticket-view
- **Источник:** auth: «Загрузка аватара» (ОГР-16, review-001 blocker C-1; E10 — внешнее допущение); impact §3 «nginx location /avatars/ → alias /var/lib/ekotov-wiki/avatars/, expires 7d, Cache-Control: public — НЕТ, слепой контур»; deploy/nginx-ekotov-wiki*.conf (шаблон), deploy/RUNBOOK.md §6
- **Тип:** НФТ, средовая (ручная процедура — автоматизации не подлежит: прод + nginx-слой вне контура автотестов; web-тесты видят только `src=/avatars/…?v=`, заголовки и alias не проверяются) | **Приоритет:** Must
- **Маркер:** manual (НЕ автоматизируется; носитель протокола деплой-проверки — как TC-sel-102 в Р3)
- **Предусловия:** деплой Релиза 4 на прод выполнен (deploy.sh, шаг 6 runbook — nginx-конфиг с `location /avatars/` применен, `nginx -t` и reload пройдены); в системе есть пользователь с загруженным аватаром (или файл заведен шагом 1).
- **Шаги (после деплоя, по runbook):**
  1. Убедиться, что каталог отдачи существует и вне rsync-корня: `ls -la /var/lib/ekotov-wiki/avatars/` — файл(ы) `*.png`, владелец `wiki:wiki`; при пустом каталоге — загрузить аватар через UI настроек (png ≤2 МБ) и повторить.
  2. Взять фактический URL аватара из `GET /api/auth/me` (ключ `avatar_url`, вида `/avatars/<user_id>.png?v=<avatar_updated_at>`).
  3. Смоук заголовков: `curl -sI https://<прод-URL>/<avatar_url>` — зафиксировать статус и заголовки.
  4. Проверить отдачу содержимого: `curl -s -o /tmp/ava.png -w '%{http_code} %{content_type}' https://<прод-URL>/<avatar_url>`; сравнить `sha256sum /tmp/ava.png` с файлом на диске `/var/lib/ekotov-wiki/avatars/<user_id>.png`.
  5. Негатив-контроль alias: `curl -sI https://<прод-URL>/avatars/../etc/passwd` (или несуществующий `/avatars/0000.png`) — нет доступа вне каталога/404, не 200.
  6. Протокол (вывод шагов 3–5) — в `test-model/` к отчету деплоя Р4.
- **Ожидаемый результат:** шаг 3 — HTTP 200; заголовки `Expires`/`Cache-Control: public` соответствуют `expires 7d` (дата ≈ +7 дней от запроса) и `Cache-Control: public`; `Content-Type: image/png`. Шаг 4 — 200, `image/png`, хеш совпадает с файлом в `/var/lib/ekotov-wiki/avatars/` (alias работает, файл отдается вне rsync-корня — закрытие review-001 C-1). Шаг 5 — обход каталога и чужие пути не отдаются (404/403, не 200 с содержимым). При заголовках «по умолчанию» (без expires/public) — ОТКЛОНЕНИЕ: пользователь не увидит новый аватар до 7 дней (риск impact §4.3), конфиг nginx правится до закрытия релиза.
- **Тестовые данные:** прод-стенд (`deploy/README`, `deploy/RUNBOOK.md`); реальный `avatar_url` из `GET /api/auth/me`; каталог `/var/lib/ekotov-wiki/avatars/`; шаблон конфига `deploy/nginx-ekotov-wiki.conf` (location /avatars/).
