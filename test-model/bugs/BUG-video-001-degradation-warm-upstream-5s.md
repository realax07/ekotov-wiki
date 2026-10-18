# BUG-video-001: деградация при остановке video — первый запрос висит ~5 c при теплом upstream-пуле nginx

- **Дата:** 2026-10-18 (qa_automation, flow=1, video-hosting)
- **Кейс:** TC-vid-004 (шаг 3: «оба маршрута `/api/videos*` и `/videos/` отвечают HTTP 503 за < 2 с (не таймаут, управляемый ответ)»)
- **Серьезность:** minor (управляемый 503 возвращается ВСЕГДА, доска/поиск/wiki/галерея не затронуты; нарушается только верхняя граница времени ответа в теплой фазе)

## Факт

После `docker stop wiki-test-video-1` на стенде wiki-test:

| Состояние nginx upstream-пула | GET /api/videos | GET /videos/<id>/preview.jpg |
|---|---|---|
| холодный пул (нет открытых keep-alive соединений к video) | 503 за **0.01 c** | 503 за **0.00 c** |
| теплый пул (3+ запросов к video непосредственно до stop) | 503 за **5.01 c** ×2, затем 1.14 c, 0.00 c | 503 за 5.01 c |

Воспроизводимость: 3/3 прогона с прогревом → первые 1–2 запроса ~5.01 c; 1/1 прогон без прогрева → мгновенно.

## Root cause (диагноз)

Остановленный контейнер: docker сеть отдаёт **DROP** (не RST) на SYN/данные к IP контейнера. nginx при теплом пуле:
1) первая попытка — запись в stale keep-alive соединение (успешно уходит в пустоту),
2) ретрай на новое соединение — SYN тонет,
3) ответ формируется только по `proxy_connect_timeout 5s` (services/frontend/nginx/ekotov-wiki.conf, строка 46).

Управляемость ответа (@videos_down / error_page) работает во всех наблюдениях: статус ровно 503, не 500/таймаут клиента.

## Рекомендация

Снизить `proxy_connect_timeout` для video-апстрима до 1 c (аналогично search/images при наличии) либо добавить `proxy_upstream_next_tries`/быстрый failover. Проверка по кейсу: после правки оба маршрута ≤ 2 c в теплой фазе.

## Окружение

wiki-test стенд (docker compose.test.yaml), nginx frontend, образ video:test пересобран на HEAD pipeline/video-hosting (ef0103f + рабочая копия qa_automation); chromium/requests, https://localhost:8443.
