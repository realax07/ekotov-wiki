# Code review — chore/p26-games, review-003: фикс БАГ-5 (страницы игр 404 через прокси)

Роль: code_reviewer (Флоу 5, компактное). Предмет: фикс-дифф 3b4a799..760e2f7 —
закрытие моего БАГ-5 из review-002: regex-локейшн
`~ ^/games/(munchkin|vice|poker|tanks|durak)(/|$)` → games-proxy-game.inc (прокси
БЕЗ вырезания префикса), `/games/api/` и `/games/previews/` вынесены в отдельные
`^~`-локейшны на срезе, strip-локейшн `/games/` переведен из `^~` в обычный
префикс; RUNBOOK §9.3.

Reviewer-Delegation: p26-games review-3 (flow 5)

Метод: НЕ только чтение диффа — конфиг-анализ порядка локейшнов + полный e2e на
ОДНОРАЗОВОМ стенде (метод №2, RUNBOOK §9.2): отдельная docker-сеть wt-p26-r3-net,
nginx:alpine с ПОЛНЫМ ekotov-wiki.conf ветки + все *.inc + self-signed серт ‖
node:26-alpine с реальным /home/openclaw/game-portal (команда §9.2 дословно,
включая -e HOST=0.0.0.0; алиас game-portal). Живой прод-стек и контейнер
game-portal НЕ тронуты. Стенд погашен после проверки.

---

## 1. Порядок локейшнов nginx — КОРРЕКТЕН, regex выигрывает у /games/

Семантика nginx: точный `=` > самый длинный prefix, и если он с `^~` — regex НЕ
проверяются > иначе regex ПО ПОРЯДКУ КОНФИГА, первый совпавший > иначе
запомненный обычный prefix. По конфигу 760e2f7:

- `/games/vice/` → самый длинный prefix `/games/` БЕЗ `^~` → проверяются regex →
  `^/games/(vice)(/|$)` совпал → games-proxy-game.inc, префикс уходит как есть →
  хаб роутит нативно. e2e: **200** (при старом `^~` бэкенд получал `/vice/` → 404 —
  именно это и было БАГ-5; регресс закрыт).
- `/games/api/games`, `/games/previews/vice.png` → самые длинные prefix С `^~` →
  regex не проверяются → срез префикса. e2e: 200/200, JSON /api/games содержит
  все 5 переписанных `"/games/previews/<id>.png"`, PNG 86 011 байт.
- `/games/`, `/games/app.js` (корень/статика хаба) → regex НЕ совпал (граница
  `/`|`$` после id) → strip-локейшн. e2e: 200, href→`/games/style.css`,
  fetch→`/games/api/games` переписаны, т.е. regex не перебил корень хаба.
- `= /games` → 301 (вне изменений).
- Других regex-локейшнов в server-блоке НЕТ (проверено grep по conf) — «первый
  совпавший regex» всегда games-овый; конфликтов порядка внутри server нет.

Побочные выборы проверены: `/games/vice` (без слэша) → regex по `$` → хаб 302 на
`/games/vice/` сквозь прокси (Location относительный — ок); `/gameszzz` → в
games-локейшны НЕ попал (на стенде 502 от отсутствующего app:8377 — граница
сегмента держит); `/games/nonexistent/` → strip-локейшн → честный 404 хаба
«Не найдено».

## 2. Дублированные директивы в двух inc — НЕ КОНФЛИКТУЮТ

- `sub_filter*` — только в games-proxy.inc; включается в 3 локейшна (api,
  previews, `/games/`), ни один не включает games-proxy-game.inc — в одном
  блоке sub_filter не задваивается (nginx -t это бы отловил).
- `set $upstream_games` — в обоих inc, но локейшны дизъюнктны; resolver один,
  на уровне server (127.0.0.11 valid=10s) — оба proxy_pass с переменной
  переразрешаются. `nginx -t`: «syntax is ok / test is successful» (единственный
  warn — listen http2, строка 22 — ПРЕДСЕСТВУЮЩИЙ, вне диффа).
- games-headers.inc включен в каждую games-локейшн (перекрытие наследования
  add_header — корректный прием, паритет search/weather/videos). На живых
  заголовках страницы игры: X-Service: games, X-Frame-Options: SAMEORIGIN
  (iframe-плеер хаба разрешен), nosniff.

## 3. e2e (одноразовый стенд, выборочно из 5 дев-проверок) — ВСЁ ЗЕЛЕНЫМ

- 5/5 страниц `/games/<id>/` → **200** (id в regex сверены с server.mjs games[] —
  munchkin/vice/poker/tanks/durak, 1:1, регистр `~` совпадает с точным find хаба).
- Относительные ассеты игр через ТОТ ЖЕ regex-локейшн → 200: style.css и
  app.js/game.js всех 5 игр (tanks ships game.js — проверен он; все src из
  index.html игр прогнаны, 200).
- Хаб 200 + переписанные href/fetch; /games/api/games 200 + 5 переписанных
  previews; превью 86 KB; /games/nonexistent/ → 404 хаба.

## 4. RUNBOOK §9.3 — СИНХРОНЕН

Дословно соответствует конфигу: `= /games` 301; `^~ /games/api/`,
`^~ /games/previews/` и `/games/` (обычный префикс) со срезом; regex с 5 id БЕЗ
среза; «новая игра = добавить id в regex»; §9.2 (docker run, HOST=0.0.0.0,
ro-маунт) воспроизведен на стенде дословно.

---

## Неблокирующее

1. **Комментарий games-proxy-game.inc неточен**: «страницы игр используют
   относительные пути (абсолютных href="/…" нет)» — в Durak/index.html есть
   `<a class="brand" href="/">`. Эффект: клик по лого Дурака внутри iframe хаба
   уводит iframe на корень вики, а не на /games/. UX-шероховатость самого хаба
   (external), не диффа; фикс-направление при желании: точечный sub_filter в
   games-proxy-game.inc либо ничего (хаб внешний). Поправить формулировку
   комментария при следующем касании файла.
2. Задвоение `X-Content-Type-Options: nosniff` на /games/*: хаб шлет свой
   nosniff + games-headers.inc добавляет второй. Безвредно, косметика (до диффа
   поведение то же для strip-части).
3. Процессное (повтор из review-002): фикс-коммит под [chore] трогает
   deploy/RUNBOOK.md — финальный PR ветки обязан быть [ops]-маркирован
   (check_deploy_gate), иначе pm_bounds_check.

## Вердикт: **APPROVE**

БАГ-5 закрыт ровно по фикс-направлению review-002 (вариант «два локейшена»):
regex-локейшн без среза выигрывает у обычного префикса, срезанные семейства
(api/previews) защищены `^~`, корень хаба не задет. Порядок локейшнов верен,
дубликатов-конфликтов нет, RUNBOOK синхронен, e2e на одноразовом стенде зеленый.

Проверено: `nginx -t` (nginx:alpine) — ok; полный e2e nginx+node с реальным хабом:
5/5 игр 200 без среза префикса, ассеты игр 200, хаб-статика с переписанными
путями 200, /games/api/games с 5 переписанными image, превью 200 (86 011 B),
302-пассруч no-slash, /games/nonexistent/ 404 хаба, /gameszzz мимо хаба,
заголовки (SAMEORIGIN) на живом ответе.
