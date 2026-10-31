# Отчет dev по куску A — 5 эскалаций (deleg_9ee8a943, 2026-10-17)

1. POST 201 возвращает status:'ready' вместо sdd §3 'uploaded' — кусок A без
   конвертации, файл отдается как есть; шов enqueue_conversion()-заглушка
   сохранен; откат формы в 3.1. — СОГЛАСОВАНО ревьюером.
2. convert-note мокапа («сервер сконвертирует в mp4») в форму загрузки НЕ
   включен — ложное обещание до куска B; добавить в 3.1.
3. services/frontend/Dockerfile (COPY videos-*.inc) — вне литеральной зоны
   1.4, но без нее includes не попадают в образ; прецедент images 1.4.
4. deploy 6.1: свежий named volume videos-data создается root-owned — нужен
   chown 10001:10001 (прецедент images-data).
5. nginx: auth_request превращает отказ subrequest в 500 основного запроса —
   @videos_down назначен с 500 в error_page (проверено: 503, не голый 500).

Ревью review-001: п.1 согласован; п.2–4 перенесены в 3.1; п.5 — note к 3.1.
