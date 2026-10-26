# BUG-024: диалог «Ссылка» теряет выделение редактора — createLink вставляет URL как новый текст вместо обертки выделения

- **Набор:** coverage-backfill-1 группа A (playwright web, chromium), кейс TC-rich-029
- **Дата:** 2026-10-26 · **Ветка:** qa/cov-backfill-rich (база origin/chore/sa-coverage-backfill)
- **Воспроизведение:** tests/web/test_coverage_rich_tools_security.py::test_tc_rich_029_toolbar_wysiwyg_roundtrip
  (шаг «ссылка на источник» → «Ссылка»); минимальный сценарий ниже.

## Кейс / ожидание / факт

- **Кейс:** TC-rich-029 (WYSIWYG round-trip): применить к фрагменту ссылку;
  сохраненная статья отображает тот же вид.
- **Ожидание:** выделенный текст оборачивается в `<a href=…>` (FR-110,
  стандартное поведение createLink).
- **Факт:** диапазон выделения СЛУЖБОВО СХЛОПЫВАЕТСЯ при открытии диалога
  (focus уходит в `#wiki-link-url`), и `applyLink` выполняет
  `execCommand('createLink')` на СВЕРНУТОЙ каретке в начале области:
  вместо обертки выделения вставляется НОВЫЙ узел
  `<a href="URL">URL</a>` перед первым символом первой строки, а выделенный
  фрагмент остается без ссылки. Минимальный сценарий (две строки, вторая
  выделена программным range):
  `<h2><a href="https://example.com/doc">https://example.com/doc</a>строка для ссылки</h2><div>вторая строка</div>`.
  Дефект НЕ виден в tests/web/test_p15_wiki_editor.py::test_link_javascript_scheme_rejected,
  т.к. тот ассертит лишь факт наличия `<a href>`, а не обертку выделения.

## Локализация

`frontend/static/js/wiki/editor.js` — `openLinkDialog()`
(`state.linkInput.focus()` сбрасывает live-выделение contenteditable) и
`applyLink()` (`focusAreaAndRun(() => execCommand('createLink', …))` —
выделение уже свернуто). Лечится сохранением Range при открытии диалога и
восстановлением (`selection.removeAllRanges(); addRange(saved)`) перед
createLink.

## Рецепт фикса

```js
function openLinkDialog() {
  state.linkRange = window.getSelection().rangeCount
    ? window.getSelection().getRangeAt(0).cloneRange() : null;
  …
}
function applyLink() {
  …
  focusAreaAndRun(function () {
    if (state.linkRange) {
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(state.linkRange);
    }
    document.execCommand('createLink', false, check.url);
  });
}
```

## Серьезность и влияние

- **major** (функциональность FR-110): ссылку нельзя повесить на
  существующий фрагмент — текст инструментом «Ссылка» не оборачивается,
  URL-текст вставляется в начало первой строки (внутри блока с кареткой
  на момент записи выделения).
- Не блокирует прогон coverage-backfill-1: TC-rich-029 проверяет
  round-trip инструмента (ссылка, вставленная редактором, доезжает до
  статьи без искажений); обертка выделения зафиксирована настоящим
  баг-репортом.

## Статус: OPEN (2026-10-26)
