# Code Review: add-responsive-mobile — задача 1.2 [S] (индикация активного раздела + z-фикс бургера)

- **Ревьюер:** независимый code_reviewer-сабагент (не автор диффа) — прогон восстановлен ПМ после двойного обрыва
- **Дата:** 2026-10-08 17:45 UTC
- **Correlation:** 076eb97c46474be6a5618f36acb22089
- **Делегация дева:** в составе волны 1 (дев-отчет волны)
- **Reviewer-Delegation:** deleg_3646c6f7 (прогон 1) + deleg_ecf87f4f (прогон 2)

> Примечание ПМ: обе платформенные делегации ревьюера прерваны ротацией сессии
> gateway (16:54 и 17:16 UTC, `delivery_state='dropped'`, состояние причины —
> REPORT о падении сессий от 2026-10-08). Результаты извлечены из
> `async_delegations.result_json`, живые транскрипты
> `~/.hermes/cache/delegation/live/deleg_3646c6f7/task-0.log` и
> `deleg_ecf87f4f/task-0.log`. Вердиктный прогон не был завершен ревьюером
> самостоятельно; ключевые факты верифицированы ПМ независимо (ниже).

## Provenance

| Поле | Значение |
|---|---|
| Ревьюемый код | c61225cf829133aa372523829f133591e1274df8 (ветка feature/p14-1.2-active-section, PR #110, НЕ мержен) |
| Голова ветки на момент вердикта | 8159650511af8b3c2252d4703f7b98b2bb410507 (ребейз на main 078b373: мета 1.1; дерево отличается только docs-метой) |
| sha256 frontend/static/css/app.css | 2b20a03615fe949c06b78f926c6a480cbd53160bebde321bd0e2bae982b55e22 (= c61225c, сверено ПМ после ребейза) |
| sha256 frontend/templates/base.html | 8488b802d274901a4355b0c03efa8611862a168c09ed4022871a538751af94c5 (= c61225c, сверено ПМ после ребейза) |
| Арбитры | openspec/changes/add-responsive-mobile/design.md §2, specs/navigation/spec.md, tasks.md 1.2, мокап design/mobile-p14/01-frame-drawer-closed.html (утв. decision 2026-10-08-p14-mockups-approve) |
| Прогон 1 (deleg_3646c6f7, 16:43–16:54) | собственный стенд uvicorn:39979 + http.server:57269; 59/59 ассертов GREEN; мутационная z-фикса поймана; смежные web-тесты 20 passed; прерван на gallery/crop-проверке (502, pre-existing-ность не установлена независимо) |
| Прогон 2 (deleg_ecf87f4f, 17:05–17:16) | стенд uvicorn:57531 + http.server:47211; z-фикс подтвержден (z=320, тап ловит бургер, первый пункт drawer не накрыт, padding-top корректен); обнаружено смещение титула; прерван до скриншот-верификации |

## Вердикт: **RETURN**

Blocker нет. Один major: порядок flex-детей мобильной шапки противоречит
утвержденному мокапу 01 — титул раздела не центрирован. z-фикс бургера
(minor-1 review-001-1.1) реализован корректно и подтвержден дважды
независимо (мутационная проверка прогона 1 + probe прогона 2).

## Замечания

### major

| # | Файл:место | Серьезность | Суть | Рекомендация |
|---|---|---|---|---|
| 1 | frontend/templates/base.html (`.mobile-header`: `<p class="header-title">` ПЕРЕД `<button class="burger">`, спейсер после) | major | Мокап 01 (арбитр, design/mobile-p14/01-frame-drawer-closed.html): порядок детей `burger → title(flex:1, text-align:center) → spacer(44px)` — титул центрируется между бургером и спейсером. Реализация: `title → burger → spacer` — `text-align:center` центрует титул внутри его flex-коробки, коробка сжата слева бургером → титул смещен влево. Измерение ревьюера (прогон 2): titleCenter 139.5 vs headerCenter 187.5. Независимая верификация ПМ на чистом стенде (probe /tmp/p14-12-pm/pm_title_probe.py, 375×812 touch): `offset: -48px` (44px бургер + 4px gap) — подтверждено. | Привести порядок детей к мокапу: `burger → header-title → header-spacer`. Сверить итоговую геометрию probe'ом (\|offset\| < 2px), скриншот против мокапа 01. |

### minor

Замечаний уровня minor в зоне диффа нет (minor-2/3 review-001-1.1 вне зоны 1.2).

## Проверенное

| Пункт | Проверка ревьюера |
|---|---|
| Титул раздела на всех 6 путях (/board, /search, /wiki, /gallery, /settings, /settings/profile; settings-profile → «Настройки») | ✅ прогон 1+2: текст и 17px везде, роль presentation (не heading — strict-локаторы смежных тестов не ломаются) |
| z-фикс бургера (minor-1 review-001-1.1) | ✅ дважды: мутационная (убран z320 → elementFromPoint ловит `.sidebar-backdrop`, RED; восстановление byte-identical, sha256 `2b20a036…` → GREEN) + probe: `z-index: 320`, тап по центру бургера ловит `burger`, drawer закрывается, первый пункт `nav-item` не накрыт (itemTop 68 ≥ headerBottom 56), padding-top открытого drawer корректен |
| Полный набор ассертов задачи | ✅ прогон 1: 59/59 GREEN (титулы, .active в drawer, drawer open/close все пути, desktop 1280 без изменений) |
| Смежные web-тесты | ✅ navigation+p12nav+qa21netdata+settings+profile: 20 passed (прогон 1, 16:51) |
| openspec validate --strict | ✅ 17 passed (дев-отчет; ревьюером не перепрогонялся) |
| Галерея/crop-фейлы на чистом main | ⚠️ НЕ установлено независимо: прогон 1 прерван на этой проверке (502 на test_qa21_gallery_ui). Дев-отчет декларирует воспроизведение на чистом main f8b3440. Для RETURN-вердикта не критично; при повторном ревью после фикса — подтвердить. |
| Титул по центру шапки (мокап 01) | ❌ FAIL — major-1 |

## Что НЕ проверено (честно)

- Скриншот-сверка с мокапом 01 «глазами» (прогон 2 прерван перед vision-анализом; геометрия проверена числово).
- Реальные touch-события (эмуляция Playwright).
- design_validator pixel-consistent — вне роли code_reviewer (волна 5.1в).

## Границы

Ревьюер код не правил (мутация z-фикса — временная, восстановлена byte-identical,
git diff quiet). ПМ код не правил. Merge не выполнялся. Стенды ревьюеров
погашены (ПМ, 17:35–17:40 UTC — включая осиротевшие после обрывов).
Provenance-запись (gate_runner record-review) — за ПМ при влите review-файла.
