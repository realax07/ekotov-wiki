# Отчет dev по куску B (волна 3: конвертация) — tasks 3.1/3.2

Ветка `pipeline/video-hosting`, head b43ef99 → коммит волны 3. Зоны:
`services/video/app/converter.py` (новый), `services/video/app/main.py`
(строка старта), `services/video/app/videos.py` (шов enqueue + minor-2/3),
`services/video/app/storage.py` (шов-хелпер), `frontend/templates/video.html`,
`frontend/static/js/video.js`, `services/video/tests/**`,
`tests/web/test_video_convert_ui.py` (новый), tasks.md 3.1/3.2 [x].

## Реализовано

- **app/converter.py** (3.1): очередь queue.Queue + ровно 1 поток-воркер
  (start_worker — idempotent); subprocess ffmpeg `nice -n 10`
  (preexec_fn), wall-clock timeout 30 мин (истечение = kill = неудача
  попытки), `-c:v libx264 -preset veryfast -movflags +faststart`;
  превью `-frames:v 1` тем же проходом, для уже-mp4 — БЕЗ
  перекодирования (конвертация скипается, снимается только кадр);
  статусы uploaded → converting → ready/error — пишет ТОЛЬКО воркер;
  ровно 1 авторетрай (non-zero exit / timeout / нет выходного файла /
  не снялся кадр), после 2-й неудачи error, оригинал сохранен, частичные
  артефакты удалены; успех: mp4+preview в томе, оригинал удален
  (для mp4-исходника оригинал и есть готовое видео — остается,
  playable_path его отдает), size_bytes обновлен; отмена DELETE —
  in-memory флаг, воркер проверяет перед записью результата, артефакты
  отбрасываются; крэш-восстановление recover_pending() на старте:
  uploaded И converting → uploaded + re-enqueue, частичный mp4/кадр
  удалены (инвариант design §3 — проверен тестом TC-vid-067).
- **main.py**: start_worker() в lifespan-старте приложения (НЕ на
  импорте — recover_pending читает БД, см. эскалацию 2).
- **videos.py**: шов куска A включен — POST 201 возвращает
  `status:"uploaded"` (sdd §3) и ставит в converter.enqueue(); DELETE
  вызывает converter.cancel() ДО удаления строки/каталога.
- **Фронт**: бейджи статусов по мокапу video-list.html («загружено»/
  «конвертируется» — пульсирующая точка + aria-busy / «готово» /
  «ошибка» с подсказкой «конвертация не удалась — оригинал сохранен»);
  convert-note «Сервер сконвертирует видео в mp4…» в форме загрузки
  (ревью-001 п.2, дословно мокап video-upload.html); автообновление
  списка polling'ом 3 c, пока есть uploaded/converting (SSE спекой не
  предусмотрена); открытый просмотр перерисовывается при смене статуса
  (плейсхолдер → плеер) без перезагрузки.
- **review-001**: minor-2 (обрыв тела → ложный текст «больше 500 МБ») —
  тексты 422 разведены; minor-3 (тихие orphan-файлы при сбое rmtree) —
  warning-лог добавлен; п.2 (convert-note) — включен; note про обход
  статуса через /videos/ (nginx alias проверяет только сессию) —
  ПРИНЯТО ОСОЗНАННО: равноправие пользователей (FR-84) — неготовый
  исходник доступен только держателям сессии сервиса, отдельной
  проверки статуса в authcheck не заводили (стык auth_request остается
  O(мс), contract design §5).

## Тесты

- `services/video/tests`: **59 passed** (44 до волны + 15 новых:
  test_converter.py, TC-vid-060…074 — реальные 0.3-сек видео
  mkv→mp4/превью для уже-mp4/поврежденный файл; фейки-ffmpeg
  (скрипт-заглушки) на ретрай/timeout-kill/нет-выходного-файла/
  неснятый-кадр; крэш-восстановление uploaded+converting; отмена
  DELETE; серийность воркера; статус через converting; нет исходника;
  гонка DELETE; cancel до старта). Двух порядков прогон — зеленый
  (фикстура-гигиена: воркер не переживает тест).
- `tests/web`: **+3** TC-vid-107…109 (test_video_convert_ui.py):
  convert-note, 4 бейджа по мокапу + aria-busy + подсказка error +
  плеер только для «готово» (route-мок /api/videos*), автообновление
  «конвертируется»→«готово» без перезагрузки и остановка опроса.
  Видео-сьют tests/web: 9 passed.
- Полный регресс: стенды api/web-наборов в этой среде не поднимаются
  (паритет волны D) — сбор tests/ 606 тестов / 0 errors; смоук
  сквозного сценария волны 3 (TestClient + реальный ffmpeg: POST
  uploaded → ready, mp4+preview в томе, превью 200, битый файл → error
  с оригиналом, DELETE чистит том) — прогнан вручную, зеленый.
- `openspec validate video-hosting --type change --strict` — green;
  node --check video.js — ok.

## Эскалации/решения (5)

1. **storage.py: +find_original()** — точечное расширение зоны 1.3
   (шов sdd §2 «пути только через storage»; конвертер иначе строил бы
   путь сам). Прецедент A-волны (Dockerfile COPY вне литеральной зоны).
2. **start_worker в lifespan, не на импорте main** — смоук волны
   поймал: импортный старт читал БД до env-конфигурирования процесса
   (sqlite3.OperationalError на /data/wiki.db при стороннем импорте
   app.main). Проверено сквозным смоуком.
3. **env-гейты**: EKOTOV_WIKI_CONVERTER=off (тесты A/D —
   детерминированный «uploaded» без писателя) и EKOTOV_WIKI_FFMPEG
   (путь бинаря; в образе — /usr/local/bin/ffmpeg с PATH). Оба —
   env-дефолты, прод-поведение без них не меняется.
4. **mp4-исходник**: video.mp4 НЕ создается (нет перекодирования),
   готовым файлом остается original.mp4 — считаю соответствующим
   design §3 r2 («без перекодирования»); альтернатива — rename в
   video.mp4, сделаю по замечанию ревью, если требуется.
5. **flow_check J10**: 13 закрытых dev-задач без approve-вердикта
   (11 существовали до волны, +3.1/3.2 по ТЗ «чекбоксы [x]») —
   ожидаемый фон до ревью волны; чекбокс-порядок из ТЗ соблюден
   (ревью-файлы — отдельными pipeline-коммитами).
