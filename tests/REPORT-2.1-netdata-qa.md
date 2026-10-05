# REPORT 2.1 — QA: регресс + новые проверки пакета add-netdata-monitoring

- **Задача:** tasks.md 2.1 [M] (QA-этап C; FR-76, FR-77, FR-78; NFR-19; design §0 п.4)
- **Correlation:** 97a81b928f744dd6a76cdce801802699 (deleg-97a81b928f744dd6)
- **Дерево:** worktree `/home/openclaw/ekotov-wiki-worktrees/qa-21-netdata`, ветка `add-netdata-monitoring`, HEAD `2e6efb5` (включает 1.2 `aeaa447`, 1.3 `3fd7af7`, 1.4 `7abdf12`, мокапы `eac40de`, решение Заказчика `4099f86`/decision `2026-10-05-netdata-mockup-approval`)
- **Зона записи:** tests/**, e2e/**, test-model/bugs/*; чекбокс `[x] 2.1` НЕ ставится (закрывает ПМ после приемки)
- **Дата:** 2026-10-05

## 0. Вердикт (кратко)

| Часть задачи | Статус |
|---|---|
| (а) web-сьют: сайдбар owner/PE/аноним + регресс профиля/разделов | **GREEN** — новые 6 проверок + полный web-сьют |
| (б) api-сьют: полный регресс ядра (паритет) | **GREEN** — 201p/9s/2xf, красное только 413-лимит стенда (не продукт, см. §4) |
| (в) стенд-проверки nginx-маршрутизации /netdata | **GREEN (live)** — стенд поднят БЕЗ docker: nginx-контур + netdata-стаб; все 10 смоук-сценариев 1.3 подтверждены независимо + композ-статика |
| (г) design_validator: пункт «Мониторинг» vs мокап 1.1а | **APPROVE** (см. §5) — вердикт также записан в `test-model/reviews/add-netdata-monitoring/review-001-design.md` |
| Дефекты | 1 новый minor (BUG-007, avatars-404 — вне скопа пакета); продукта пакета дефектов НЕ найдено |

**Итог сьютов (финальные прогоны на QA-стенде):**

| Сьют | Результат | Время |
|---|---|---|
| `tests/web` (incl. 6 новых netdata-проверок `tests/web/test_qa21_netdata_sidebar_ui.py`) | **171 passed, 1 skipped, 0 failed** | 6:34 |
| `tests/api` + `tests/test_walkthrough_probe.py` | **201 passed, 9 skipped, 2 xfailed** (+2 failed = 413-лимит стенда, §4) | 2:04 |
| `services/search/tests` | **12 passed** | 1.4s |
| `pytest tests/` (единая коллекция) | BUG-006 (известный, вне скопа) — обход: покаталоговый запуск | — |
| Смоук-матрица deploy.sh (раздел 6) + smoke_static | **все чеки green** (§3.3) | — |

## 1. Стенд (часть «в»)

Docker недоступен под текущим пользователем (`docker ps` → permission denied;
то же ограничение, что в R6/REPORT-regress-21 §5), поэтому compose-стенд
`deploy/compose.test.yaml` не поднимался. Вместо него — **живой nginx-контур
локальной машины** (nginx 1.24.0 есть в системе), повторяющий топологию
`services/frontend/nginx/ekotov-wiki.conf`:

```
nginx :18443 (HTTP; локации netdata/search/app — ДОСЛОВНО из прод-конфига)
  = /netdata, = /netdata/, ^~ /netdata/ + auth_basic (htpasswd qa-monitoring/qa-test-only,
    сгенерирован локально openssl passwd -apr1 — метод compose.test.yaml шапки)
  → netdata-стаб :19999 (python-httpserver: дашборд-маркер + /api/v1/info JSON)
  = /api/search, ^~ /api/search/, = /api/suggestions, ^~ /api/suggestions/ → search :8378 (uvicorn)
  остальное → app :8080 (uvicorn, backend/) — свежая БД + seed owner/wife + migrate_r4
```

Отличия от образа (зафиксированы, на семантику netdata-проверок не влияют):
TLS не терминировался (HTTP), upstream-имена `netdata:19999`/`search:8378` в
include'ах заменены на `127.0.0.1:19999`/`127.0.0.1:8378` (docker-DNS
`resolver 127.0.0.11` директива сохранена в конфиге — без docker она просто
не вызывается; анти-stale-DNS семантика «переменная+resolver» независимо
проверена задачей 1.3 на песочнице с resolver'ом), `client_max_body_size`
оставлен прод-значением 2m (см. §4 про 413).

Стенд погашен после прогонов (nginx -s quit, uvicorn ×2, стаб).

### 3.1. Смоук netdata-маршрутизации (живой nginx) — 10/10 GREEN

| # | Сценарий | Факт |
|---|---|---|
| 1 | `/netdata` без кредов | **301** Location=`…/netdata/` ✓ |
| 2 | `/netdata/` без кредов | **401**, `WWW-Authenticate: Basic realm="Monitoring"` ✓ (до прокси: стаб запросов не получил) |
| 3 | `/netdata/` с `qa-monitoring:qa-test-only` | **200**, дашборд-маркер в теле ✓ |
| 4 | неверный пароль | **401** (+ запись `password mismatch` в error_log) ✓ |
| 5 | `/netdataX` (посторонний) | в netdata-локацию НЕ попал (app → 302 /login, как корневой путь без сессии) ✓ |
| 6 | `/netdata/static/img/logo.svg` с кредами | **200**, префикс вырезан (стаб получил `/static/...`) ✓ |
| 7 | `/netdata/api/v1/info?after=5` с кредами | **200** JSON, args сохранены ✓ |
| 8 | security-заголовки netdata-ответа | nosniff / DENY / same-origin / HSTS — все 4 ✓ (netdata-headers.inc работает) |
| 9 | регресс app через nginx | `/api/health` 200, `/login` 200 ✓ |
| 10 | регресс search-семейства | `/api/suggestions` 401+`X-Service: search` без сессии / 200 с сессией; `/api/search?q=x` 200 ✓ |

**Ограничение (честно):** upstream — стаб, а не реальный контейнер
netdata/netdata. Поведение ПРОКСИ (subpath-вырезание, auth до прокси, args,
заголовки) доказано; поведение самого Netdata за прокси (сборка его
реального дашборда браузером, метрики host/containers из /proc//sys//docker.sock)
— НЕ проверялось и не может быть проверено без docker. Это переносится на
стенд-матрицу 2.2 (живой подъем) — так же, как зафиксировано в REPORT-1.3.

### 3.2. compose-паритет (статически, docker недоступен)

`yaml.safe_load` обоих compose + сверка сервисов `netdata` прод vs тест:
image / mem_limit 256m / порты не публикуются (None в обоих) / proc+sys ro /
docker.sock ro / healthcheck / restart / logging json-file 10m×3 — **полный
паритет**. htpasswd-маунты: прод `/etc/nginx/netdata.htpasswd:…:ro`,
тест `./netdata.htpasswd.test:…:ro` (ожидаемое различие, design §2/§6).

### 3.3. Смоук-матрица deploy.sh (ключевые чеки раздела 6)

`/api/health` 200; `/login` 200; `/static/css/app.css` 200; `/api/search?q=smoke`
401 + `X-Service: search` (коридор 200/401/422 — PASS); `/robots.txt` 200;
netdata-чеки 301/401/200 (п.3.1); `scripts/smoke_static.py` — 14 статик-ресурсов,
проблем 0.

## 2. Часть (а): web-сьют

Новый артефакт: `tests/web/test_qa21_netdata_sidebar_ui.py` (6 тестов, pytest
tests/web, маркеры web+must):

| Тест | Проверка | Результат |
|---|---|---|
| `test_monitoring_link_visible_for_owner` | owner: пункт в sidebar-footer, href=/netdata/, target=_blank, rel=noopener, текст | GREEN |
| `test_monitoring_link_hidden_for_product_engineer` | wife (Product engineer): профиль заполнен, пункта НЕТ | GREEN |
| `test_monitoring_link_hidden_for_anonymous` | аноним: /board → /login, пункта НЕТ | GREEN |
| `test_profile_block_and_sections_regression` | регресс: профиль O/owner, разделы Доска/Поиск/Wiki, ровно один пункт, позиция «Мониторинг»→«Настройки»→«Выйти»→профиль | GREEN |
| `test_monitoring_link_present_on_all_functional_pages` | пункт на /board, /search, /wiki, /settings | GREEN |
| `test_design_validator_markup_and_tokens` | часть (г): структура + токены + состояния (§5) | GREEN |

Регресс-прогоны: полный `tests/web` — **171 passed / 1 skipped / 0 failed**
(дважды: до и после финальной конфигурации стенда). Первые (отладочные)
прогоны на временном стенде давали массовую красну (см. §6, уроки) — после
восстановления search-сервиса и env-параметров стенда сьют полностью green;
продуктовых регрессий от 1.4 нет.

## 3. Часть (б): api-сьют (паритет ядра)

`tests/api` + probe: **201 passed / 9 skipped / 2 xfailed / 2 failed**.
Состав skip — ожидаемый (tests/README.md): 2 manual-рестарт НФТ, bcrypt-НФТ,
6 web_ui-skip. Оба xfailed — известный BUG-003 (empty-name body format).
`services/search/tests` — 12 passed. Ядро netdata-коммитами не затронуто
(диффы aeaa447/3fd7af7/7abdf12: compose, nginx-конфиг, static/js+css) —
паритет подтвержден фактическим прогоном.

**2 failed — НЕ продуктовые** (артефакт стенда): `test_avatar_r4::
test_reject_oversize` и `test_gaps_r5::test_size_limit_boundary_…` ожидают от
app 422/200 для тел ~2МБ+, но nginx стенда отвечает **413** раньше app
(`client_max_body_size 2m` — прод-значение образа; «±1 байт» тестового тела
выходит за лимит при multipart-обрамлении). Контрольный прогон мимо nginx
(прямо в app :8080): тот же oversize-запрос → **422 `{"error":"file too
large"}`** — валидация app работает. Это известное расхождение /tmp-стенда
(зафиксировано в REPORT-regress-21 §3 как сознательное; здесь стенда с
поднятым лимитом НЕ делал — не маскировал различие). В эталонной R6-прогонке
эти тесты green на стенде с лимитом 64m. Предложение (не требую): учитывать
в README-матрице, что 2 avatar-boundary-теста требуют стенд с `client_max_
body_size ≥ 64m` или запуск мимо nginx.

## 5. Часть (г): design_validator — вердикт **APPROVE**

Полное ревью: `test-model/reviews/add-netdata-monitoring/review-001-design.md`.
Сверка фактического вида (живой DOM через Playwright на QA-стенде) против
утвержденного мокапа `design/netdata-sidebar-mockup.html` (eac40de; решение
Заказчика 4099f86: без промпт-карточки, без маркера внешней ссылки,
иконка-пульс утверждена):

| Критерий | Мокап | Факт (продукт) | Вердикт |
|---|---|---|---|
| Разметка | `a.nav-item.nav-item-monitoring` в sidebar-footer перед «Настройки» | идентично (insertBefore settingsLink) | ✓ |
| Иконка | inline-SVG polyline `2.5 12 7 12 10 5.5 14 18.5 17 12 21.5 12`, stroke=currentColor, 16px | посимвольно; computed 16×16px | ✓ |
| Маркер ext-hint | присутствует в .html мокапа (остаток варианта ДО решения) | **отсутствует** (count=0) — по решению Заказчика, не по устаревшей строке мокапа | ✓ (решение > артефакт; N-1 review-001-1.4 уже фиксирует) |
| Токены | color `--p-paper-050` #faf7f2; active `--color-accent` #a8432c; focus-ring rgba(168,67,44,.35) | computed-style: rgb(250,247,242) / rgb(168,67,44) / ring из `--focus-ring` — значения из `:root`, не хардкод | ✓ |
| hover | вуаль rgba(255,253,249,0.08), opacity 1 | совпадает (единственное «сырое» значение — унаследованный каркас `.nav-item`, N-2 review-001-1.4, не чинить) | ✓ |
| focus-visible | inset focus-ring | box-shadow inset rgba(168,67,44,0.35) при клавиатурном фокусе | ✓ |
| active | фон `--color-accent` | rgb(168,67,44) при mouse.down | ✓ |
| Роль-гейт | пункт только owner (Product manager) | только после /api/auth/me с role=PM; PE/аноним — нет (тесты §2) | ✓ |
| href/target/rel | `/netdata/`, `_blank`, `noopener` | идентично | ✓ |

**APPROVE.** Замечаний, требующих return, нет. Примечание для ПМ: в мокапе
design/** остался ext-hint-остаток (N-1 review-001-1.4) — предлагается
косметическая правка ui_designer'ом при случае, не блокер.

## 6. Уроки стенда (для следующих QA-сессий; E16)

1. **web-стенд требует ТРИ процесса + env**: без search-сервиса на :8378
   («отрезанные» search-маршруты, f0fe4ec) все tag-combobox/подсказки-тесты
   красные (401/404 от app); без `EKOTOV_WIKI_AVATARS_DIR` — tooltip-тесты
   error; search-сервису нужен `EKOTOV_WIKI_DB_PATH` (не `DB_PATH`).
2. **Ошибка «cannot import requests» в heredoc** — системный python, не venv;
   всегда `/home/openclaw/venvs/wiki/bin/python`.
3. BUG-006 (pytest_plugins в не-корневом conftest) подтвержден на этом дереве
   тоже — покаталоговый запуск работает.

## 7. Баг-репорты и артефакты

| Артефакт | Что |
|---|---|
| `tests/web/test_qa21_netdata_sidebar_ui.py` | 6 новых проверок (a)+(г) |
| `test-model/reviews/add-netdata-monitoring/review-001-design.md` | design_validator-ревью, вердикт APPROVE |
| `test-model/bugs/BUG-007-avatars-404-no-fallback-broken-image.md` | minor, вне скопа пакета (avatars), рекомендация в бэклог |
| `deploy/netdata.htpasswd.test` | сгенерирован заново на этой машине (qa-monitoring/qa-test-only, apr1); git-ignored (check-ignore подтвержден) — артефакт стенда, в git не попадает |
| Логи / конфиг стенда | `/tmp/nginx-qa21/` (вне репо) |

## 8. Эскалации / на усмотрение ПМ

1. **E-2.1a:** часть «в» выполнена на live-nginx + netdata-СТАБЕ (без docker).
   Proxy-семантика доказана; реальный контейнер netdata (сборка дашборда,
   метрики host/containers, RAM-замер NFR-19) — только на 2.2 (живой подъем)
   или при docker-доступе. Не выдумываю результат: стаб помечен явно.
2. **E-2.1b:** 2 api-падения — 413 nginx стенда (прод-лимит 2m) на avatar-
   boundary-тестах; предложение по матрице запуска — §4.
3. **E-2.1c:** мокап design/netdata-sidebar-mockup.html содержит ext-hint-остаток
   (противоречит утвержденному решению 4099f86) — косметика ui_designer (N-1).
4. **E-2.1d:** BUG-007 (avatars 404 без fallback) — minor, вне скопа пакета,
   кандидат в бэклог.

Чекбокс 2.1 в tasks.md не отмечен — приемка и закрытие за ПМ.
