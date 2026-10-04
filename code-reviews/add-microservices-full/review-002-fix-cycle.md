# Ре-ревью фикс-цикла — пакет add-microservices-full (ЭТАП A)

Reviewer-Delegation: deleg-arch-rev-001

- Дата: 2026-10-04
- Ре-ревью к: `code-reviews/add-microservices-full/review-001-0.1-0.3.md` (verdict: request_changes)
- Проверяемый коммит: `0495346` — «tests(api): TC-трассировка контрактного гейта search-сервиса — фикс review-001 major 0.3-a (TC-openapi-201/202)»
- Зона фикса (по ТЗ): только major 0.3-a (TC-трассировка) и minor 0.3-b (xfail-reason → 1.5). Design §9 и nit'ы — сознательно вне круга (решение ПМ, релизный журнал R6, 12:34).
- Метод: собственные команды (git show / flow_check / openspec validate / чтение тест-файла целиком / живой прогон).

---

## 1. Дифф 0495346 — зона и состав

**Факт:** `git show 0495346 --stat` — ровно 1 файл: `tests/api/test_openapi_search_service.py`, +7/-6. Выхода за зону нет.

Состав диффа:
- module docstring: инвариант 1 помечен `(TC-openapi-201)`, инвариант 2 — `(TC-openapi-202)`; формулировка «задача 1.5 снимает xfail и тест зеленеет» сохранена.
- `test_search_contract_is_frozen` — docstring начинается с `TC-openapi-201`.
- `test_core_has_no_search_routes` — docstring начинается с `TC-openapi-202`.
- xfail `reason` заменен: «Активируется задачей **1.3**…» → «Активируется задачей **1.5**: снятие xfail после выделения search-сервиса (ЭТАП B)».

**Формат TC сверлен с tests/api/test_openapi_r11.py:** там трассировка в module docstring — строка `TC-ID: TC-openapi-101, TC-openapi-102 (test-model/regression/api/.)` плюс в docstring-описании. В новом файле выбран эквивалентный формат: TC-ID в module docstring (каждому инварианту) + TC-ID в docstring каждой тест-функции — даже прозрачнее (rule 6 проверяет вхождение `TC-…-NNN` в текст, покрывается на обоих уровнях). Написание идентично: `TC-openapi-…-NNN`, то же семейство `openapi`, что и у существующих кейсов regression/api/TC-openapi-101/102.

**Вывод:** дифф точно в зоне фикса; major 0.3-a закрыт, minor 0.3-b закрыт.

## 2. flow_check

**Факт:** `python scripts/flow_check.py .` → ровно **1** ошибка:

```
FLOW-ERROR: openspec/changes/add-microservices-full: 3 закрытых dev-задач без code-review —
каталог code-reviews/add-microservices-full/ пуст или без approve-вердиктов (J10): 0.1, 0.2, 0.3
```

Ошибки rule 6 (тесты без TC-трассировки) **нет** — именно она была major 0.3-a в review-001.

Технический факт для PM (вне зоны ревьюера): J10 связывает review-файл с задачами по числовым task-id в имени файла (`review-<NNN>-<task>-ids.md`) либо через `code-reviews/add-microservices-full/review-mapping.json`; имя `review-002-fix-cycle.md` task-id не содержит, поэтому 0.1/0.2/0.3 остаются «uncovered», пока PM не дополнит review-mapping.json строкой вида `{"review-002-fix-cycle.md": ["0.1","0.2","0.3"]}` (файл ревью содержит `## Вердикт: approve` + `Reviewer-Delegation: deleg-arch-rev-001` — оба обязательных атрибута парсера на месте, проверено чтением flow_check.py, строки 23–31, 96–156). На вердикт ревью это не влияет.

**Вывод:** предусловие approve выполнено.

## 3. Тест-файл целиком — логика не сломана

Прочитан весь файл (50 строк, состояние `0495346`):

- `test_core_has_no_search_routes`: `@pytest.mark.xfail(strict=True, reason=…)` — **strict сохранен** (изменен только текст reason). Проверки тела не тронуты: `search_router`/`suggestions_router` не в `backend/app/main.py`, оба assert на месте.
- `test_search_contract_is_frozen`: `paths = set(contract.get("paths", {}))`; `assert paths == EXPECTED_PATHS` — проверка **осталась строгим множеством** (ловит и лишние, и недостающие пути, симметрично, с диагностикой в сообщении). `openapi.startswith("3.")`, чтение с диска — без изменений.
- Сеть по-прежнему не нужна телу теста (импорты: json/pathlib/pytest; main.py читается с файловой системы).

**Живой прогон** (venv проекта): `1 passed, 1 xfailed in 0.11s` — совпадает с review-001. Нюанс окружения (не связан с фикс-циклом): без поднятого стенда автоз-фикстура `base_url` из tests/api/conftest.py (session-scope, poll `/api/health` 60 c → RuntimeError), затягиваемая autouse-фикстурой `_verify_url` плагина pytest-base-url, дает ERROR на setup первого теста — это предсуществующее поведение conftest (до 0299bef), не следствие диффа 0495346; на чистом прогоне без плагина (`-p no:base_url`) — `1 passed, 1 xfailed`. Рекомендация вне зоны (адресат SA/QA-инфра): файловым тестам без сетевых фикстур не мешала бы защита от autouse-фикстур стенда — не блокирует, отдельная тема.

## 4. openspec validate

**Факт:** `openspec validate --all --strict` → `Totals: 13 passed, 0 failed (13 items)`. Только INFO-замечания о длине requirement-текстов (предсуществующие, не из этого пакета).

## 5. Находки review-001 вне зоны фикса — перенос, не требование

Не входят в зону этого фикс-цикла (решение ПМ зафиксировано в релизном журнале R6) — **перенесено: адресат SA / не блокирует**:

- **трассировка-6 (minor):** design §9 устарел относительно нумерации tasks.md («0.4 каркас backup», «1.5 backup-sidecar») — адресат SA, следующая ревизия design.
- **0.1-b (nit):** design §3 «поднимает search-сервис» vs фактически монолит с фильтрацией в export-скрипте — адресат SA.
- **0.1-a (nit):** счет операций в commit message/отчете 0.1 («6 операций» вместо 4) — исторический артефакт исправлению не подлежит, учтен для будущих отчетов.
- **tasks.md 0.3 (minor, источник):** формулировка «активируется задачей 1.3» в tasks.md противоречит задаче активации 1.5 — поправить при следующей ревизии tasks.md (адресат PM/SA); в коде теста причина уже корректна (1.5).
- **Новое, информационное:** кейсы TC-openapi-201/202 пока не заведены в test-model/ (approved/regression) — семья TC-openapi-101/102 заведалась в цикле add-containerization; завести кейсы при авторизации кейсов пакета (адресат QA/SA, rule 6 этого не требует — не блокирует).

## Сводка

| Находка review-001 | Статус в 0495346 |
|---|---|
| 0.3-a major — нет TC-трассировки (flow_check rule 6 FAIL) | **Закрыт** (TC-openapi-201/202 в docstring; flow_check чист по rule 6) |
| 0.3-b minor — xfail-reason ссылался на 1.3 вместо 1.5 | **Закрыт** (reason = 1.5) |
| трассировка-6, 0.1-a, 0.1-b, tasks.md 0.3 | Перенесены: адресат SA/PM, не блокируют (см. §5) |

Новых замечаний уровня major/minor в зоне фикса нет.

## Вердикт: approve

Оба замечания зоны dev из review-001 (major 0.3-a, minor 0.3-b) закрыты коммитом 0495346; дифф хирургический (1 файл, +7/-6), логика гейта не ослаблена (strict xfail и строгое множество путей сохранены), flow_check чист по TC-трассировке (остаточная ошибка J10 — механика связки файл↔задачи через review-mapping.json, см. §2, закрывается PM вне зоны ревью), openspec validate 13/13. Отклоненные в перенос находки — вне зоны dev и не блокируют.
