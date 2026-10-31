# Code review — chore/p26-games, review-002: пере-ревью 4 фиксов (f6c472c)

Роль: code_reviewer (Флоу 5, компактное). Предмет: точечная проверка фикс-диффа
850a56c..f6c472c против 4 блокеров моего review-001 (git-история ветки; сам
review-001.md удален фикс-коммитом — см. неблокирующее). Фиксы: games-proxy.inc
(sub_filter_types +text/javascript +application/json, правило `"/previews/`),
games-headers.inc (SAMEORIGIN), RUNBOOK §9.2 (-e HOST=0.0.0.0).

Reviewer-Delegation: deleg_4d9ead1e

Метод: НЕ только чтение диффа — полный e2e на одноразовом стенде: docker-сеть
(nginx:alpine с полным ekotov-wiki.conf + все *.inc + self-signed серт ‖ node:26-alpine
с РЕАЛЬНЫМ /home/openclaw/game-portal, команда из RUNBOOK §9.2 ДОСЛОВНО, включая
-e HOST=0.0.0.0, алиас game-portal). curl через :443-прокси хаба, /api/games,
превью, страницу игры; grep переписанных тел. Плюс `nginx -t` (nginx:alpine) —
«syntax is ok / test is successful» (единственный warn — listen http2, строка 22,
ПРЕДСЕСТВУЮЩИЙ, вне диффа). Стенд погашен.

---

## Проверка закрытия 4 блокеров — ВСЕ ЗАКРЫТЫ РОВНО ПО РЕКОМЕНДАЦИИ

1. **БАГ-1 (text/javascript) — ЗАКРЫТ.** `sub_filter_types application/javascript
   text/javascript application/json;`. e2e: /games/app.js отдается, внутри
   `fetch('/games/api/games')` (переписан) — /games/api/games 200 с телом каталога.
2. **БАГ-2 (JSON-превью) — ЗАКРЫТ.** Правило `'/previews/' → '"/games/previews/'`
   с кавычкой-якорем. e2e: в JSON /api/games все 5 image переписаны в
   `/games/previews/<id>.png`, `url:"/games/<id>/"` НЕ задет (якорь точен);
   /games/previews/vice.png через прокси — 200, 86 KB PNG. Ложных срабатываний нет:
   единственный `"/previews/` в HTML хаба — `src="/previews/vice.png` (index.html:7),
   и он корректно ловится правилом `src="/` в тот же результат — двойного
   префикса нет (sub_filter не ресканирует заменный текст); до правило `src="/`
   или кавычка-якорь дают идентичный `/games/previews/vice.png`.
3. **БАГ-3 (SAMEORIGIN) — ЗАКРЫТ.** games-headers.inc: X-Frame-Options: SAMEORIGIN
   (подтверждено заголовками живого ответа прокси), iframe-плеер хаба same-origin
   теперь разрешен.
4. **БАГ-4 (RUNBOOK -e HOST=0.0.0.0) — ЗАКРЫТ.** Команда §9.2 воспроизведена
   дословно на стенде — server.mjs поднялся на 0.0.0.0, nginx-прокси получил
   ответы (без флага было бы ECONNREFUSED/502 — до флага стенд именно 502 и давал).

Новых дыр в самих фиксах не внесено: расширение sub_filter_types ловит только
типы ответов хаба (text/javascript = его .js, application/json = его /api/games);
лишних переписываний в телах не найдено (проверены hub.html, app.js, api.json).

---

## НОВЫЙ БЛОКЕР: БАГ-5 (обнаружен e2e, НЕ внесен фикс-диффом — мой пропуск review-001)

**Страницы игр /games/<id>/ через прокси — 404, игры не открываются.**
server.mjs роутит `/games/<id>/` НАТИВНО (regex `^\/games\/([^/]+)(\/.*)?$`) —
проверено напрямую: бэкенд `/games/vice/` → 200, `/vice/` → 404. Но games-proxy.inc
ВЫРЕЗАЕТ префикс (`rewrite ^/games(?<gpath>/.*)$ $gpath break;`) → бэкенд получает
`/vice/` → «Не найдено» 404. app.js открывает игру `$('#game-frame').src=game.url`,
где game.url из JSON = `/games/vice/` (в JSON не переписывается — и не должен) →
iframe получает 404. e2e: `curl /games/vice/` через прокси = 404 «Не найдено».

Мой review-001 ошибочно зафиксировал «url:"/games/<id>/" — через префикс работает
нативно»: нативный роут хаба работает БЕЗ прокси (standalone :8080), а через прокси
префикс срезается ДО бэкенда. Ошибка моя, честно фиксирую.

Дефект в строках e9f7893 (фикс-дифф их не трогал), но блокирует главный сценарий
P26 — запуск игр из хаба. Фикс-направление (на выбор дева, nginx-only): не
вырезать префикс для игровых страниц, сохранив вырезание для корня/API/статики/
превью хаба (map $gpath: `^/api/`, `^/previews/`, статика корня хаба → $gpath;
игровые пути → `/games$gpath`), либо зеркально — два локейшена (`^~ /games/api/`
со срезанным префиксом как сейчас + `^~ /games/` с сохранением). Хардкод id игр
в map не предлагать (хаб external, список игр растет). Прогон e2e-стенда из
метода выше — обязателен при перепроверке (именно он ловит этот класс).

## Неблокирующее

- Фикс-коммит трогает deploy/RUNBOOK.md под [chore]: на уровне КОММИТА pm_bounds_check
  красится (J26 — deploy-дифф только под [ops]); финальный PR ветки обязан быть
  [ops]-маркирован, иначе check_deploy_gate. Процессное, не дифф.
- review-001.md удален фикс-коммитом: аудит-след RETURN-вердикта остается только в
  git-истории (достижим, но непривычно — в остальных пакетах review-файлы живут в
  ветке). Дальше review-файлы в фикс-коммитах не удалять.

## Вердикт: **RETURN** — 1 новый блокер (БАГ-5, nginx-only фикс в games-proxy.inc /
ekotov-wiki.conf); 4 исходных блокера подтверждены закрытыми на живом e2e-стенде.

Проверено: реальный `nginx -t`; полный e2e-стенд nginx+node с реальным хабом
(команда RUNBOOK §9.2 дословно): хаб 200, /games/api/games 200 с переписанными
image, превью 200 (86 KB), app.js с переписанным fetch, SAMEORIGIN на живых
заголовках, /games/vice/ 404 (БАГ-5), бэкенд-пробы /vice/ 404 vs /games/vice/ 200.
