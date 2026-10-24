# TC-redesign-010: Единый источник токенов — перенос без изменения значений

## Трассировка
- **CHK:** CHK-010
- **Тип:** поз. | **Приоритет:** Must (по CHK-010)
- **FR/Требование:** design-tokens ADDED — «Единый источник дизайн-токенов «Пульт»» (FR-128)
- **Scenario:** «Перенос токенов без изменения значений», «Служебные токены техноязыка определены»

## Предусловия
- Эталон: `design/redesign-pro/tokens-console.html` (базлайн b5a1475); редизайн применен.
- Доступ к `frontend/static/css/app.css`; скрипт-сверка гейта 1.1 (REPORT волны 1.1).

## Шаги
1. Сравнить блок `:root` app.css с блоком токенов tokens-console.html дословно (скриптом: парсинг `--p-*`/`--glow-*`/etc. из обоих файлов, diff по именам и значениям). Контрольные значения: `--p-bg-000 #0e1621` … `--p-bg-300 #26354d`, `--p-border #33435c`, `--p-border-2 #4d607c`, `--p-text-900 #e7edf4`, `--p-amber-400 #f0b45c`, `--p-amber-900 #3a2c12`, `--p-cyan-300 #4fd8eb`, статусы teal/coral/violet.
2. Проверить наличие `color-scheme: dark` в `:root`/html.
3. Проверить определение служебных токенов техноязыка: `--glow-amber`, `--glow-cyan`, `--texture-grid` (ячейка 32px), `--font-family-data`, `--tracking-caps`/`--tracking-micro`, `--focus-ring`, `--speed-fast` 140ms, `--speed-modal` 200ms.
4. Открыть любую страницу фронта: рендер темный (фон `--p-bg-000`, текст `--p-text-900`) — сверить computed `background-color`/`color` с `body`.

## Ожидаемый результат
- Diff `:root` app.css vs tokens-console.html — пустой (каждое значение: hex, rgba, ms, px, stacking focus-ring — совпадает).
- `color-scheme: dark` объявлен; все служебные токены списка определены.
- Рендер страниц темный, значения берутся из токенов.
