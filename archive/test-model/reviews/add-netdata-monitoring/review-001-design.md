# review-001-design — design_validator 2.1(г): пункт «Мониторинг» vs мокап 1.1а (add-netdata-monitoring)

- **Reviewer-Delegation:** deleg_0b722e1e

- **Дата:** 2026-10-05
- **Роль:** design_validator (часть задачи 2.1; correlation 97a81b928f744dd6a76cdce801802699)
- **Дерево:** worktree `/home/openclaw/ekotov-wiki-worktrees/qa-21-netdata`, ветка `add-netdata-monitoring`, HEAD `2e6efb5` (факт 1.4 = `7abdf12`)
- **Эталоны:** `design/netdata-sidebar-mockup.html` (eac40de) + `design/netdata-icon.svg`; решение Заказчика `decisions/2026-10-05-netdata-mockup-approval.md` (коммит 4099f86): «без промпт-карточки / иконку утверждаю / маркер НЕ нужен»; design.md §0 п.4, §3
- **Метод:** живой DOM (Playwright chromium) на QA-стенде nginx :18443 (паритет прод-конфига) + computed-style; автоматизировано тестом `tests/web/test_qa21_netdata_sidebar_ui.py::test_design_validator_markup_and_tokens` (GREEN)

## Сверка

| Критерий | Мокап (эталон) | Факт (продукт) | Вердикт |
|---|---|---|---|
| Контейнер | `a.nav-item.nav-item-monitoring` в `.sidebar-footer`, ПЕРЕД «Настройки» | идентично; insertBefore(.nav-item-settings) в profile.js | ✓ |
| href/target/rel | `/netdata/`, `_blank`, `noopener` | идентично (href — константа NETDATA_URL) | ✓ |
| Иконка | inline-SVG polyline `2.5 12 7 12 10 5.5 14 18.5 17 12 21.5 12`, fill=none, stroke=currentColor, width 2, round cap/join, 16px, aria-hidden | посимвольно; bounding box 16×16px | ✓ |
| Маркер ext-hint | в .html мокапа присутствует (строки 150/160-161/186 — остаток варианта ДО решения Заказчика) | отсутствует (locator count=0) — соответствует УТВЕРЖДЕННОМУ решению («маркер не нужен»), а не устаревшей строке артефакта | ✓ (см. примечание N-1) |
| Промпт-карточка перехода | transition-mockup (архив по решению) | нет: клик → /netdata/ напрямую | ✓ |
| Цвет пункта | `--p-paper-050` #faf7f2 | computed rgb(250,247,242); токен читается из `:root` (не хардкод в правиле — `color: var(--p-paper-050)`) | ✓ |
| hover | фон rgba(255,253,249,0.08), opacity 1 | computed совпадает; значение — унаследованный каркас `.nav-item:hover` (N-2 review-001-1.4: допустимо, кандидат на токенизацию `--nav-veil` в будущей полировке) | ✓ |
| focus-visible | inset focus-ring rgba(168,67,44,0.35) | box-shadow: inset rgba(168,67,44,0.35) при клавиатурном фокусе (`--focus-ring` из :root) | ✓ |
| active | фон `--color-accent` #a8432c | rgb(168,67,44) при нажатии; правило `background: var(--color-accent)` | ✓ |
| Роль-гейт | пункт только owner («Product manager» из /api/auth/me); PE/аноним — не создается | подтверждено тестами (owner видит / wife не видит / аноним не видит) | ✓ |
| Позиция/соседи | «Мониторинг» → «Настройки» → «Выйти» → профиль | порядок в footer подтвержден регресс-тестом | ✓ |
| Токены, не хардкод | — | color/ring/active — var(); единственное сырое значение — вуаль каркаса (см. hover) | ✓ |

## Вердикт: **APPROVE**

Расхождений с утвержденным видом нет; решение Заказчика 4099f86 исполнено
(а не буква устаревшего артефакта мокапа).

### Примечания (не блокеры)

- **N-1:** `design/netdata-sidebar-mockup.html` все еще содержит `.ext-hint`
  (маркер внешней ссылки) и demo-правила к нему — противоречит решению
  Заказчика. Зафиксировано еще в review-001-1.4 (замечание 1, minor).
  Рекомендация: косметическая правка/аннотация ui_designer'ом (зона design/**)
  при случае; на продукт не влияет.
- **N-2:** вуаль hover `rgba(255,253,249,0.08)` — сырое значение каркаса
  R3 (app.css `.nav-item:hover`), не новый хардкод задачи 1.4. Кандидат на
  токенизацию в полировке V3.
