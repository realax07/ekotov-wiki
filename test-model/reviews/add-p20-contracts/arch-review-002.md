# arch-review-002 — add-p20-contracts (сверка по списку возврата arch-review-001)

- **Change:** add-p20-contracts (P20 «Сервисные контракты»)
- **Ревью:** arch-review-002, роль архитектор (второе ревью — сверка доработки СА по списку возврата arch-review-001)
- **База:** main @ 7e615bf (merge PR #289, commit 7c04155 «СА-доработка по возврату arch-review-001 (Д-Б1/Д-Б2/Д-З1/Д-З2)»)
- **Сверено:** openspec/changes/add-p20-contracts/{design.md, tasks.md, requirements.md, impact.md, proposal.md, specs/contracts/spec.md} против живого кода сервисов (services/video/app/{videos,social}.py, services/images/app/gallery.py, services/search/app/main.py, contracts/openapi-search.json, scripts/export_openapi_search.py)

## Сверка по списку возврата arch-review-001

### Д-Б1 — IR-07 сужен до `^contracts/openapi\.json$` и перенесен в волну 0 — ЗАКРЫТО

- **design §5:** сужения IR-01 и IR-07 явно отнесены к волне 0, ДО первой волны
  с якорем/контрактом, с обоснованием «без переноса в волну 0 волны 2–4
  немержибельны в CI»; триггер IR-07 после сужения — `^contracts/openapi\.json$`;
  IR-07 сохраняется как guard на ядерный контракт, контроль сервисных — IR-08…IR-11.
- **tasks.md:** волна 0 «Подготовка: сужение IR-01 и IR-07» — задача 0.2 сужает
  IR-07 `when[].path` → `^contracts/openapi\.json$` с механическими проверками
  (JSON читается; симуляции: новый `contracts/openapi-video.json` — DENY нет;
  ОГР-31-дифф — DENY нет; чистый HEAD — DENY нет).
- **specs/contracts/spec.md:** требование «Сужение существующих правил IR-01 и
  IR-07 до волн заморозки» — «MUST быть сужены волной 0», триггер IR-07 —
  `^contracts/openapi\.json$`; два сценария: волна заморозки проходит ворота,
  ОГР-31-PR проходит без ядерного контракта.

### Д-Б2 — IR-01 сужен до `^services/[^/]+/openapi\.json$`, тоже в волне 0 — ЗАКРЫТО

- **design §5:** тот же блок волны 0; сужение IR-01 до `^services/[^/]+/openapi\.json$`
  (yaml-якоря `services/<svc>/openapi.yaml` перестают триггерить ложный DENY,
  правило консервируется как guard).
- **tasks.md:** задача 0.1 (волна 0) — точный regex, симуляция «новый
  services/video/openapi.yaml» → DENY нет.
- **specs/contracts/spec.md:** то же требование волны 0, сценарий покрывает
  суженный IR-01 совместно с IR-07.

### Д-З1 — числа операций по коду: video=14, images=11; «15»/«11+health» сняты — ЗАКРЫТО

Пересчет по живому коду (grep декораторов маршрутов):

| Файл | Декораторов | Код |
|---|---|---|
| `services/video/app/videos.py` | 7 (POST/GET/GET file/GET preview/DELETE/PATCH/GET authcheck) | подтверждено |
| `services/video/app/social.py` | 6 (comments GET/POST/DELETE, reaction DELETE/PUT, categories GET) | подтверждено |
| `services/images/app/gallery.py` | 10 (POST/GET/GET id, like PUT×2, dislike PUT×2, comments POST/DELETE, rename PUT) | подтверждено |

- **Документы:** video — «14 операций (`videos.py` 7 + `social.py` 6 + `/api/health`)»
  (design §1, tasks 2.1, specs, FR-135); images — «11 операций (`gallery.py` 10 +
  `/api/health`)» (design §1, tasks, specs, FR-134). 7+6+1=14, 10+1=11 — сходится.
- **Хвосты сняты:** grep по пакету на «15 операц…» — пусто; формулировки
  «11+health» как отдельного числа нет. Оставшиеся упоминания «4 пути» в контексте
  search (design §1, tasks 1.1/1.2, requirements АКТУАЛЬНА, FR-137, impact, proposal) —
  корректны: это описание ТЕКУЩЕГО замороженного контракта (проверено: в
  `contracts/openapi-search.json` ровно 4 path-items), который волной 1 станет 5.
- design §1 корректно уточняет: сверка — по path-items живой схемы, не по числу
  операций (у FastAPI path-items < операций при нескольких методах на путь).

### Д-З2 — search: живая схема 1:1 (5 path-items с health), переэкспорт волной 1, TC-openapi-20х синхронно — ЗАКРЫТО

- **Живая схема = 5 path-items:** `/api/health` есть в живом коде сервиса
  (`services/search/app/main.py:66` + exempt в middleware); замороженный контракт
  содержит 4 пути (проверено парсингом `contracts/openapi-search.json`), т.е.
  расхождение и объем переэкспорта описаны верно.
- **Переэкспорт волной 1:** tasks 1.1 — правка `scripts/export_openapi_search.py`
  (упразднение `_filter_search_schema`, полный экспорт: 5 path-items с `/api/health`),
  переэкспорт контракта, обновление якоря; критерии механические (множество путей =
  живому 1:1; повторный экспорт — пустой дифф; `services/search/app` не меняется —
  ОГР-29). design §7: волна 1 — search, переэкспорт + синхронные path-ассерты.
- **TC-openapi-201…210 синхронно:** tasks 1.2 — только ассерты множеств путей
  («ровно 4 пути» → 5 с `/api/health`, включая TC-openapi-201/205), поведение не
  трогается, behavior-neutral оговорка к NFR-45; проверка — прогон обоих сьютов.
  Маркеры подтверждены в живых тестах: TC-openapi-201/202 (tests/api/
  test_openapi_search_service.py), TC-openapi-203…210 (services/search/tests/
  test_search_service.py) — все существуют, нумерация непрерывна.
- FR-137, impact.md, proposal.md синхронизированы (4 → 5, Д-З2).

## Прочие проверки

- Волны: 0 (сужения) → 1 search → 2 video → 3 images → 4 weather → 5 схемная
  валидация → 6 карта+nginx → 7 гейт; сужения гейт не включают — согласовано
  между design §7, tasks.md и specs.
- Карта: без изменений — пакет на этапе СА-документации, код сервисов/ядра не
  меняется (ОГР-29), архитектурных сдвигов нет; карточка будет актуализирована
  задачей волны 6 по плану пакета.

## Вердикт: Одобрить (approve)

Все четыре пункта списка возврата arch-review-001 (Д-Б1, Д-Б2, Д-З1, Д-З2)
закрыты; числа и формулировки сверены с живым кодом сервисов, расхождений
план/код не найдено. Пакет допускается к dev-этапу по волнам tasks.md.
