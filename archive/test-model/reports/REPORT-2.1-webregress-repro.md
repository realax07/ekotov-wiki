# REPORT-2.1: верификация полного web-регресса на чистом стенде (закрытие ограничения review-003)

**Дата:** 2026-10-06. **Исполнение:** ПМ (докат после обрыва сессии 20261006_112348, kill фоновых процессов при gateway_turn_interrupt).
**Корреляция:** ограничение `code-reviews/add-gallery-service/review-003-2.1.md` §4/§6 — «полный web-регресс 170p не воспроизведен точно (163p/7f — не-галерейные сьюты на остаточных данных БД стенда)».

## Результат

**170 passed, 1 skipped, 0 failed — 515s (0:08:35)** — точное воспроизведение REPORT-чисел
(`tests/REPORT-2.1-gallery-qa.md` §5: «полный web-регресс 170p/1s/0f»; 1 skip — docker-зависимый
инфра-тест, кейс TC-GAL-120/121 семейства).

- HEAD: b26abc7 (ветка add-gallery-service), код не менялся.
- Стенд: /tmp/qa21-verify — app :8080 + search :8378 + images :8379 + nginx :18443
  (паритет services/frontend/nginx/ekotov-wiki.conf 1.4 без docker), БД пересоздана
  начисто (схема → migrate_gallery → migrate_r4 → seed owner/wife + 3 категории).
- Лог: /tmp/qa21-verify/webregress-final.log.

## Причина расхождения прогона ревьюера (163p/7f)

Не «остаточные данные БД» как таковые, а **нарушение env-протокола прогона**. Тест-сьют
требует ОДНОВРЕМЕННО (все три читаются хуками conftest/тестов):

- `EKOTOV_WIKI_BASE_URL=http://127.0.0.1:18443` — внешний полный стенд (иначе
  автостенд без search/images → пают combobox/tag-hints/search-builder, 37f);
- `EKOTOV_WIKI_DB_PATH=<стендовая БД>` — без него хук очистки QAGAL-хвостов
  (`_cleanup`) молча не работает (`if not DB_PATH: return`) → хвосты предыдущих
  тестов искажают порядок листания лайтбокса (фейл TC-GAL-116) и счетчики;
- `EKOTOV_WIKI_IMAGES_DIR` — путь файлов галереи для hygiene-хуков;
- `EKOTOV_WIKI_AVATARS_DIR` — без него 15 ERROR teardown/test_r5_crop +
  каскадный фейл avatar-preview (непочищенный аватар).

Прогон ревьюера шел против оставленного стенда с остаточной БД (5 категорий прошлых
прогонов) — все 7 фейлов в сьютах, чувствительных к данным. На чистой БД с полным
env-протоколом фейлов нет.

## Попутно исправлено (окружение стенда, не продукт)

- `/tmp/qa21-verify/stand_up.sh`: cwd сабсервисов был `services/search/app`
  (uvicorn: `ModuleNotFoundError: app`) → `services/search` и `services/images`.
- `/tmp/qa21-verify/db_reset.sh`: пересоздание БД без рестарта сервисов
  (секреты через env; app на время пересоздания гасится — держит открытый sqlite).

## Вывод

Ограничение review-003 снято: REPORT-числа подтверждены независимым прогоном ПМ.
Изменений продукта не требуется. Урок для QA-протокола: env-набор веб-прогона
(BASE_URL + DB_PATH + IMAGES_DIR + AVATARS_DIR) фиксировать в tests/README как
обязательный «полный стенд»-профиль — без DB_PATH очистка молча деградирует.
