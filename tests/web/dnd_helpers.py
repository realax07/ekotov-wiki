"""Помощники HTML5 DnD для web-тестов (урок architect-ревью кейсов
TC-dnd-101…106: Playwright НЕ эмулирует нативный HTML5 DnD мышью —
события возбуждаются dispatchEvent с общим объектом DataTransfer).

Нюансы продуктового cards.js, учтенные здесь:
- drag-ghost ставится в requestAnimationFrame после dragstart — класс
  читается только после очередного кадра (wait_raf);
- drop-target ставится обработчиком dragover на столбце-приемнике.

Урок regress №7 (флейк связки TC-dnd-106: green изолированно, красный
полной коллекцией tests/web): refreshBoard асинхронен — перерисовка
renderBoard от ПРЕДЫДУЩЕГО действия (в 106 — от 409-перевода шага 1)
приземляется между резолвом элемента локатором и evaluate-выражением
над ним. Detached-узел рвет el.closest('.board-column')
(TypeError: Cannot read 'dataset' of null) и уводит dragend с живой
карточки. Правило фикса: каждое событие жеста возбуждается в ОДНОМ
JS-таске со свежим querySelector по data-task-id — перерисовка
renderBoard синхронна (один JS-таск), поэтому атомарна относительно
нашего evaluate; никаких элемент-хендлов, переживающих кадр.
"""

# Одноразовый dragstart: карточка и ее столбец-источник читаются свежим
# querySelector в том же таске, где возбуждается событие.
# P23: карточка может лежать и в столбце зоны FASTLINE (.fastline-column,
# этап в data-fastline-stage) — статус-источник берется из обоих форматов.
_DRAGSTART_JS = """
(data) => {
  const card = document.querySelector(
    'article[data-task-id="' + data.taskId + '"]'
  );
  if (!card) { return { error: "card not found" }; }
  const column = card.closest(".board-column, .fastline-column");
  if (!column) { return { error: "card not in a column" }; }
  const fromStatus = column.dataset.status || column.dataset.fastlineStage;
  window.__qaDnD = {
    dt: new DataTransfer(),
    taskId: data.taskId,
    fromStatus: fromStatus,
  };
  const event = new DragEvent("dragstart", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: window.__qaDnD.dt });
  card.dispatchEvent(event);
  return { ok: true, fromStatus: fromStatus };
}
"""

# Класс карточки после очередного кадра (drag-ghost ставит rAF);
# карточка перечитывается свежим querySelector внутри rAF-колбэка —
# переживает перерисовку доски между dragstart и чтением.
_GHOST_JS = """
(data) => new Promise((resolve) => {
  requestAnimationFrame(() => {
    const card = document.querySelector(
      'article[data-task-id="' + data.taskId + '"]'
    );
    resolve(card ? card.className : null);
  });
})
"""

# dragover/drop на цели + dragend на карточке; card и target берутся
# свежими querySelector в одном таске — если перерисовка заменила узлы
# ПОСЛЕ dragstart, события все равно попадают в живые элементы (урок
# regress №7: dragend на detached-узле не доходил до делегирования
# #board и drag-ghost оставался висеть).
_FINISH_JS = """
(data) => {
  const state = window.__qaDnD;
  if (!state) { return { error: "no drag session" }; }
  const card = document.querySelector(
    'article[data-task-id="' + state.taskId + '"]'
  );
  const target = document.querySelector(data.targetSelector);
  if (!card) { return { error: "card not found" }; }
  if (!target) { return { error: "target not found" }; }
  const fire = (el, type) => {
    const event = new DragEvent(type, { bubbles: true, cancelable: true });
    Object.defineProperty(event, "dataTransfer", { value: state.dt });
    el.dispatchEvent(event);
    return event.defaultPrevented;
  };
  const result = {};
  result.dragoverPrevented = fire(target, "dragover");
  result.targetClass = target.className;
  if (data.drop) {
    result.dropPrevented = fire(target, "drop");
  }
  fire(card, "dragend");
  result.cardClassAfterDragEnd = card.className;
  return result;
}
"""


def _card_task_id(card) -> int:
    """taskId из атрибута карточки (get_attribute — действие Playwright
    с auto-retry резолва; сам жест дальше ищет карточку заново)."""
    task_id = card.get_attribute("data-task-id")
    assert task_id, "у карточки нет data-task-id"
    return int(task_id)


def dnd_start(page, card) -> str:
    """dragstart на карточке (синтетический, с общим DataTransfer).
    Возвращает fromStatus столбца-источника (читается в том же таске)."""
    result = page.evaluate(_DRAGSTART_JS, {"taskId": _card_task_id(card)})
    assert "error" not in result, result
    return result["fromStatus"]


def dnd_card_class_after_raf(page, card) -> str:
    """Класс карточки после очередного кадра (drag-ghost ставит rAF)."""
    return page.evaluate(_GHOST_JS, {"taskId": _card_task_id(card)})


def dnd_finish(page, card, target_locator, *, drop: bool = True) -> dict:
    """dragover (+ drop) на цели, затем dragend на карточке.
    Возвращает наблюдаемые классы/факты preventDefault. card — только
    источник taskId: элемент перечитывается свежим querySelector
    (урок regress №7 — никакого переиспользования узлов через кадр)."""
    target_selector = target_locator.evaluate(
        """el => {
          if (el.id) { return '#' + CSS.escape(el.id); }
          let path = el.tagName.toLowerCase();
          if (el.dataset.status) { path += '[data-status="' + el.dataset.status + '"]'; }
          return path;
        }"""
    )
    return page.evaluate(
        _FINISH_JS,
        {"targetSelector": target_selector, "drop": drop},
    )


def dnd_dispatch(page, card, target_locator, *, drop: bool = True) -> dict:
    """Полный жест: dragstart → кадр (rAF) → dragover/drop/dragend.
    cardClass читается после rAF — момент постановки drag-ghost.
    Все три шага перечитывают карточку свежим querySelector: асинхронная
    перерисовка refreshBoard между шагами жест не ломает."""
    from_status = dnd_start(page, card)
    result = {"cardClass": dnd_card_class_after_raf(page, card),
              "fromStatus": from_status}
    result.update(dnd_finish(page, card, target_locator, drop=drop))
    return result
