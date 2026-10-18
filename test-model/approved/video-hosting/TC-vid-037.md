# TC-vid-037 — Здоровье и лимиты контейнера video на стенде (NFR-35)

- **Change:** video-hosting
- **Источник:** video-service: «Ресурсы и здоровье сервиса video» (NFR-35/NFR-20) / Scenario: Здоровье и лимиты на стенде
- **Тип:** НФТ | **Приоритет:** Must
- **Среда/предусловия:** контейнер `video` запущен (mem_limit, healthcheck, json-file 10m×3); доступ к хосту; загружен файл ~200 МБ
- **Шаги:**
  1. Проверить `docker inspect <video>`: Healthcheck, Memory, LogConfig.
  2. Запустить конвертацию файла ~200 МБ; в ходе нее каждые 10 с снимать `docker stats --no-stream <video>`.
  3. Проверить healthcheck в ходе конвертации.
  4. Суммировать mem_limit стека; зафиксировать замеры в REPORT.
- **Ожидаемый результат:** шаг 1 — healthcheck настроен, mem_limit задан, LogConfig json-file max-size 10m max-file 3; шаг 2–3 — healthcheck отвечает (healthy), RAM в пределах лимита во всей конвертации; шаг 4 — суммарные лимиты стека оставляют хосту ≥ 2 GB резерва; замеры зафиксированы в REPORT до прод-выкатки.
- **Тестовые данные:** файл ~200 МБ; `docker inspect`/`docker stats`; REPORT стенда.
