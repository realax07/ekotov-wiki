# TC-migr-005 — NFR-8: автосверка до/после миграции подтверждает ноль потерь

- **CHK:** CHK-101
- **Change:** add-r2-categories-settings
- **Источник:** categories: Миграция без потери данных (NFR-8) / Scenario: Автосверка до/после подтверждает ноль потерь
- **Тип:** НФТ | **Приоритет:** Must
- **Среда/предусловия:** тестовая БД приложения (env `EKOTOV_WIKI_DB_PATH`); доступ к `sqlite3` CLI; скрипт миграции из пакета (sdd §5); выполнен вход owner (куки `owner_cookies.txt`); **seed справочника в этом кейсе НЕ выполняется** — справочник должен быть пуст ДО миграции (миграция сама создает категории из значений задач). Кейс — разовая проверка внедрения (метка `candidate-archive`, impact §3 п.2).
- **Сценарий:**
  - **GIVEN** до миграции зафиксирован снимок: список уникальных непустых значений category и категории каждой задачи
  - **WHEN** миграция выполнена и запущена автоматическая сверка
  - **THEN** сверка показывает: (а) каждая задача имеет то же значение категории, что в снимке; (б) COUNT категорий справочника = COUNT уникальных непустых значений снимка; расхождений нет; бонус: все fast-задачи после миграции priority=high
- **Шаги:**
  1. Снимок «до» (до миграции): `sqlite3 "$EKOTOV_WIKI_DB_PATH"` — (а) `SELECT id, category FROM tasks;` → файл `snapshot_tasks_before.csv`; (б) `SELECT COUNT(DISTINCT category) FROM tasks WHERE category IS NOT NULL AND category != '';` → число `U`; (в) `SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high';` → число `F_bad_before`.
  2. Запустить миграцию.
  3. Сверка «после»: (а) повторить `SELECT id, category FROM tasks;` → файл `snapshot_tasks_after.csv`; построчное сравнение двух CSV скриптом (Python); (б) `SELECT COUNT(*) FROM categories;` → число `C_total`; (в) `SELECT COUNT(*) FROM tasks WHERE is_fast = 1 AND priority != 'high';` → `F_bad_after`.
  4. Дополнительно: `GET /api/categories` → количество записей сверить с `C_total`.
- **Ожидаемый результат:** (а) CSV идентичны построчно — ни одна задача не потеряла и не изменила категорию (0 расхождений); (б) `C_total == U + C_seed` (категорий справочника ровно столько, сколько уникальных непустых значений «до», плюс категории, существовавшие до миграции — их число зафиксировать в снимке отдельной строкой; итоговое равенство обязательно); (в) `F_bad_before` — любое, `F_bad_after == 0` (все fast-задачи приведены к priority=high — бонус sdd §5). В протоколе — числа и вывод скрипта сверки.
- **Тестовые данные:** снимки `snapshot_tasks_before.csv` / `snapshot_tasks_after.csv`; счетчики `U`, `C_total`, `F_bad_before/after`.
