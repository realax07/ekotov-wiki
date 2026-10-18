# Отчет dev по волне 2, кусок D (социальный слой) — tasks 2.1–2.5

Реализовано (ветка pipeline/video-hosting, коммит волны 2):

1. **2.1 миграция** — `backend/app/migrate_video.py`: + `video_comments`
   (id TEXT PK, video_id FK CASCADE, user_id FK users, text NOT NULL,
   created_at), `video_reactions` (PK(video_id,user_id), value CHECK IN
   (1,-1), FK CASCADE, created_at), `ALTER ... ADD COLUMN category_id
   INTEGER REFERENCES image_categories(id)` идемпотентно (проверка наличия
   колонки); одна транзакция BEGIN IMMEDIATE; автосверка расширена
   (колонки/PK/FK/CASCADE/CHECK по PRAGMA+sqlite_master). Fail fast при
   отсутствии users ИЛИ image_categories. Проверено: двойной запуск на БД
   куска A и на чистой — exit 0; CHECK/PK/CASCADE — runtime-пробами.
2. **2.2 API** — `services/video/app/social.py` (+ include_router в
   main.py, строка регистрации — по sdd §2 «main.py включает роутеры»):
   comments GET/POST/DELETE (422 пустой/whitespace, 403 чужой, 404),
   PUT reaction {value:1|-1} — toggle/перенос в одной транзакции BEGIN
   IMMEDIATE, ответ {my_reaction, likes, dislikes}; GET /api/videos/
   categories — SELECT image_categories (RO). db.py: профиль владения
   обновлен (RW D-таблицы, RO справочник). Новых exempt НЕТ (NFR-38).
3. **2.3 категории в videos.py** — POST: опц. category_id с валидацией
   существования (422), NULL = «Без категории»; GET: ?category=<id|none>
   + category_id/category_name/likes/dislikes/my_reaction; DELETE —
   CASCADE (FK, foreign_keys=ON).
4. **2.4 фронтенд** — video.html/video.js по мокапам (блоки D):
   реакции (пилюли с счетчиками, my-vote, aria-pressed, hint),
   комментарии (автор/время/текст, «удалить» только у своих — сравнение
   с me.id из /api/auth/me, «Отправить» disabled пока пусто), фильтр
   категории в тулбаре, пилюля на карточке и в деталях, select категории
   при загрузке + «+ Новая категория…» (создание через POST /api/categories
   ядра — справочник один, RO у сервиса). Иконки inline-SVG, XSS —
   createElement/textContent.
5. **2.5 тесты** — services/video/tests/test_social.py (12 тестов,
   TC-vid-040…058: 401 NFR-38 на все D-эндпоинты, 422/403/404 комментариев,
   реакции: постановка/снятие/перенос — счетчики ровно на единицу, одна
   строка на пару; категории: RO-справочник/валидный/422/none-фильтр;
   CASCADE); фикстура test_videos_service.py расширена схемой куска D
   (2 контракта сверены — openapi/list обновлены по r2-спеке);
   tests/web/test_video_social_ui.py (3 теста, TC-vid-104…106 — блоки D
   по мокапам; API видео на web-стенде не поднят — каркас).

Тест-каунт:
- services/video/tests: **44 passed** (было 32; +12 social).
- tests/ collect: **603 / 0 errors** (база 600/0; +3 web-теста D).
- web: video 3/3 (кусок A) + 3/3 (D новые) + навигация 3/3.
- Полный регресс серийно: web 226 passed/9 failed/16 errors; не-web
  46 passed/28 failed (все — tests/test_flowctl.py) + 274 errors.
  Фон идентичен чистому HEAD (сверка прогоном на stash HEAD: те же
  test_flowctl 28; web-фейлы HEAD — надмножество, +1 flaky r5_crop),
  причина — env-ограничение среды: нет стенда 127.0.0.1:8080 (api/web
  suite против живого стека — контур 5.5). Новых падений волна D не дает.

Эскалации: нет. Заметка (не эскалация): регистрация social_router — одна
строка в main.py (зона 1.2), выполнено по sdd §2 («включает роутеры»);
`openspec validate video-hosting --strict` — green (16 failed --all —
чужие change-пакеты, вне зоны).
