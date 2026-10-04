# Ревью задачи 1.3 — пакет add-microservices-full (nginx-маршрутизация search-семейства)

Reviewer-Delegation: deleg_3eca7b18 <!-- платформенный id реестра async_delegations (state=completed); вписан ПМ из реестра после сдачи отчета ревьюера -->

- Дата: 2026-10-04
- Ревьюируемый коммит: `4902e3f` — «feat(frontend): nginx-маршрутизация /api/search*, /api/suggestions → search:8378»
- Задача: 1.3 (tasks.md, ЭТАП B; design §1 — топология, §4 — контрактный CI-gate + деградационный тест; FR-65 паритет)
- Автор: dev-делегация (не я — независимое ревью)
- Метод: собственные команды (git show, сверка с contracts/openapi-search.json, deploy/nginx-ekotov-wiki-10443.conf, полный прогон контрактного гейта в venv проекта, flow_check, docker-стенд недоступен — см. «Что НЕ проверено»). Отчет исполнителя не принимался на веру: каждое заявление проверено по диффу/коду.

---

## 1. Зона диффа

`git show 4902e3f --stat`: 6 файлов — `services/frontend/Dockerfile`, `services/frontend/README.md`, `services/frontend/nginx/ekotov-wiki.conf`, `services/frontend/nginx/search-headers.inc` (new), `services/frontend/nginx/search-proxy.inc` (new), `tests/api/test_openapi_search_service.py`. Выхода за зону задачи (services/frontend/** + tests/api/) **нет**. Чекбокс tasks.md 1.3 не снимался — корректно (снимает ПМ/flow после ревью).

## 2. nginx-матчи — соответствие контракту (проверено по коду)

Контракт `contracts/openapi-search.json` — ровно 4 пути: `/api/search` (GET), `/api/search/advanced` (POST), `/api/suggestions` (GET), `/api/suggestions/users` (GET) — подтверждено разбором JSON.

| Путь контракта | Локация, которая его поймает | ✓ |
|---|---|---|
| `/api/search` | `location = /api/search` (точный) | ✓ |
| `/api/search/advanced` | `location ^~ /api/search/` | ✓ |
| `/api/suggestions` | `location = /api/suggestions` | ✓ |
| `/api/suggestions/users` | `location ^~ /api/suggestions/` | ✓ |

- **Не ловят лишнего:** `/api/searching`, `/api/searchx` не матчатся ни одной из 4 локаций: `=` — только точный URI; `^~`-префиксы заканчиваются на `/`, а nginx матчит префикс посимвольно — `/api/searching` не начинается с `/api/search/` (и не равен `/api/search`). Комментарий в конфиге о «границе сегмента» по сути верен (точный префикс `/api/search` без слэша поймал бы `/api/searching`, поэтому выбран суффикс-слэш — решение корректное, формулировка неточна, см. minor 1.3-c). Посторонние пути уходят в `location /` → app. Проверено разбором алгоритма выбора локации nginx; живой прогон — на стенде исполнителя (см. §7).
- **`^~` vs regex:** единственные regex-локации в конфиге (и в базе deploy/nginx-ekotov-wiki-10443.conf) — отсутствуют; есть только `=` (robots.txt), префиксные `/static/`, `/avatars/`, `/`. `^~` здесь ничего не отключает сегодня, но страхует от будущих regex — соответствует замыслу ТЗ. Существующие префиксные `/static/` и др. длиннее/не пересекаются — конфликтов нет. Приоритеты nginx соблюдены (точный > `^~`-префикс).
- **URI не переписывается** (`proxy_pass` без URI-части при переменной) — search-роутеры видят свои пути, контракт прозрачен (design §3 п.2). ✓

## 3. 503-деградация (design §4)

Цепочка: `proxy_next_upstream error timeout` (в search-proxy.inc, действует на все 4 search-локации) → `proxy_intercept_errors on` → `error_page 502 503 504 = @search_down` → `@search_down`: `return 503` + JSON-тело + `Retry-After: 5` + security-заголовки.

- **Механика на single-upstream корректна и не избыточна:** `proxy_next_upstream` для единственного апстрима не дает повторной попытки, но зато переводит «ошибку соединения/таймаут» в немедленную обработку error-фазы — без него nginx по умолчанию с `proxy_next_upstream off`... фактически дефолт (`error timeout`) и так есть; включение явно — безвредно и документирует намерение (исполнитель отчитался о 503 за ~11мс ×5/5 на стенде; механика согласуется с конфигом).
- **proxy_intercept_errors обязателен и присутствует:** без него 502 от nginx ушел бы клиенту как есть, error_page не сработал бы на 502/504. ✓
- **Побочный эффект перехвата (оценено, не блокирует):** `proxy_intercept_errors on` перехватывает и **легитимные ответы самого search** с кодами 502/503/504, заменяя их тело на `@search_down`. Сверено с контрактом: в `contracts/openapi-search.json` declare только 200/422 — сервис по контракту не обещает 502/503/504, и FastAPI/uvicorn с healthcheck'ом не генерирует их в штатных путях. Решение осознанно соответствует design §4 («503 от nginx, не 502-залипание»). Если в будущем search начнет отвечать собственным 503-телом (rate-limit и т.п.), тело клиента будет nginx'овским — зафиксировано как minor 1.3-b.
- **Retry-After** — `add_header ... always` в `@search_down` — будет на 503-ответах. ✓
- **@search_down `internal`** — снаружи напрямую недоступна. ✓

## 4. X-Service и security-заголовки (add_header inheritance)

Правило nginx: любое `add_header` внутри location отменяет наследование add_header с уровня server. Проверка:

- `search-headers.inc` повторяет **все 4** server-овых security-заголовка NFR-7 (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, HSTS) + добавляет `X-Service: search`, все с `always`. Включен во все 4 search-локации **и в @search_down** — security-заголовки есть и на деградационном 503. ✓
- Включение search-proxy.inc (содержит proxy_set_header, error_page и пр., но **ни одного add_header**) не ломает наследование — по конфигу в search-локациях add_header только из search-headers.inc. ✓
- App-локации (location /) своих add_header не имеют — server-овые security-заголовки наследуются, поведение до 1.3 не изменилось. X-Service на app-ответах не заведен — соответствует решению (маркер только у search). ✓
- Нюанс: `location /static/` и `/avatars/` имеют собственные `add_header Cache-Control` — наследование security-заголовков там отменялось **и до этого коммита** (предсуществующее поведение add-containerization 1.2, не регрессия этого диффа; вне зоны, не замечание к 1.3).

## 5. Dockerfile и include-пути

- `COPY services/frontend/nginx/ekotov-wiki.conf services/frontend/nginx/search-proxy.inc services/frontend/nginx/search-headers.inc /etc/nginx/conf.d/` — все три файла копируются **в один каталог** `/etc/nginx/conf.d/`; include в конфиге — `include /etc/nginx/conf.d/search-proxy.inc` / `search-headers.inc` — пути совпадают байт-в-байт. ✓
- Нюанс: `.inc`-файлы теперь лежат в `/etc/nginx/conf.d/` рядом с `ekotov-wiki.conf`. Базовый `nginx.conf` образа делает `include /etc/nginx/conf.d/*.conf;` — `.inc` не имеет расширения `.conf`, двойного включения верхним http-контекстом не будет. Проверено по базовому образу nginxinc/nginx-unprivileged (стандартный include glob `*.conf`). ✓

## 6. Тесты (гейт)

- `test_nginx_routes_search_family`:
  - **Skip-условие не маскирует отказ:** skip только при `200 + нет X-Service` (стенд со старым образом frontend без маршрутизации — легитимный случай до перевыпуска образа). Если маршрутизация сломана (502/503 на живом search, 404, X-Service ≠ search, X-Service заехал на /api/board) — тест **падает**, не скипается. Граница проведена корректно: skip детектирует отсутствие функции, fail — дефект функции.
  - Покрывает все 4 пути семейства + негативную проверку `/api/board` без X-Service. TC-openapi-203 в docstring — flow_check rule 6 green (прогон `python3 scripts/flow_check.py .` → OK).
  - **Прогон локально (venv, без стенда):** `1 passed, 1 xfailed` для двух контрактных тестов + `ERROR` на setup нового теста из-за предсуществующей session-fixture `base_url` (conftest требует живой стенд; ENV от завершенной сессии stale). Это **не дефект диффа** — fixture-модель общая для всего api-сьюта; на стенде с сервисом тест проходит (отчет: PASSED). Но см. minor 1.3-a: на стенде **без** маршрутизации тест дает skip, а не pass — заявленная в commit message формулировка «PASSED (skip на стендах без маршрутизации)» точна.
- `test_core_has_no_search_routes`: `xfail(strict=True)` сохранен, reason теперь корректно ссылается на 1.5. strict-маскировки нет: если main.py перестанет импортировать роутеры раньше 1.5, тест XPASS и **уронит** сьют — правильная защита. ✓
- `test_search_contract_is_frozen` не тронут (строгое множество путей).

## 7. Верификация стенда (что подтверждено, что нет)

**Подтверждено мной:** синтаксис конфига консистентен (все include-пути существуют в репо, все директивы допустимы в своих контекстах — location/include/set/add_header/proxy_*), матчи сверены с алгоритмом nginx, контракт сверен с локациями, тест прочитан и прогнан файлово.

**Не проверено (стенд недоступен ревьюеру — docker socket permission denied в этой сессии):** живые смоук 16/16, деградация 503 ×5/5 за ~11мс, recovery через ttl резолвера, nginx -t в контейнере. Эти заявления исполнителя согласуются с конфигом и тестом, но **фактически не перепроверены независимым прогоном** — принято с этой оговоркой; деградационный сценарий design §4 также покрыт задачей 2.2 (стенд-матрица), где это будет прожито еще раз.

---

## Находки

| # | Severity | Файл:место | Замечание → рекомендация |
|---|---|---|---|
| 1.3-a | minor | tests/api/test_openapi_search_service.py:68 | Skip-условие различает стенды только по факту «200 + нет X-Service». Стенд **со включенной маршрутизацией, но упавшим search** (503 от @search_down с `X-Service: search`!) не попадет в skip и честно упадет на `assert 200` — это хорошо; но 503-ветка деградации тестом не покрыта вообще (design §4 требует деградационный тест, он заявлен на стенд 2.2). Рекомендация: параметризовать негативную ветку (stop-search → 503 + Retry-After) отдельным тестом с docker-скипом, либо явно записать в tasks.md 2.2, что §4-деградационный тест закрывается там. |
| 1.3-b | minor | services/frontend/nginx/search-proxy.inc (proxy_intercept_errors on) | Перехват распространяется и на легитимные 502/503/504 от самого search — их тело будет заменено на `@search_down` без различения «search недоступен» vs «search отказал». Контракт 502/503/504 не декларирует (200/422 only), поэтому сегодня поведение корректно; зафиксировать в комментарии конфига, чтобы будущий 503-ответ сервиса не был «проглочен» молча. |
| 1.3-c | minor | services/frontend/nginx/ekotov-wiki.conf:94–96 | Комментарий «префикс-локация /api/search без слэша НЕ съела бы /api/searchX… nginx матчит префикс по границе сегмента» — формулировка вводит в заблуждение: nginx префиксный матч идет по символам, и `location /api/search` (без `=`) **действительно** поймал бы `/api/searching`. Верное обоснование выбора `^~ /api/search/` — ровно наоборот («суффикс-слэш исключает чужие URI»). Поправить текст комментария. |
| 1.3-d | nit | services/frontend/Dockerfile | Три файла в одном COPY — при изменении любого инвалидируется слой; микроню для образа на 3 файла, не требует действия. |

Blocker/major: **нет**.

---

## Трассировка tasks.md 1.3 ↔ реализация

- «location /api/search, /api/suggestions → proxy_pass http://search:8378 (resolver 127.0.0.11 + переменная)» — выполнено (+ разбиение на точный/префиксный, обоснованное контрактом). ✓
- «остальные → app» — `location /` не тронут; /static/, /avatars/, robots.txt без изменений (регрессии по конфигу нет). ✓
- «X-Service заголовок» — search-headers.inc, только на search-ответах (+ негативная проверка в тесте). ✓
- «503-деградация (proxy_next_upstream + error_page)» — search-proxy.inc + @search_down. ✓
- «Проверка на стенде: поиск через 8443 = 200, X-Service: search; app без маршрутов поиска» — отчет исполнителя согласуется с тестом гейта (TC-openapi-203); независимо не перепроверено (стенд), см. §7.
- design §1 (resolver/переменная для search, старт без search-контейнера) — соответствует; design §4 (заголовок сервиса + деградация в конфиге) — соответствует, деградационный автотест отложен на 2.2 (см. 1.3-a).

## Что НЕ проверено (честно)

1. Живой стенд: docker API в сессии ревьюера недоступен (permission denied) — смоук, деградация, recovery, nginx -t не перепроверены независимым прогоном; согласованность с конфигом подтверждена чтением.
2. search-api регресс «26 passed, 7 skipped» — не воспроизводился (требует стенда с сервисом; скип-кейсы с EKOTOV_WIKI_DB_PATH соответствуют описанию conftest).
3. Сборка образа (build) не повторялась.

---

## Сводка находок

- blocker: 0; major: 0
- minor: 3 (1.3-a — деградационная ветка без автотеста/явной записи в 2.2; 1.3-b — перехват легитимных 502/503/504 от search не зафиксирован комментарием; 1.3-c — вводящий в заблуждение комментарий о префиксном матче)
- nit: 1 (1.3-d)

## Вердикт: approve

Матчи точны и полны против замороженного контракта (проверено разбором обоих артефактов), деградационная цепочка механически корректна, security-заголовки и X-Service разведены с учетом наследования add_header (включая @search_down), Dockerfile-пути совпадают с include, skip-условие гейт-теста не маскирует отказ, strict-xfail сохранен, дифф строго в зоне. Замечания minor не блокируют: 1.3-a адресуется задачей 2.2 (просьба — зафиксировать явно), 1.3-b/1.3-c — одна строка комментария в следующий инфра-коммит (1.4).

## Мета

- Reviewer-Delegation: deleg_UNKNOWN — платформенный delegation_id в постановке задачи отсутствует; **мета требует ручной правки ПМ** (строка выше + парсер flow_check читает `deleg[-_]…`).
- Для J10: имя файла содержит task-id 1.3; при необходимости дополнить `code-reviews/add-microservices-full/review-mapping.json`.
