"""Помощники HTML5 DnD для web-тестов (урок architect-ревью кейсов
TC-dnd-101…106: Playwright НЕ эмулирует нативный HTML5 DnD мышью —
события возбуждаются dispatchEvent с общим объектом DataTransfer).

Нюансы продуктового cards.js, учтенные здесь:
- drag-ghost ставится в requestAnimationFrame после dragstart — класс
  читается только после очередного кадра (wait_raf);
- drop-target ставится обработчиком dragover на столбце-приемнике.
"""

# Одноразовый dragstart на карточке; возвращает id и исходный статус.
_DRAGSTART_JS = """
(data) => {
  const card = document.querySelector(
    '.board-column[data-status="' + data.fromStatus + '"] ' +
    'article[data-task-id="' + data.taskId + '"]'
  );
  if (!card) { return { error: "card not found" }; }
  window.__qaDnD = { dt: new DataTransfer(), card: card };
  const event = new DragEvent("dragstart", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: window.__qaDnD.dt });
  card.dispatchEvent(event);
  return { ok: true };
}
"""

# dragover/drop на цели + dragend на карточке; читает классы после кадров.
_FINISH_JS = """
(data) => {
  const state = window.__qaDnD;
  const card = state.card;
  const target = document.querySelector(data.targetSelector);
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


def dnd_start(page, card) -> None:
    """dragstart на карточке (синтетический, с общим DataTransfer)."""
    task_id = card.get_attribute("data-task-id")
    assert task_id, "у карточки нет data-task-id"
    from_status = card.evaluate(
        "el => el.closest('.board-column').dataset.status"
    )
    result = page.evaluate(
        _DRAGSTART_JS, {"taskId": int(task_id), "fromStatus": from_status}
    )
    assert "error" not in result, result


def dnd_card_class_after_raf(page, card) -> str:
    """Класс карточки после очередного кадра (drag-ghost ставит rAF)."""
    return card.evaluate(
        "el => new Promise((resolve) => requestAnimationFrame(() => resolve(el.className)))"
    )


def dnd_finish(page, card, target_locator, *, drop: bool = True) -> dict:
    """dragover (+ drop) на цели, затем dragend на карточке.
    Возвращает наблюдаемые классы/факты preventDefault."""
    task_id = card.get_attribute("data-task-id")
    from_status = card.evaluate(
        "el => el.closest('.board-column').dataset.status"
    )
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
        {
            "taskId": int(task_id),
            "fromStatus": from_status,
            "targetSelector": target_selector,
            "drop": drop,
        },
    )


def dnd_dispatch(page, card, target_locator, *, drop: bool = True) -> dict:
    """Полный жест: dragstart → кадр (rAF) → dragover/drop/dragend.
    cardClass читается после rAF — момент постановки drag-ghost."""
    dnd_start(page, card)
    result = {"cardClass": dnd_card_class_after_raf(page, card)}
    result.update(dnd_finish(page, card, target_locator, drop=drop))
    return result
