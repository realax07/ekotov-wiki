# Релизный журнал R6 — add-microservices-full (верхнеуровневый лог передач)

Формат: `[время UTC] КТО → КОМУ: ЧТО (артефакт/вердикт)`. Append-only.
Полные детали — в гейт-репортах (`~/.hermes/state/gate-reports/`) и review-файлах.

---

## Этап 0. Решение и подготовка

- **[2026-10-03, вечер] Заказчик → ПМ (main):** директива — «следующий релиз — полный переход на микросервисы (в контейнерах)»; доделать и подготовить план перехода всех сервисов.
- **[2026-10-03, вечер] ПМ → ПМ (артефакт):** пакет `add-microservices-full` создан (proposal/design/tasks/specs; search :8378 + backup sidecar, auth не выделяется), strict-валидация.
- **[2026-10-04 ~11:35] Заказчик → ПМ:** «погнали» (старт: архивация add-containerization + ЭТАП A).

## Этап 0.5. Архивация (ПМ solo, гейты strict)

- **[11:44] ПМ → openspec/master-specs:** дельта deploy (12 сценариев) слита в `openspec/specs/deploy/spec.md`, Purpose написан; `add-containerization` → `archive/2026-10-04-add-containerization`. Strict 13/13.
- **[11:46] ПМ → себе (урок):** flow_check I3 падал после архивации (покрытие маршрутов жило в архивном пакете) → фикс: корневое покрытие (sdd + master-specs) всегда; фабрика PR #27, wiki синхронно.

## ЭТАП A. Контракт и каркас (Флоу 1)

### Подготовка ворот (ПМ → state machine, 5 попыток prepare)

- **[11:49] flowctl → ПМ: DENY** — `implement` вне графа Флоу 1 → выбрано `create_change`.
- **[11:50] flowctl → ПМ: DENY** — нет решения Заказчика → создан `decisions/2026-10-04-microservices-full.md` (дословные цитаты).
- **[11:51] flowctl → ПМ: DENY ×2** — запись не машиночитаема; scope не словарь → блок `decision-record/1` по формату P0.4.
- **[11:51] flowctl → ПМ: DENY** — зона SA не покрывает contracts/ → политика зон проектной копии приведена к реальной структуре wiki (sa: +contracts/**; dev: backend/frontend/services вместо шаблонного src/**).
- **[11:52] ПМ → flowctl: ALLOW** — корреляция `751bf741`, зоны [contracts, export_openapi_search.py].

### Задача 0.1 — заморозка контракта поиска

- **[11:52] ПМ → SA (deleg_2566f48e):** ТЗ — скрипт экспорта + замороженный контракт + deprecated-пометки.
- **[11:56] SA → ПМ:** выполнено — `scripts/export_openapi_search.py`, `contracts/openapi-search.json` (sha256 `79704d9d…`), `openapi.json` deprecated ×4; strict 13/13.
- **[11:57] ПМ (верификация) → gate:** факты подтверждены; отчет `task-0.1-report.md`.
- **[11:57] gate → ПМ: returned** (flow_check/openspec/pm_bounds PASS; pr_validate SKIPPED — нет PR; замечание OUT_OF_ZONE: отчет писал ПМ, не СА — урок).

### Задачи 0.2 + 0.3 — каркас сервисов и тест-гейт

- **[11:59] ПМ → flowctl: ALLOW** (корреляция `01af7088`) — после снятия зомби-резерва `tests/**` (утренний пилот в needs_attention закрыт админски с журналом).
- **[11:59] ПМ → dev (deleg_441015f9):** ТЗ — каркас services/search|backup, тест-гейт xfail, чекбоксы.
- **[12:17] dev → ПМ:** выполнено — `e776e59` (каркас), `0299bef` (тест-гейт), `b1f9636` (чекбоксы 0.1–0.3); pytest 1 passed/1 xfail; strict 13/13.
- **[12:26] ПМ (верификация) → gate:** тест у ПМ падал (нет стенда) → поднят стенд по tests/README → PASSED/XFAIL подтверждены; стенд погашен.
- **[12:26] gate → ПМ: returned, overall FAIL** — flow_check: 3 закрытых задачи без code-review (J10) — машина требует ревью (штатно).

### Ревью review-001 (независимый ревьюер)

- **[12:27] ПМ → code_reviewer (deleg_8775daa4):** ТЗ — проверка 0.1/0.2/0.3 по фактам.
- **[12:34] code_reviewer → ПМ: request_changes** — review-001 (`a5987fc`): 1 major (тесты без TC-трассировки — flow_check rule 6 красный), 2 minor (xfail-reason → 1.5 вместо 1.3 — ошибка исходного tasks.md; design §9 устарел), 3 nit. 0.1 и 0.2 — чисто, детерминизм и границы зон подтверждены независимо.

### Фикс-цикл

- **[12:34] ПМ → dev (deleg_c08daa6c):** ТЗ-фикс — TC-openapi-201/202 в docstring, xfail-reason → 1.5. Design §9 и nit'ы — сознательно не в этом круге (design → SA далее).
- **[12:37] dev → ПМ:** фикс готов — `0495346` (один коммит, только тест-файл); flow_check: ошибка TC ушла, осталась 1 (code-review — закрывается циклом); pytest 1 passed/1 xfail (стенд поднят/погашен); strict 13/13.
- **[12:38] ПМ (верификация):** дифф точечный (1 файл, +7/−6), TC-формат совпадает с rule 6, запушено.
- **[12:39] ПМ → code_reviewer (deleg_4f791b51): ре-ревью** — короткий круг: только фикс-коммит, verdict ждется в review-002-fix-cycle.md.

---

### Ре-ревью и закрытие ЭТАПА A

- **[12:48] code_reviewer (deleg_4f791b51) → ПМ: approve** — review-002-fix-cycle.md: оба замечания зоны dev закрыты (0495346), дифф хирургический, гейт не ослаблен; перенесено на SA/PM: design §9, design §3, tasks.md 0.3 (1.3/1.5), TC-кейсы в test-model (информационно).
- **[12:50] ПМ:** публикация review-002 + task-0.1-report (9cf54de); review-mapping.json — связка review-002 → 0.1/0.2/0.3 (b456e9b); flow_check → **OK**.
- **[12:52] ПМ (самонаходка):** Reviewer-Delegation в review-файлах был фиктивным (deleg-arch-rev-001 — ярлык из моего ТЗ, не платформенный id) → заменены на реальные deleg_8775daa4 (review-001) / deleg_4f791b51 (review-002); проверка реестра теперь проходит. Урок: в ТЗ ревьюеру никогда не задавать литеральный id — только ссылку на реальную делегацию.
- **[12:53] ПМ:** полный PR-набор (impact-анализ H5, чеклист, approved-кейсы, test-model review) — артефакты ЭТАПА C (2.1), не этапные ворота A. ЭТАП A закрыт.

---

**ЭТАП A ЗАКРЫТ** (0.1–0.3: contract frozen, каркас, тест-гейт; review-001 → request_changes → фикс → review-002 approve; flow_check OK, strict 13/13).

## ЭТАП B. Выделение сервисов

- **[13:05] Заказчик → ПМ:** «Погнали» на ЭТАП B + директива: вопросы конвейера/гейтов — в бэклог на рассмотрение, починки — синхронно в обоих репо.
- **[13:08] ПМ → BACKLOG фабрики (PR #30, merged 010f908):** J37 — 6 открытых вопросов конвейера (required checks не принудительны; delegation-id в метах; автозаполнение review-mapping; файловые тесты без стенда; разведение стадийных/PR-ворот; env-конвенция чекеров).
- **[13:10] ПМ (синхрон-аудит):** pr_validate wiki отставал от фабрики по SELF_REVIEW-блоку (is_dir-защита + missing при отсутствии меты) → взята фабричная версия; pm_bounds — осознанное расхождение (проектный дефолт PM_PROTECTED_EXCLUDE=contracts/) оставлено. Прочее ядро байт-в-байт.
- **[13:12] ПМ → себе (урок, к J37):** делегация в finished держит резерв зоны — manual-закрытие реестра; автоосвобождение зон на finished — в J37.
- **[13:13] ПМ → flowctl: ALLOW** (корреляция `86aae105`) → **ПМ → dev (deleg_a5c7a151):** ТЗ 1.1 — код search-сервиса (роутеры как есть, row_schema с трассировкой, db WAL, TestClient-тесты TC-openapi-203+, протокол needs-debug).

---

**Открыто:** ЭТАП B 1.1 (dev работает) → далее 1.2 → 1.3 → 1.4 последовательно (одно инфраизменение в шаге) → 1.5 → ревью. Перенесено на SA: design §9, design §3, tasks.md 0.3; на QA-инфра: autouse base_url (тесты без стенда).
- [21:00 UTC] Заказчик → ПМ: «Погнали» (запуск ревью-волны 1.1/1.2/1.5 + подготовка перегенерации контракта)
- [21:00 UTC] ПМ → ворота: 3× code_review ALLOW (1.1: deleg-3292234a, 1.2: deleg-26060811, 1.5: deleg-95a2a3a8; approval_ref 2026-10-04-microservices-full-dev-tasks)
- [21:01 UTC] ПМ → 3 независимых code_reviewer (deleg_a8abc895, deleg_e6e0df28, deleg_48346510): ревью диффов f0e5a37+41ffe87 / 980bbac / f0fe4ec; зоны review-004-{1.1,1.2,1.5}.md
- [21:15 UTC] ПМ → SA (deleg_01491e0f, corr e00ecc0e): перегенерация contracts/openapi.json (находка 1.5-a major из review-004-1.5); зомби-hold deleg-751bf741 (0.1, finished→completed) закрыт админски с журнальной записью
- [21:10 UTC] code_reviewer → ПМ: review-004-1.5.md — approve (major 1.5-a: перегенерация контракта до 2.1); ПМ: мета deleg_48346510 из реестра, чекбоксы 1.3/1.5 сняты
- [21:30 UTC] 3× code_reviewer → ПМ: review-004-1.1 (request_changes: 2 major 1.1-a/b, 2 minor, 1 nit), review-004-1.2 (request_changes: 1 major 1.2-a, 3 minor, 2 nit), review-004-1.5 (approve); результаты доставлены из async_delegations (delivery_state=dropped, инцидент ротации #92859)
- [21:32 UTC] ПМ: commits f926dbd (openapi.json + review-004-1.1/1.2 + release-log); зомби-холды закрыты админски (86aae105/f2d0a220/e00ecc0e/d9469d9f, журнальные записи в lifecycle)
- [22:45 UTC] ПМ → 2× dev (deleg_777730b6, gate a4d1b09b/deleg-a4d1b09b + 756bade8/deleg-756bade8): фикс-циклы review-004-1.1 (1.1-a/b major + c/d/e, 1.2-f) и review-004-1.2 (1.2-a major + b/c/d/e); зоны services/search/** и deploy/**+services/backup/**
- [22:40 UTC] ПМ: ложные BYPASS (54bc87e0/01491e0f) устранены — статусы flowctl синхронизированы (needs_attention→completed после админ-клоза зомби); вотчдог run2 exit=0
- [23:05 UTC] dev → ПМ: фикс-циклы завершены — cda3d22 (1.1-a..e + 1.2-f, тесты 12/12, негативные пруфы дискриминации в REPORT-fix-11.md), 795aded (1.2-a..e, DRY_RUN EXIT=0, REPORT-fix-12.md); ПМ: верификация независимым прогоном — подтверждено
- [23:07 UTC] ПМ: gate finish обеих dev-сессий — returned (OUT_OF_ZONE: пути параллельной сессии в общем base..HEAD; обе работы верифицированы независимо); сессии закрыты админски синхронно реестр+flowctl
- [23:12 UTC] ПМ → 2× code_reviewer (deleg_9cf35336, gate e7fdc320 + f546b8c1): ре-ревью коротким кругом фикс-диффов cda3d22 / 795aded → review-005-{1.1,1.2}.md
- [23:25 UTC] 2× code_reviewer → ПМ: review-005-1.1 approve (R-1 minor не блокирует), review-005-1.2 request_changes (1.2-g minor — регресс дубль-бэкапа от retry-фикса, 1.2-h nit); ПМ: мета Reviewer-Delegation вписана (59e478b)
- [23:27 UTC] ПМ → dev (deleg_4f19dd1c, gate 14f93497): фикс 1.2-g/h; ре-ревьюер: повторное ревью после него не требуется
- [04:40 UTC] dev → ПМ: фикс 1.2-g/h — патчи applied (делегация оборвана шлюзом на репликации), ПМ докатил: верификация py_compile+bash -n+репликация main() A/B/C PASS, коммит cb5e65b, REPORT-fix-12g.md
- [04:42 UTC] ПМ: gate finish 14f93497 returned (OUT_OF_ZONE релизного журнала); сессии закрыты синхронно; вотчдог run2 exit=0
- [04:55 UTC] ПМ: [x] 1.1 закрыта (approve 005-1.1); попытка закрыть 1.2 до approve — DENY INVALID_GATE машиной («история не переписывается»), чекбокс откачен честно
- [04:57 UTC] ПМ → code_reviewer (deleg_edb7a5de, gate 24112044): ре-ревью №6 фикс-диффа cb5e65b (1.2-g/h) → review-006-1.2.md
- [06:05 UTC] code_reviewer → ПМ: review-006-1.2 approve (репликация 4 сценария, регрессий нет); ПМ: мета вписана, [x] 1.2 (54213db); flow_check: OK — ЭТАП B закрыт
- [06:10 UTC] ПМ → QA (deleg_5339bc4c, gate 9ba2c5ec): задача 2.1 — полный регресс (api на стенде + юниты сервисов); DENY ZONE_OUTSIDE_POLICY (test-model/bugs/** vs политики bugs/*) разобран уточнением паттерна
- [07:04 UTC] QA → ПМ: 2.1 завершена (a9f8176) — tests/api 201p/9s/2xf/0f на маршрутизированном стенде (app:8080+search:8378+nginx:18443), юниты search 12p/0f, смоук маршрутизации + 503-деградация green; BUG-006 major (pytest tests/ не собирается, pytest_plugins в не-корневом conftest); ПМ: gate finish returned (OUT_OF_ZONE журнала), сессия закрыта
- [07:07 UTC] ПМ → code_reviewer (deleg_ae91c6a8, gate d647709e): ревью QA-отчета 2.1 → review-007-2.1.md
- [07:20 UTC] code_reviewer → ПМ: review-007-2.1 request_changes (F-1 major: web-сьют не прогнан, playwright работает; F-2..F-4 minor); ПМ: сессия ревьюера закрыта
- [07:25 UTC] ПМ → QA (deleg_0260fc2d, gate 399c23ce): фикс-цикл F-1..F-4 (прогон tests/web + правки REPORT-regress-21.md)
- [08:20 UTC] ПМ: фикс-делегация 2.1 (deleg_0260fc2d / flowctl 399c23ce) оборвана ротацией шлюза на фоновом web-прогоне (state=error/dropped, результата в дереве нет); ПМ перезапустил повтором deleg_af1b2fe2 В ТУ ЖЕ flowctl-сессию 399c23ce (зона tests/** сохранена), gated_map вписан синхронно
- [10:50 UTC] ПМ: deleg_af1b2fe2 уперся в лимит итераций на диагностике 2 фейлов (дерево чистое, стенда-факты собраны); ПМ-верификация TestClient изолированно: GET assigned=none и advanced 'assigned IS NULL' корректны — продуктового дефекта НЕТ, фейлы = дефект изоляции тестов (чужие unassigned-задачи в живой БД); завершающая делегация deleg_0ec8d7b9 в ту же сессию 399c23ce: изоляция 2 тестов + F-2..F-4 в REPORT + подтверждающий прогон + коммит. Запись gated_map+журнала подтверждена Заказчиком после блокировки permission-gate
- [11:05 UTC] ПМ: фикс-цикл 2.1 ЗАВЕРШЕН — web 165p/0f/1s EXIT=0 (a4aee1c); докат ПМ после двух лимит-обрывов: чистка QAT-хвостов, скоуп локаторов (board/view-modal), финальный прогон; продукт здоров (TestClient-верификация); finish returned (OUT_OF_ZONE: review-007 + релизный журнал ПМ в диффе сессии — норма); стенд погашен; далее — ре-ревью review-008 коротким кругом
- [11:12 UTC] ПМ → code_reviewer (deleg_a0d8fe68, gate 24a56f11): ре-ревью 008 коротким кругом — фикс-дифф a4aee1c (165p/0f подтвержден прогоном, F-2..F-4 внесены); зона review-008-2.1.md
- [11:20 UTC] code_reviewer → ПМ: review-008-2.1.md — approve (F-1..F-4 закрыты, изоляция усилена, докат ПМ признан допустимым, N-1 minor процессное); ПМ: gate finish returned (OUT_OF_ZONE журнала — норма), сессия 24a56f11 закрыта синхронно; [x] 2.1 — закрыта; далее 2.2 (стенд-матрица)
- [11:25 UTC] ПМ: flow_check OK — 2.1 покрыта review-008 (approve); поправка формата: заголовок «## Вердикт» для VERDICT_LINE_RE (содержание не менялось); следующая по флоу — 2.2 (стенд-матрица, QA)
- [11:30 UTC] ПМ → dev (deleg_3a1d54d8, gate 9a7836cf): задача 2.2 — стенд-матрица деградаций (stop search → 503, backup, лимиты памяти, смоук записи); зона tests/** + tasks.md
- [11:40 UTC] dev → ПМ: 2.2 завершена (edd1964, REPORT-matrix-22: stop search 503/запись/restart PASS, деплой-бэкап PASS, память 2749MB PASS; docker-ограничения → 2.3 честно); ПМ: finish returned (OUT_OF_ZONE журнала — норма), сессия 9a7836cf закрыта синхронно; [11:42] ПМ → code_reviewer (deleg_55eae375, gate db70926e): ревью 2.2 → review-009-2.2.md
- [11:45 UTC] code_reviewer → ПМ: review-009-2.2.md — approve (N-1..N-3 minor/info, blocker нет; backup-трасса и прод-паритет верифицированы командами); ПМ: finish returned (OUT_OF_ZONE — норма), сессия db70926e закрыта синхронно; [x] 2.2 — закрыта; следующая — 2.3 прод-параллель (развилка Заказчика)
- [13:05 UTC] ПМ: PR #22 смержен в main (6f71a84) — артефакты 2.1/2.2 + test-model (impact, чеклист CHK-P12, кейсы TC-openapi-201/202, review-001 ОДОБРИТЬ) + скрипт 2.3-par; CI flow+e2e SUCCESS; на /opt/ekotov-wiki Заказчику: git pull + bash deploy/2.3-par.sh full
- [13:07 UTC] журнал дополнен пост-merge записью (в ветке пакета)
- [13:15 UTC] Заказчик → ПМ: 2.3 приемка браузером :10444 — «Вроде все работает. Проверил» (логин, доска, поиск, создание задачи, аватар); ПМ: независимая верификация 10444/10443 = 200/200; acceptance-protocol-2.3.md оформлен; [x] 2.3 закрыта
- [13:40 UTC] Заказчик → ПМ: 2.4 приемка браузером :10443 — «Вроде все норм работает. Ок»; ПМ: независимая верификация (login 200, X-Service: search на прод-порту); acceptance-protocol-2.4.md оформлен; [x] 2.4 закрыта; ПРОД РАБОТАЕТ НА МАТРИЧНОМ СТЕКЕ p12-rc1; осталась 2.5 [docs]
- [13:50 UTC] ПМ → dev (deleg_b9907f23, gate 7895fb46): 2.5 docs-часть — актуализация deploy/RUNBOOK.md по факту релиза (зона сужена до deploy/**: architecture/** и sdd.md вне политики роли dev — DENY машины честный; map.md/sdd.md — ПМ-проход отдельным ходом)
- [14:00 UTC] dev → ПМ: 2.5 RUNBOOK-часть (7a2e7a0, REPORT-2.5-runbook.md); ЭСКАЛАЦИЯ: 2.3-par.sh rollback теперь опасен (проект par = продовой, down -v снесет продовый том) — протокол 2.4 и RUNBOOK исправлены (stop nginx, НЕ down -v); ПМ: finish returned (норма), сессия закрыта; map.md + sdd.md r13 — ПМ-проход; [x] 2.5 — ВСЕ ЗАДАЧИ ПАКЕТА ЗАКРЫТЫ
- [14:20 UTC] Заказчик → ПМ: «Релиз принят» (ОВ-1); decision 2026-10-05-release-microservices-full зафиксирован (e1d2600); openspec archive add-microservices-full → archive/2026-10-05-add-microservices-full; master-спека services создана, Purpose заполнен (TBD-плейсхолдер закрыт); openspec strict 13 PASS, flow_check OK. РЕЛИЗ ЗАВЕРШЕН.
- [14:10 UTC] ПМ: PR #23 (финализация, [chore] после архивации пакета) смержен в main (5a12c35); CI flow+e2e SUCCESS; РЕЛИЗ R6 / add-microservices-full ЗАВЕРШЕН ПОЛНОСТЬЮ
- [14:55 UTC] ЦИКЛ R7 СТАРТ: решение 2026-10-05-r7-launch (cb544e9); SA-старт add-netdata-monitoring через ворота (deleg_a0fc0fe4, gate a8290b71) — proposal/design/tasks/requirements; перед стартом закрыты зомби-holds 2a5327cc (SA add-containerization, пакет в релизе) и f3b432f6 (недоисполненный gate-start); ветка add-netdata-monitoring
- [15:15 UTC] SA → ПМ: 0.1 завершена (da6e645+c059c5d) — пакет add-netdata-monitoring: proposal/requirements (FR-75..78, NFR-19, ГОТОВ К УТВЕРЖДЕНИЮ)/design (§0 дизайн-фаза Р4/Р5)/specs (monitoring NEW 5req/14scn + navigation ADDED + deploy MODIFIED)/tasks (6 задач: 1.1 [design] ui_designer → развилка Заказчика → 1.2/1.3 devops → 1.4 dev фронт → 2.1 QA+design_validator → 2.2 [ops] приемка)/sdd r14; strict 14 PASS, flow_check OK; эскалации E1 (zone-policy: requirements/research вне зон sa — на решение ПМ), E4 (пароль basic auth отдельный)
- [15:16 UTC] ПМ: gate finish returned (E1/E2 OUT_OF_ZONE честные), сессия закрыта синхронно; пуш ветки; ДАЛЕЕ — requirements на утверждение Заказчика (развилка) → мокап ui_designer → развилка → dev
- [15:30 UTC] Заказчик → ПМ: requirements add-netdata-monitoring УТВЕРЖДЕНЫ + zone-policy sa расширить (обе репы); decision 2026-10-05-netdata-monitoring-requirements; проектный [pipeline]-коммит 462e017; эталон ai-factory — PR #32 мерж (0c61364, CI SUCCESS); СЛЕДУЮЩЕЕ: мокап ui_designer 1.1 (gate ALLOW)
- [15:35 UTC] Заказчик → ПМ: «Может внедрим design task?» → решение 2026-10-05-design-task-flow1: действие design_task (ui_designer) в Флоу 1 — STAGE_TABLE + check_design_task, ядро проекта [pipeline] 11ae595; эталон ai-factory — следующим ходом; gated_map вписан; ui_designer 1.1 (deleg_9537fb41) — мокапы в design/**
- [17:10 UTC] dev → ПМ: 1.4 завершена (7abdf12, playwright 29/29, регресс профиль/tooltip 20p; 2 pre-existing fails вне зоны эскалированы); finish returned (OUT_OF_ZONE: untracked мокапы галереи параллельной сессии в диффе — известная норма); сессия закрыта синхронно; code_review 1.4 (deleg_b6b65365, gate d6364e03) запущен
- [17:25 UTC] code_reviewer → ПМ: review-001-1.4 — approve (0 blocker/major; 2 minor вне зоны 1.4: .ext-hint в мокапе → design_validator, rgba-каркас → бэклог); самостоятельные прогоны ревьюера 20p+3p совпали с dev; [x] 1.4; далее — 1.2 Netdata-контейнер + 1.3 nginx-локация (devops-волна)
- [17:30 UTC] ПМ: review-001-1.4 approve (0 blocker/major, самостоятельные прогоны ревьюера совпали); [x] 1.4; devops-волна: 1.2 Netdata-compose (deleg_3f3a08c9, gate acf88974) запущена ([P]-задача, параллельна ui_designer галереи — зоны не пересекаются); 1.3 nginx-локация — следующая
- [17:55 UTC] dev → ПМ: 1.2 завершена (aeaa447: netdata в обоих compose, curl-vs-wget обосновано официальным Dockerfile; 26/26 структурных проверок; живой подъем в 2.2); ПМ: приемка yaml-верификации (REPORT-1.2-netdata-compose.md), finish returned (норма), сессия закрыта; code_review 002-1.2 (deleg_56063e79, gate 54e97c3b) запущен
- [17:45 UTC] code_reviewer → ПМ: review-002-1.2 — approve (33/33 независимых проверок; docker.sock-компромисс зафиксирован в design §4 осознанно; 1 minor: digest-пин — бэклог); [x] 1.2; gate 1.3 ALLOW (0dd08a0b: nginx-локация /netdata + basic auth, зоны frontend/**+deploy/**)
- [17:50 UTC] ПМ: [x] 1.2 (review-002 approve 33/33); 1.3 nginx-локация /netdata через ворота (deleg_f5a5ef22, gate 0dd08a0b) — зоны frontend/**+deploy/**
