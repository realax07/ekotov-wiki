# Review 005 — задача 3.2: tooltip профиля (feature/r4-tip, ab93f9f)

- **Ревьюер:** code_reviewer конвейера ai-factory
- **Масштаб:** `git diff main..feature/r4-tip` на коммите ab93f9f: `frontend/static/js/tooltip.js` (new, 180 строк), `frontend/static/js/profile.js` (+83), `frontend/static/css/app.css` (+89), `tests/web/test_tooltip_r4.py` (new, 374 строки), checkbox tasks.md 3.2 → [x]. Прод не затронут (worktree r4-tip, `pages.py`/`static_v` не менялись).
- **Метод:** сверка диффа с design §5 (единый механизм, §11 риск «у нижнего края»), дельтами specs/navigation + specs/board (Scenario «Единый механизм всплывашек») + specs/auth (состав me), FR-43, ОГР-17, ОВ-25, Д-10, TC-vis-105; независимые прогоны в venv `/home/openclaw/venvs/wiki`.

## Вердикт: approve

Задача может вливаться. Спецификация выполнена полностью, включая негативные сценарии; XSS-гигиена соблюдена; API модуля готов к переиспользованию в 5.1 без перевертывания DOM. Два minor-замечания, ни одно не блокирует.

## Соответствие спеке (первый круг)

- **FR-43 / ОВ-25 (состав tooltip профиля):** аватар (или кружок-фоллбек с первой буквой), display_name или логин (Д-10), логин, роль, bio — ровно по design §5; пустые role/bio — блоки не рендерятся; пустой display_name — fallback на логин. Покрыто TC-tip-101/103/106 (badge O / img `?v=` / пустое bio при живом остальном составе).
- **ОГР-17 (один экземпляр, переиспользование):** модуль хранит единственный `div#app-tooltip` (module-level `tooltipEl` + `ensureTooltip()`); TC-tip-105 доказывает `querySelectorAll('#app-tooltip').length === 1` при show на два target'а. Публичный API `show(target, content|узел)` / `hide()` / `attach(target, buildContent, {delay})` → `detach()` — контент карточки 5.1 строится самой карточкой из уже загруженных данных (design §5, без отдельных запросов), DOM карточек не затрагивается. `buildContent()` — фабрика свежего узла на каждый показ.
- **Позиционирование (design §5/§11):** `position: fixed` по `getBoundingClientRect` (не зависит от скролла/родителей); низ-лево с клампом по горизонтали, нехватка снизу → вверх, финальный кламп `top >= margin`. Замер размеров по нулевой позиции перед клампом — корректно. TC-tip-104: все 4 границы вьюпорта + позиция «вверх» (низ tooltip ≤ низ профиля) + совпадение левых краев.
- **TC-vis-105 / reduced-motion:** CSS `@media (prefers-reduced-motion: reduce) { transition: none !important }`; тест подтверждает computed `transition-duration: 0s` **и** мгновенный `opacity: 1` (TC-tip-107).
- **aria:** `role="tooltip"` на всплывашке + `aria-describedby="app-tooltip"` на target на время показа, снимается при скрытии (TC-tip-101); target имеет `tabindex=0` (из 3.1) — focus-путь работает (TC-tip-102, Escape — негативный путь).
- **Клик при видимой всплывашке:** `pointer-events: none` в CSS + задержка показа 300мс; TC-tip-108: hover → tooltip виден → click → URL `/settings/profile` (не /settings, ОГР-20).
- **Вне спеки ничего не добавлено.**

## Безопасность / гигиена (XSS)

bio, display_name, логин, роль — только `createElement` + `textContent`; строковый контент `show()` — через `textContent`; URL аватара — свойство `src` (не разметка), alt пустой. Инъекция через пользовательские строки невозможна. Динамический `import("./tooltip.js")` с `.catch` — деградация «без всплывашки», без глотания ошибок рендера.

## Проверено прогоном (независимо)

- **tests/web, полный** (собственный tmp-стенд conftest, `env -u EKOTOV_WIKI_BASE_URL -u EKOTOV_WIKI_DB_PATH -u EKOTOV_WIKI_AVATARS_DIR`, AVATARS_DIR=tmp): **92 passed, 1 skipped**, в т.ч. `test_tooltip_r4.py` — **8/8**.
- **tests/api, полный** (scratch-стенд uvicorn :8902, tmp-БД + `app.seed_users` + `app.migrate_r4`, AVATARS_DIR=tmp): **157 passed, 9 skipped, 2 xfailed** — совпадает с базлайном review-004. Прод не затронут.
- Примечание к прогону (дефект среды ревьюера, не кода): bare `app.seed_users` не проставляет роли ОВ-21 (их бэкфиллит `migrate_r4` — на web-стенде роли дублируются в conftest-seed); первый прогон api с bare-seed дал 7 «падений» (role=None, 500 на аватаре — стенд без AVATARS_DIR), после `migrate_r4` + явного `AVATARS_DIR` на стенде — чистые 157.

## Замечания

| # | Файл/место | Серьезность | Замечание | Рекомендация |
|---|---|---|---|---|
| m-1 | tooltip.js `show()` / test_module_api_reuse | minor | Прямой `show(b, …)` поверх показанного `show(a, …)` не снимает `aria-describedby` с предыдущего target — атрибут остается висеть до явного `hide()`. Тест TC-tip-105 это даже фиксирует (`shownOnA == "app-tooltip"` после show(b)). В реальном attach-потоке (mouseleave → hide → show) гонки hover между двумя карточками не возникает — атрибут снимается сразу в `hide()`, дефект недостижим через attach. | В `show()` перед `currentTarget = target` снять атрибут со старого `currentTarget`; скорректировать ожидание TC-tip-105. Можно отложить в задачу 5.1. |
| m-2 | tooltip.js `show()` | minor | Переключение target'ов в окне HIDE_DELAY_MS (250мс) дает короткий миг скрытия: hide() поставил `hidden` через 250мс, show() нового target'а сработал на 300мс — всплывашка мигает. Чистая косметика перехода. | При `show()` поверх идущего скрытия можно не давать `hidden=true` дозиграть (уже делается clearTimeout) плюс пропускать повторный reflow-хак; либо не откладывать `hidden`, а только класс. Не блокирует. |

## Проверенные Scenario

navigation MODIFIED «display_name» (TC-tip-101/103); board ADDED «Единый механизм всплывашек» (TC-tip-105); «Уменьшение движения отключает анимации» (TC-tip-107); design §5 hover/mouseleave (TC-tip-101), focus/Escape (TC-tip-102), вьюпорт (TC-tip-104); ОВ-25 состав/пустое bio/аватар (TC-tip-101/103/106); FR-39 regression клик при видимой всплывашке (TC-tip-108). Негативные пути Escape и пустых полей покрыты.

## Что НЕ проверено

- Реальные карточки задач с tooltip (5.1) — вне задачи; проверена только механика модуля через публичный API.
- Мобильные/узкие вьюпорты: кламп проверен на дефолтном viewport Playwright; поведение при ширине < max-width tooltip не тестировалось отдельно.
- Скриншот-регресс / визуальная полировка CSS (токены V3 использованы, сверка осмотром).
- Поведение при очень длинном bio (перенос `white-space: pre-line` + `overflow-wrap: anywhere` — осмотром, нагрузочным тестом не проверено).
