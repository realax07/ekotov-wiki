# TC-wiki-421 — Смок стенда: compose.test, health, логин обоих, CRUD-маршрут wiki, контракт 9 путей

- **Change:** add-wiki
- **Источник:** wiki (ADDED): все Requirements (сквозной смок) + tasks 4.4(б); design §2–§6; CHK-wiki-2, CHK-wiki-9, CHK-wiki-21, CHK-wiki-24, CHK-wiki-26, CHK-wiki-27
- **Тип:** НФТ, средовое (стенд из ветки) | **Приоритет:** Must
- **Предусловия:** `docker compose -f deploy/compose.test.yaml -p wiki-test up -d --build` из ветки (порт 8443, TLS self-signed); seed: app.db → seed owner/wife → migrate_r4 → migrate_gallery → migrate_wiki (явные шаги — замечание RUNBOOK)
- **Шаги:**
  1. Контейнеры стека healthy ×6 (app, nginx, search, images, backup, netdata); /api/health → 200 ok.
  2. images-сервис жив: GET /api/images под сессией → 200; search: /api/search → 200.
  3. Логин owner (200, Product manager) и wife (200, Product engineer).
  4. /wiki без сессии → 302 /login; под owner и wife → 200 каркас.
  5. Смок-маршрут: POST /api/wiki/pages → 201; PUT → 200 + versions 1→2; GET /api/wiki/search?q=поиска → 200 (snippet, match_offset); POST revert/1 → new_version_id=3, контент v1, versions [3,2,1].
  6. Паритет: wife GET/PUT 200; аноним → 401.
  7. Контракт: 9 REST-путей /api/wiki/* — все отвечают ожидаемыми кодами, лишних/недостающих нет.
- **Ожидаемый результат:** стек из ветки поднимается и обслуживает wiki-функционал end-to-end: оба пользователя работают, гейты 401/302 работают, контракт полон. Факт прогона 4.4: green — 16/16 PASS (REPORT-4.4-smoke.md §(б)).
- **Автотест:** автотеста нет — прогон 4.4 REPORT-4.4 §(б) (скриптовый смок: curl + cookie-сессии + браузер; отдельного pytest-сьюта смока нет)
- **Статус:** **approved** (QA 4.4 прогнан: смок 16/16 PASS)
