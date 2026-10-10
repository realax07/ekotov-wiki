# TC-wiki-405 — Миграция pages/page_versions: накатка, идемпотентность, репетиция на прод-снапшоте (NFR-32)

- **Change:** add-wiki
- **Источник:** wiki (ADDED): Requirement «Миграция таблиц pages и page_versions» (NFR-32, паттерн app.migrate_gallery) — Scenario «Повторный запуск миграции», «Репетиция на копии прод-БД»; design §1–§2; CHK-wiki-31
- **Тип:** НФТ, инфраструктура | **Приоритет:** Must
- **Предусловия:** копия прод-БД (REPORT-4.4 §(а): снапшот тома ekotov-wiki-par_wiki-data через sqlite3.Connection.backup() из ro-контейнера, прод не тронут); интерпретатор venv wiki; cwd=backend
- **Шаги:**
  1. `DB_PATH=<копия> SECRET_KEY=<test> python -m app.migrate_wiki` (прогон 1) → «Создано таблиц: 2: ['pages','page_versions']», «индексов: 3», «Сверка: ОК», exit 0.
  2. Повторный запуск (прогон 2) → «Создано таблиц: 0 (no-op)», сверка ОК, exit 0 — идемпотентность.
  3. Независимая сверка: PRAGMA integrity_check = ok; foreign_key_check пуст; счетчики 13 старых таблиц до/после — 0 расхождений; PRAGMA table_info — колонки/NOT NULL/DEFAULT по design §1; FK (parent RESTRICT, page_versions CASCADE, author→users); 3 индекса на местах.
- **Ожидаемый результат:** миграция идемпотентна (повтор — no-op), сверка зеленая, боевые данные не тронуты; боевая накатка на прод разрешена после зеленой репетиции. Факт прогона 4.4: green (репетиция на ФАКТИЧЕСКОМ прод-снапшоте — ОК ×2, integrity ok, 0 расхождений; REPORT-4.4-smoke.md §(а)).
- **Автотест:** автотеста нет — прогон 4.4 REPORT-4.4 §(а) (скрипт `python -m app.migrate_wiki` на прод-снапшоте, 2 прогона + PRAGMA-сверка)
- **Статус:** **approved** (QA 4.4 прогнан: репетиция ОК ×2, сверка зеленая)
